import csv
import enum
import importlib
import importlib.metadata
import inspect
import io
import json
import os
import pkgutil
import re
import sqlite3
import zlib
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from xml.etree import ElementTree as ET

import requests
import typer
from tabulate import tabulate

HELP = """
Look up financial vocabulary, identifier schemes and definitions from
third-party sources instead of inventing them.

Sources are fetched the first time a command needs them and cached in
`data/semantics.db`. Every row carries its source and that source's version;
cite both when stating a definition.

- `sources` lists every source with licence, version and row counts
- `schemes` lists identifier schemes and whether each is `concept-only`,
`syntax-validated` or `resolvable`
- `identify VALUE` infers the scheme of a bare string offline from syntax,
check digits and code lists; no match means a `vendor` symbol
- `resolve VALUE [--to SCHEME]` asks a registry (FIRDS, GLEIF, OpenFIGI)
or a cached code list what the identifier denotes; registry answers are
cached for 30 days
- `term LABEL [--source SOURCE]` returns definitions whose label contains
`LABEL`, ignoring case, spaces and punctuation; rows from different sources
are shown side by side and never merged

`--refresh SOURCE` (or `all`) before the command redownloads and reindexes a
source, or clears the cached answers of a registry. `--json` on every
command. `OPENFIGI_API_KEY` raises the OpenFIGI rate limit if set.
"""

DB = Path('data/semantics.db')
TTL = timedelta(days=30)
SCHEMA = """
CREATE TABLE IF NOT EXISTS source (
    id TEXT PRIMARY KEY, label TEXT, authority TEXT, url TEXT, licence TEXT,
    kind TEXT, version TEXT, fetched_at TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS scheme (
    id TEXT PRIMARY KEY, label TEXT, source_id TEXT NOT NULL,
    authority_kind TEXT, syntax TEXT, check_algo TEXT, example TEXT,
    resolver TEXT, status TEXT
);
CREATE TABLE IF NOT EXISTS term (
    id TEXT, label TEXT, definition TEXT, source_id TEXT NOT NULL, iri TEXT,
    kind TEXT, extra TEXT, PRIMARY KEY (source_id, id)
);
CREATE TABLE IF NOT EXISTS lookup (
    scheme TEXT, value TEXT, payload TEXT, source_id TEXT NOT NULL,
    fetched_at TEXT, PRIMARY KEY (scheme, value, source_id)
);
"""

FIBO = 'https://raw.githubusercontent.com/edmcouncil/fibo'
FIBO_TREE = 'https://api.github.com/repos/edmcouncil/fibo/git/trees/master'
FIX = (
    'https://raw.githubusercontent.com/FIXTradingCommunity/orchestrations/'
    'master/FIX%20Standard/OrchestraFIXLatest.xml'
)
MIC = 'https://www.iso20022.org/sites/default/files/ISO10383_MIC/'
CCY = (
    'https://www.six-group.com/dam/download/financial-information/'
    'data-center/iso-currrency/lists/list-one.xml'
)
EUROVOC = 'https://publications.europa.eu/webapi/rdf/sparql'
QL_DOCS = 'https://quantlib-python-docs.readthedocs.io/en/latest'
FIRDS = 'https://registers.esma.europa.eu/solr/esma_registers_firds/select'
GLEIF = 'https://api.gleif.org/api/v1/lei-records'
OPENFIGI = 'https://api.openfigi.com/v3/mapping'

RDF = '{http://www.w3.org/1999/02/22-rdf-syntax-ns#}'
RDFS = '{http://www.w3.org/2000/01/rdf-schema#}'
SKOS = '{http://www.w3.org/2004/02/skos/core#}'
OWL = '{http://www.w3.org/2002/07/owl#}'
DSG = '{https://www.omg.org/spec/Commons/Designators/}'
FIXR = '{http://fixprotocol.io/2020/orchestra/repository}'
SCHEME_ROOT = re.compile(
    r'https://www\.omg\.org/spec/Commons/.*(Scheme|CodeSet)$'
)
PYLIBS = ('skfolio', 'quantstats')

EUROVOC_TERMS = """
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?c ?l (COALESCE(SAMPLE(?def), SAMPLE(?note)) AS ?d) WHERE {
  ?c skos:inScheme <http://eurovoc.europa.eu/100141> ; skos:prefLabel ?l
  FILTER(lang(?l) = 'en')
  OPTIONAL { ?c skos:definition ?def FILTER(lang(?def) = 'en') }
  OPTIONAL { ?c skos:scopeNote ?note FILTER(lang(?note) = 'en') }
} GROUP BY ?c ?l
"""
EUROVOC_VERSION = """
SELECT ?v WHERE {
  <http://eurovoc.europa.eu/100141>
  <http://www.w3.org/2002/07/owl#versionInfo> ?v
}
"""

# fmt: off
META_COLUMNS = ('kind', 'licence', 'authority', 'label', 'url')
META = {
    id: dict(zip(META_COLUMNS, fields))
    for id, *fields in (
        ('fibo', 'ontology', 'MIT', 'EDM Council',
         'Financial Industry Business Ontology',
         'https://github.com/edmcouncil/fibo'),
        ('fibo-actus', 'ontology', 'MIT',
         'EDM Council, ACTUS Financial Research Foundation',
         'FIBO ACTUS module (contract types and terms)',
         'https://github.com/edmcouncil/fibo/tree/master/ACTUS'),
        ('fix', 'codelist', 'free (FIX Trading Community)',
         'FIX Trading Community', 'FIX Latest Orchestra repository', FIX),
        ('mic', 'codelist', 'free from SWIFT',
         'ISO, SWIFT as registration authority',
         'ISO 10383 market identifier codes', MIC),
        ('ccy', 'codelist', 'free from SIX', 'ISO, SIX as maintenance agency',
         'ISO 4217 currency codes', CCY),
        ('builtin', 'codelist', 'n/a', 'this tool',
         'schemes no external source declares', None),
        ('eurovoc', 'ontology', 'free, EU Publications Office',
         'EU Publications Office', 'EuroVoc thesaurus (English labels)',
         EUROVOC),
        ('quantlib-docs', 'library', 'undetermined', 'community project',
         'QuantLib-Python-Docs', QL_DOCS),
        ('pylib', 'library',
         'per library (skfolio BSD-3-Clause, quantstats Apache-2.0)',
         'library authors', 'skfolio and quantstats docstrings', None),
        ('firds', 'registry', 'free EU open data', 'ESMA',
         'Financial Instruments Reference Data System', FIRDS),
        ('gleif', 'registry', 'CC0', 'GLEIF', 'LEI records', GLEIF),
        ('openfigi', 'registry', 'free API',
         'Bloomberg as FIGI registration authority', 'OpenFIGI mapping API',
         OPENFIGI),
    )
}
# fmt: on
NOTES = {
    'quantlib-docs': 'unofficial community project; covers what its authors '
    'wrote, not all of QuantLib; entries without prose are not indexed',
    'pylib': 'first docstring paragraph; undocumented members not indexed',
    'firds': 'CFI codes are returned undecoded: the ISO 10962 table is '
    'paywalled and FIBO decodes only an equity subset',
}

# fmt: off
SCHEME_COLUMNS = (
    'id', 'authority_kind', 'syntax', 'check_algo', 'example', 'resolver'
)
KNOWN_SCHEMES = {
    fibo_name: dict(zip(SCHEME_COLUMNS, fields))
    for fibo_name, *fields in (
        ('InternationalSecuritiesIdentificationNumberingScheme', 'isin', 'iso',
         r'[A-Z]{2}[A-Z0-9]{9}[0-9]', 'luhn_alnum', 'IE00B4L5Y983', 'firds'),
        ('LegalEntityIdentifierScheme', 'lei', 'iso', r'[A-Z0-9]{18}[0-9]{2}',
         'iso7064_97_10', '549300QS4Q1IT6XCA514', 'gleif'),
        ('FinancialInstrumentGlobalIdentifierScheme', 'figi', 'registry',
         r'[B-DF-HJ-NP-TV-Z]{2}G[B-DF-HJ-NP-TV-Z0-9]{8}[0-9]', 'figi',
         'BBG000BLNNH6', 'openfigi'),
        ('BusinessIdentifierCodeScheme', 'bic', 'iso',
         r'[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?', None, 'DEUTDEFF', None),
        ('MICCodeScheme', 'mic', 'iso', r'[A-Z0-9]{4}', 'codelist', 'XETR',
         'mic'),
        ('ISO4217-CodeSet', 'ccy', 'iso', r'[A-Z]{3}', 'codelist', 'EUR',
         'ccy'),
    )
}
# fmt: on

ACCEPTS = {
    'firds': {'isin'},
    'gleif': {'lei'},
    'openfigi': {'isin', 'figi', 'vendor'},
    'mic': {'mic'},
    'ccy': {'ccy'},
}
FIGI_ID_TYPES = {'isin': 'ID_ISIN', 'figi': 'ID_BB_GLOBAL', 'vendor': 'TICKER'}
REGISTRY_VERSIONS = {'firds': 'solr', 'gleif': 'api v1', 'openfigi': 'api v3'}


class Status(enum.StrEnum):
    CONCEPT_ONLY = 'concept-only'
    SYNTAX_VALIDATED = 'syntax-validated'
    RESOLVABLE = 'resolvable'


class AuthorityKind(enum.StrEnum):
    ISO = 'iso'
    REGISTRY = 'registry'
    PROTOCOL = 'protocol'
    VENDOR = 'vendor'


app = typer.Typer(
    help=HELP,
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode='markdown',
    context_settings={'help_option_names': ['-h', '--help']},
)
JsonOption = Annotated[bool, typer.Option('--json', help='Print JSON.')]


def fail(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


def now() -> str:
    return datetime.now(UTC).isoformat()


def get(url: str, **kwargs: Any) -> requests.Response:
    response = requests.get(url, timeout=120, **kwargs)
    response.raise_for_status()
    return response


def term(
    id: str, label: str, definition: str, iri: str | None, kind: str, **extra
) -> dict:
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    row = dict(id=id, label=label, definition=definition, iri=iri, kind=kind)
    return row | dict(extra=extra_json)


def scheme(label: str, **fields: str | None) -> dict:
    row = dict.fromkeys(SCHEME_COLUMNS) | fields | dict(label=label)
    match row:
        case {'resolver': str()}:
            status = Status.RESOLVABLE
        case {'syntax': str()}:
            status = Status.SYNTAX_VALIDATED
        case _:
            status = Status.CONCEPT_ONLY
    return row | dict(status=str(status))


def fibo_files(actus: bool) -> tuple[str, list[bytes]]:
    tree = get(FIBO_TREE, params=dict(recursive=1)).json()
    paths = [
        path
        for path in (node['path'] for node in tree['tree'])
        if path.endswith('.rdf')
        and '/' in path
        and path.split('/')[0] not in ('etc', 'EXMP')
        and not path.rsplit('/', 1)[-1].startswith('Metadata')
        and path.startswith('ACTUS/') == actus
    ]
    with ThreadPoolExecutor(16) as pool:
        files = pool.map(lambda p: get(f'{FIBO}/{tree["sha"]}/{p}'), paths)
        return tree['sha'], [response.content for response in files]


def rdf_resources(files: list[bytes]) -> list[dict]:
    resources = []
    for data in files:
        for element in ET.fromstring(data):
            iri = element.get(f'{RDF}about')
            label = element.findtext(f'{DSG}hasTextualName') or (
                element.findtext(f'{RDFS}label')
            )
            if not iri or not label or element.tag == f'{OWL}Ontology':
                continue
            definition = element.findtext(f'{SKOS}definition') or (
                element.findtext(f'{DSG}hasDescription') or ''
            )
            individual = element.tag == f'{OWL}NamedIndividual'
            parents = {
                child.get(f'{RDF}resource')
                for child in element
                if child.tag in (f'{RDFS}subClassOf', f'{RDF}type')
            }
            resources.append(
                dict(
                    iri=iri,
                    label=label.strip(),
                    definition=' '.join(definition.split()),
                    kind='code' if individual else 'concept',
                    parents=parents,
                    tag=element.findtext(f'{DSG}hasTag'),
                )
            )
    return resources


def fibo_schemes(resources: list[dict]) -> list[dict]:
    parents = {p for r in resources for p in r['parents'] if p}
    roots = {p for p in parents if SCHEME_ROOT.match(p)}
    members, added = set(roots), True
    while added:
        new = {
            r['iri']
            for r in resources
            if r['iri'] not in members and members & r['parents']
        }
        members |= new
        added = bool(new)
    schemes = {}
    for r in resources:
        if r['iri'] in members - roots:
            name = r['iri'].rsplit('/', 1)[-1]
            iso = 'ISO' in r['label'] + r['definition']
            fields = dict(id=name, authority_kind='iso' if iso else 'registry')
            fields |= KNOWN_SCHEMES.get(name, {})
            schemes.setdefault(fields['id'], scheme(r['label'], **fields))
    return list(schemes.values())


def fibo_terms(resources: list[dict]) -> list[dict]:
    return [
        term(
            r['iri'].split('/ontology/')[-1],
            r['label'],
            r['definition'],
            r['iri'],
            r['kind'],
            **({'tag': r['tag']} if r['tag'] else {}),
        )
        for r in resources
    ]


def fetch_fibo() -> dict:
    version, files = fibo_files(actus=False)
    resources = rdf_resources(files)
    return dict(
        version=version,
        terms=fibo_terms(resources),
        schemes=fibo_schemes(resources),
    )


def fetch_fibo_actus() -> dict:
    version, files = fibo_files(actus=True)
    return dict(version=version, terms=fibo_terms(rdf_resources(files)))


def fix_documentation(element: ET.Element) -> str:
    return ' '.join(
        ' '.join((doc.text or '').split())
        for doc in element.iter(f'{FIXR}documentation')
        if doc.get('purpose') in ('SYNOPSIS', 'ELABORATION')
    )


def fetch_fix() -> dict:
    root = ET.fromstring(get(FIX).content)
    terms = [
        term(
            f'{field.get("name")}({field.get("id")})',
            field.get('name', ''),
            fix_documentation(field),
            None,
            'concept',
            tag=field.get('id'),
            type=field.get('type'),
        )
        for field in root.iter(f'{FIXR}field')
    ]
    for code_set in root.iter(f'{FIXR}codeSet'):
        field = code_set.get('name', '').removesuffix('CodeSet')
        terms += [
            term(
                f'{field}={code.get("value")}',
                code.get('name', ''),
                fix_documentation(code),
                None,
                'code',
                field=field,
                tag=code_set.get('id'),
                value=code.get('value'),
                deprecated=code.get('deprecated'),
            )
            for code in code_set.iter(f'{FIXR}code')
        ]
    return dict(version=root.get('version'), terms=terms)


def fetch_mic() -> dict:
    response = get(f'{MIC}ISO10383_MIC.csv')
    text = response.content.decode('utf-8-sig')
    terms = [
        term(
            row['MIC'],
            row['MIC'],
            f'{row["MARKET NAME-INSTITUTION DESCRIPTION"]} ({row["CITY"]}, '
            f'{row["ISO COUNTRY CODE (ISO 3166)"]}), {row["STATUS"].lower()}',
            None,
            'code',
            **{key.lower(): value for key, value in row.items() if value},
        )
        for row in csv.DictReader(io.StringIO(text))
    ]
    return dict(version=response.headers.get('Last-Modified'), terms=terms)


def fetch_ccy() -> dict:
    root = ET.fromstring(get(CCY).content)
    codes: dict[str, dict] = {}
    for entry in root.iter('CcyNtry'):
        if code := entry.findtext('Ccy'):
            info = codes.setdefault(code, dict(countries=[]))
            info['countries'].append(entry.findtext('CtryNm'))
            info |= dict(
                name=entry.findtext('CcyNm'),
                number=entry.findtext('CcyNbr'),
                minor_units=entry.findtext('CcyMnrUnts'),
            )
    terms = [
        term(code, code, info['name'], None, 'code', **info)
        for code, info in codes.items()
    ]
    return dict(version=root.get('Pblshd'), terms=terms)


def fetch_builtin() -> dict:
    vendor = scheme(
        'vendor, broker or exchange ticker symbol (no standard)',
        id='vendor',
        authority_kind='vendor',
        example='QCI.DE',
        resolver='openfigi',
    )
    return dict(version='1', schemes=[vendor])


def sparql(query: str) -> list[dict]:
    headers = {'Accept': 'text/csv'}
    response = get(EUROVOC, params=dict(query=query), headers=headers)
    return list(csv.DictReader(io.StringIO(response.text)))


def fetch_eurovoc() -> dict:
    terms = [
        term(row['c'].rsplit('/')[-1], row['l'], row['d'], row['c'], 'concept')
        for row in sparql(EUROVOC_TERMS)
    ]
    return dict(version=sparql(EUROVOC_VERSION)[0]['v'], terms=terms)


def rst_paragraph(lines: list[str], indent: int) -> str:
    paragraph = []
    for line in lines:
        stripped = line.strip()
        if not stripped and paragraph:
            break
        if not stripped:
            continue
        if len(line) - len(line.lstrip()) < indent:
            break
        if stripped.startswith(('..', ':')):
            break
        paragraph.append(stripped)
    return ' '.join(paragraph)


def rst_terms(text: str, page: str, anchors: dict) -> Iterator[dict]:
    underline = re.compile(r'([#*=\-~^"])\1{2,}\s*$')
    directive = re.compile(
        r'(\s*)\.\. (class|function|method):: (?:ql\.)?(\w+)'
    )
    lines = text.splitlines() + ['']
    heading, heading_prose, owner = '', '', None
    for i, line in enumerate(lines[:-1]):
        if underline.match(lines[i + 1]) and not underline.match(line):
            if line.strip():
                heading, owner = line.strip(), None
                heading_prose = rst_paragraph(lines[i + 2 :], 0)
                continue
        if not (match := directive.match(line)):
            continue
        indent, kind, name = len(match[1]), match[2], match[3]
        if kind == 'class':
            owner = name
        if kind == 'method':
            name = f'{owner or heading}.{name}'
        prose = rst_paragraph(lines[i + 1 :], indent + 1)
        if not prose and name == heading:
            prose = heading_prose
        if prose:
            iri = anchors.get(name, page)
            yield term(f'ql.{name}', name, prose, iri, 'function')


def fetch_quantlib_docs() -> dict:
    parts = get(f'{QL_DOCS}/objects.inv').content.split(b'\n', 4)
    lines = zlib.decompress(parts[4]).decode().splitlines()
    inventory = [line.split(' ', 4) for line in lines]
    anchors = {
        name.removeprefix('ql.'): f'{QL_DOCS}/{uri.replace("$", name)}'
        for name, role, _, uri, _ in inventory
        if role.startswith('py:')
    }
    docs = [
        name
        for name, role, *_ in inventory
        if role == 'std:doc'
        and name != 'index'
        and not name.startswith(('examples/', 'getting_started/'))
    ]
    with ThreadPoolExecutor(8) as pool:
        sources = pool.map(
            lambda doc: get(f'{QL_DOCS}/_sources/{doc}.rst.txt'), docs
        )
        texts = [response.text for response in sources]
    terms: dict[str, dict] = {}
    for doc, text in zip(docs, texts):
        for t in rst_terms(text, f'{QL_DOCS}/{doc}.html', anchors):
            terms.setdefault(t['id'], t)
    version = parts[2].decode().removeprefix('# Version: ').strip()
    return dict(version=version, terms=list(terms.values()))


def signature(obj: Any) -> str | None:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return None


def introspect(package: str) -> Iterator[dict]:
    root = importlib.import_module(package)
    modules = [package] + [
        info.name
        for info in pkgutil.walk_packages(root.__path__, f'{package}.')
        if '._' not in info.name and '.tests' not in info.name
    ]
    seen = set()
    for module_name in modules:
        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(
            module, lambda o: inspect.isfunction(o) or inspect.isclass(o)
        ):
            origin = (getattr(obj, '__module__', ''), obj.__qualname__)
            if name.startswith('_') or origin in seen:
                continue
            if not origin[0].startswith(package):
                continue
            seen.add(origin)
            doc = (inspect.getdoc(obj) or '').split('\n\n')[0]
            if doc.strip():
                yield term(
                    f'{module_name}.{name}',
                    name,
                    ' '.join(doc.split()),
                    None,
                    'function',
                    signature=signature(obj),
                )


def fetch_pylib() -> dict:
    version = ', '.join(
        f'{lib} {importlib.metadata.version(lib)}' for lib in PYLIBS
    )
    terms = [t for lib in PYLIBS for t in introspect(lib)]
    return dict(version=version, terms=terms)


SOURCES: dict[str, Callable[[], dict]] = {
    'fibo': fetch_fibo,
    'fibo-actus': fetch_fibo_actus,
    'fix': fetch_fix,
    'mic': fetch_mic,
    'ccy': fetch_ccy,
    'builtin': fetch_builtin,
    'eurovoc': fetch_eurovoc,
    'quantlib-docs': fetch_quantlib_docs,
    'pylib': fetch_pylib,
}
VOCABULARIES = [source for source in SOURCES if source != 'builtin']


def normalise(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = lambda cursor, row: {
        column[0]: value for column, value in zip(cursor.description, row)
    }
    con.create_function('normalise', 1, normalise, deterministic=True)
    con.executescript(SCHEMA)
    return con


def insert(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    for row in rows:
        columns = ', '.join(row)
        values = ', '.join(f':{column}' for column in row)
        con.execute(
            f'INSERT OR REPLACE INTO {table} ({columns}) VALUES ({values})',
            row,
        )


def store_source(con: sqlite3.Connection, id: str, version: str) -> None:
    row = META[id] | dict(id=id, version=version, fetched_at=now())
    insert(con, 'source', [row | dict(note=NOTES.get(id))])


def ensure(con: sqlite3.Connection, *ids: str) -> None:
    cached = {row['id'] for row in con.execute('SELECT id FROM source')}
    for id in (id for id in ids if id not in cached):
        typer.echo(f'fetching {id}', err=True)
        data = SOURCES[id]()
        store_source(con, id, data['version'])
        for table in ('term', 'scheme'):
            rows = data.get(f'{table}s', [])
            insert(con, table, [row | dict(source_id=id) for row in rows])
        con.commit()


def clear(con: sqlite3.Connection, ids: list[str]) -> None:
    for id in ids:
        for table in ('term', 'scheme', 'lookup'):
            con.execute(f'DELETE FROM {table} WHERE source_id = ?', (id,))
        con.execute('DELETE FROM source WHERE id = ?', (id,))
    con.commit()


def emit(rows: list[dict], as_json: bool, empty: str) -> None:
    if as_json:
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if not rows:
        raise fail(empty)
    cells = [
        {
            key: json.dumps(value, ensure_ascii=False)
            if isinstance(value, dict | list)
            else value
            for key, value in row.items()
        }
        for row in rows
    ]
    table = tabulate(
        cells, headers='keys', maxcolwidths=60, disable_numparse=True
    )
    typer.echo(table)


def alphanumeric_digits(value: str) -> str:
    return ''.join(str(int(char, 36)) for char in value)


def digit_sum(value: int) -> int:
    return sum(divmod(value, 10))


def luhn_alnum(value: str) -> bool:
    digits = reversed(alphanumeric_digits(value))
    total = sum(digit_sum(int(d) * (1 + i % 2)) for i, d in enumerate(digits))
    return total % 10 == 0


def iso7064_97_10(value: str) -> bool:
    return int(alphanumeric_digits(value)) % 97 == 1


def figi_check(value: str) -> bool:
    payload = enumerate(value[:11])
    total = sum(digit_sum(int(c, 36) * (1 + i % 2)) for i, c in payload)
    return (10 - total % 10) % 10 == int(value[11])


CHECKS: dict[str, Callable[[str], bool]] = {
    'luhn_alnum': luhn_alnum,
    'iso7064_97_10': iso7064_97_10,
    'figi': figi_check,
}


def passes_check(con: sqlite3.Connection, row: dict, value: str) -> bool:
    match row['check_algo']:
        case None:
            return True
        case 'codelist':
            ensure(con, row['scheme'])
            return bool(
                con.execute(
                    'SELECT 1 FROM term WHERE source_id = ? AND label = ?',
                    (row['scheme'], value),
                ).fetchone()
            )
        case algo:
            return CHECKS[algo](value)


def candidates(con: sqlite3.Connection, value: str) -> list[dict]:
    ensure(con, 'fibo', 'builtin')
    rows = con.execute(
        'SELECT scheme.id AS scheme, scheme.label, authority_kind, syntax, '
        'check_algo, status, resolver, source_id AS source, version '
        'FROM scheme JOIN source ON source.id = scheme.source_id '
        "WHERE syntax IS NOT NULL OR scheme.id = 'vendor' "
        'ORDER BY check_algo IS NULL, scheme.id'
    ).fetchall()
    matches = [
        row
        for row in rows
        if row['syntax'] and re.fullmatch(row['syntax'], value)
        if passes_check(con, row, value)
    ]
    vendor = [row for row in rows if row['scheme'] == 'vendor']
    return [
        {key: row[key] for key in row if key != 'syntax'}
        | dict(
            check=f'{row["check_algo"]} passed'
            if row['check_algo']
            else 'none'
        )
        for row in matches or vendor
    ]


def gleif_record(lei: str, relation: str = '') -> dict | None:
    response = requests.get(f'{GLEIF}/{lei}{relation}', timeout=60)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    attributes = response.json()['data']['attributes']
    entity = attributes['entity']
    return dict(
        lei=attributes['lei'],
        name=entity['legalName']['name'],
        country=entity['legalAddress']['country'],
        jurisdiction=entity['jurisdiction'],
        legal_form=entity['legalForm']['id'],
        entity_status=entity['status'],
        registration_status=attributes['registration']['status'],
    )


def resolve_gleif(value: str, scheme_id: str) -> Any:
    record = gleif_record(value)
    return record and record | {
        relation.replace('-', '_'): gleif_record(value, f'/{relation}')
        for relation in ('direct-parent', 'ultimate-parent')
    }


def resolve_firds(value: str, scheme_id: str) -> Any:
    query = f'isin:{value} AND type_s:parent AND latest_received_flag:1'
    params = dict(q=query, wt='json', rows=1000)
    docs = get(FIRDS, params=params).json()['response']['docs']
    if not docs:
        return None
    venues: dict[bool, set] = {True: set(), False: set()}
    for doc in docs:
        venues[bool(doc.get('mrkt_trdng_trmination_date'))].add(doc['mic'])
    first = docs[0]
    return dict(
        isin=value,
        name=first.get('gnr_full_name'),
        short_name=first.get('gnr_short_name'),
        cfi=first.get('gnr_cfi_code'),
        issuer_lei=first.get('lei'),
        currency=first.get('gnr_notional_curr_code'),
        competent_authority_mic=first.get('rca_mic'),
        venues=sorted(venues[False]),
        terminated_venues=sorted(venues[True]),
    )


def resolve_openfigi(value: str, scheme_id: str) -> Any:
    key = os.environ.get('OPENFIGI_API_KEY')
    response = requests.post(
        OPENFIGI,
        json=[dict(idType=FIGI_ID_TYPES[scheme_id], idValue=value)],
        headers={'X-OPENFIGI-APIKEY': key} if key else {},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()[0].get('data')


REGISTRIES: dict[str, Callable[[str, str], Any]] = {
    'firds': resolve_firds,
    'gleif': resolve_gleif,
    'openfigi': resolve_openfigi,
}


def lookup(
    con: sqlite3.Connection, scheme_id: str, value: str, registry: str
) -> dict:
    expiry = (datetime.now(UTC) - TTL).isoformat()
    row = con.execute(
        'SELECT payload, fetched_at FROM lookup WHERE scheme = ? '
        'AND value = ? AND source_id = ? AND fetched_at > ?',
        (scheme_id, value, registry, expiry),
    ).fetchone()
    if row:
        return dict(
            fetched_at=row['fetched_at'], payload=json.loads(row['payload'])
        )
    payload = REGISTRIES[registry](value, scheme_id)
    store_source(con, registry, REGISTRY_VERSIONS[registry])
    row = dict(scheme=scheme_id, value=value, source_id=registry)
    row |= dict(payload=json.dumps(payload), fetched_at=now())
    insert(con, 'lookup', [row])
    con.commit()
    return dict(fetched_at=row['fetched_at'], payload=payload)


def codelist_lookup(con: sqlite3.Connection, source: str, value: str) -> dict:
    rows = con.execute(
        'SELECT label, definition, extra FROM term '
        'WHERE source_id = ? AND label = ?',
        (source, value),
    ).fetchall()
    payload = [
        row | dict(extra=json.loads(row['extra'] or 'null')) for row in rows
    ]
    return dict(fetched_at=None, payload=payload)


@app.callback(invoke_without_command=True)
def main(
    refresh: Annotated[
        str | None,
        typer.Option(
            metavar='SOURCE',
            help='Redownload and reindex SOURCE, or clear the cached answers '
            'of a registry; `all` for every source.',
        ),
    ] = None,
) -> None:
    if refresh is None:
        return
    known = [*SOURCES, *REGISTRIES]
    if refresh != 'all' and refresh not in known:
        raise fail(f'unknown source {refresh}, one of: {", ".join(known)}')
    ids = known if refresh == 'all' else [refresh]
    con = connect()
    clear(con, ids)
    ensure(con, *[id for id in ids if id in SOURCES])


@app.command()
def sources(as_json: JsonOption = False) -> None:
    """List every source with licence, version, fetch date and row counts."""
    con = connect()
    counts = ', '.join(
        f'(SELECT COUNT(*) FROM {table} WHERE source_id = source.id) {table}s'
        for table in ('term', 'scheme', 'lookup')
    )
    cached = {
        row['id']: row
        for row in con.execute(
            f'SELECT id, version, fetched_at, {counts} FROM source'
        )
    }
    rows = [
        dict(id=id, kind=meta['kind'], licence=meta['licence'])
        | cached.get(id, dict(version='not cached'))
        | dict(note=NOTES.get(id))
        for id, meta in META.items()
    ]
    emit(rows, as_json, 'no sources')


@app.command()
def schemes(
    status: Annotated[
        Status | None, typer.Option(help='Only schemes of this status.')
    ] = None,
    authority_kind: Annotated[
        AuthorityKind | None,
        typer.Option(help='Only schemes of this authority kind.'),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """List identifier schemes discovered in FIBO plus the built-ins."""
    con = connect()
    ensure(con, 'fibo', 'builtin')
    rows = con.execute(
        'SELECT scheme.*, source.version FROM scheme '
        'JOIN source ON source.id = scheme.source_id '
        'WHERE (:status IS NULL OR status = :status) '
        'AND (:kind IS NULL OR authority_kind = :kind) '
        'ORDER BY status DESC, scheme.id',
        dict(status=status, kind=authority_kind),
    ).fetchall()
    emit(rows, as_json, 'no scheme matches')


@app.command()
def identify(value: str, as_json: JsonOption = False) -> None:
    """Infer candidate schemes of VALUE from syntax and check digits."""
    emit(candidates(connect(), value.strip()), as_json, 'no candidate')


@app.command()
def resolve(
    value: str,
    to: Annotated[
        str | None,
        typer.Option(
            metavar='SCHEME', help='Use the resolver of this scheme.'
        ),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """Ask a registry or code list what VALUE denotes."""
    con = connect()
    found = candidates(con, value := value.strip())
    targets = found
    if to:
        targets = con.execute(
            'SELECT id AS scheme, resolver, status FROM scheme WHERE id = ?',
            (to,),
        ).fetchall()
        if not targets:
            raise fail(f'unknown scheme {to}, see `schemes`')
    resolver = next(
        (row['resolver'] for row in targets if row['resolver']), None
    )
    if resolver is None:
        names = ', '.join(
            f'{row["scheme"]} ({row["status"]})' for row in targets
        )
        raise fail(f'no resolver for {names}, see `schemes`')
    accepted = [
        row['scheme'] for row in found if row['scheme'] in ACCEPTS[resolver]
    ]
    if not accepted:
        wanted = ', '.join(sorted(ACCEPTS[resolver]))
        names = ', '.join(row['scheme'] for row in found)
        raise fail(f'{resolver} resolves {wanted}, not {names}')
    if resolver in SOURCES:
        answer = codelist_lookup(con, resolver, value)
    else:
        answer = lookup(con, accepted[0], value, resolver)
    version = con.execute(
        'SELECT version FROM source WHERE id = ?', (resolver,)
    ).fetchone()['version']
    row = dict(
        value=value, scheme=accepted[0], source=resolver, version=version
    )
    emit([row | answer], as_json, 'not found')


@app.command('term')
def term_command(
    label: str,
    source: Annotated[
        list[str] | None, typer.Option(help='Only this source (repeatable).')
    ] = None,
    limit: Annotated[int, typer.Option(help='Maximum rows.')] = 20,
    as_json: JsonOption = False,
) -> None:
    """Definitions whose label contains LABEL, with source and IRI."""
    ids = source or VOCABULARIES
    if unknown := set(ids) - set(VOCABULARIES):
        raise fail(f'unknown source {", ".join(sorted(unknown))}')
    con = connect()
    ensure(con, *ids)
    key = normalise(label)
    rows = con.execute(
        'SELECT term.label, definition, source_id AS source, version, term.kind, '
        'term.id, iri, extra FROM term '
        'JOIN source ON source.id = term.source_id '
        f'WHERE source_id IN ({", ".join("?" * len(ids))}) '
        'AND normalise(term.label) LIKE ? '
        'ORDER BY normalise(term.label) != ?, '
        "definition = '', length(term.label) LIMIT ?",
        (*ids, f'%{key}%', key, limit),
    ).fetchall()
    for row in rows:
        extra = row.pop('extra')
        if as_json:
            row['extra'] = json.loads(extra) if extra else None
    emit(rows, as_json, f'no term label contains {label!r}')
