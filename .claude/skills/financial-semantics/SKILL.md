---
name: "financial-semantics"
description: "Use before stating what a financial term, order type, instrument class, contract term, identifier or code means, before writing code or prose that names one, and whenever a bare identifier (ISIN, LEI, FIGI, MIC, currency code, ticker) needs to be classified or looked up: queries the financial-semantics CLI instead of answering from memory."
---

# Financial semantics

Definitions, identifier schemes and code lists come from
`uv run financial-semantics`, not from memory. It caches FIBO (with its ACTUS
module), FIX Orchestra, ISO 10383 MIC, ISO 4217, EuroVoc, QuantLib-Python-Docs
and the skfolio and quantstats docstrings, and asks FIRDS, GLEIF and OpenFIGI
about single identifiers. The first call fetches what it needs, which takes a
few seconds.

Which command for which question:

- What does a term mean ("stop limit", "collective investment vehicle",
  "UCITS", "nominal interest rate", "sharpe")?
  `term LABEL`, with `--source fix|fibo|fibo-actus|eurovoc|quantlib-docs|pylib`
  to narrow. The label match ignores case, spaces and punctuation and is a
  substring match, so search for the shortest distinctive words ("stop limit",
  not "stop-limit order").
- What kind of identifier is this string? `identify VALUE`. It works offline.
  A `vendor` result means no standard scheme matched (e.g. `QCI.DE`).
- What does this identifier denote? `resolve VALUE`. ISIN goes to FIRDS (name,
  CFI, issuer LEI, venues), LEI goes to GLEIF (entity, parents), FIGI and
  vendor tickers go to OpenFIGI, and MIC and currency codes are answered from
  the cached code lists. `--to figi` maps an ISIN to its FIGIs.
- Which schemes exist and which can be checked or resolved? `schemes`
  (`--status`, `--authority-kind`).
- What is cached, in which version and under which licence? `sources`.

Add `--json` when the output feeds further processing.

When stating a definition, cite the source and version from the output (e.g.
"FIX OrdType=4 StopLimit, FIX.Latest_EP312"). If sources disagree, show each
row with its source rather than merging them. If nothing matches, say that the
sources have no entry. Do not fill the gap with an invented definition.

The tool does not cover broker vocabulary such as the German Stop-Loss,
Stop-Buy or Trailing Stop. Where a broker term and the matching FIX term
differ, point out the difference when using them. CFI codes from FIRDS are
returned undecoded.
