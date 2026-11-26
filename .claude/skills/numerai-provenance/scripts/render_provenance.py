"""Render a model provenance diagram from a JSON spec to a PNG.

The spec format is documented in the numerai-provenance SKILL.md (section "Spec").
The spec holds model details: keep it outside git, like the rendered image.

Usage: python render_provenance.py SPEC.json OUT.png
"""

import argparse
import json
import textwrap
from typing import Any

import matplotlib

matplotlib.use('Agg')

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

WIDTH = 3.6
WRAP = 47
ADVANCE = 0.165
GAP = 0.07
PADDING = 0.12
MARGIN = 1.0

BOX_STYLES: dict[str, dict[str, Any]] = {
    'root': dict(
        facecolor='#fde2e1', edgecolor='#b42318', linestyle='-', linewidth=2.2
    ),
    'deployed': dict(
        facecolor='#dcf3e4', edgecolor='#1a7f4b', linestyle='-', linewidth=2.0
    ),
    'training': dict(
        facecolor='#fff1d6', edgecolor='#c76b00', linestyle='--', linewidth=2.0
    ),
    'path': dict(
        facecolor='#f2f2f2', edgecolor='#8a8a8a', linestyle=':', linewidth=1.2
    ),
    'callout': dict(
        facecolor='#fff9c4', edgecolor='#9a7d00', linestyle='-', linewidth=1.2
    ),
}

EDGE_STYLES = {
    'parent': dict(color='#444444', linestyle='-', linewidth=1.4, rad=0.0),
    'variant': dict(
        color='#b42318', linestyle=(0, (4, 3)), linewidth=1.2, rad=0.15
    ),
    'borrow': dict(
        color='#5b4bc4', linestyle=(0, (2, 2)), linewidth=1.3, rad=0.12
    ),
}

SECTION_STYLES = {
    'title': dict(
        fontsize=8.0, fontweight='bold', family='monospace', color='black'
    ),
    'body': dict(fontsize=7.6, color='black'),
    'metric': dict(fontsize=7.6, color='#1f4fa8', fontstyle='italic'),
    'ensemble': dict(fontsize=7.6, color='#7a3e00'),
}

LEGEND_BOXES = [
    ('root', 'root model (no parent in the notes)'),
    (
        'deployed',
        'registered on Numerai (prefix + timestamp), pickle in workspace/models',
    ),
    ('training', 'being trained (script on disk, no pickle yet)'),
    ('path', 'intermediate experiments, collapsed (not registered)'),
]

LEGEND_EDGES = [
    (
        'variant',
        'described as a variant ("as X but ...") without a parent= link',
    ),
    ('borrow', 'design ported across branches'),
    ('parent', 'parent -> child (parent= field of the model note)'),
]


def load_spec(path):
    with open(path) as handle:
        return json.load(handle)


def node_sections(node):
    sections = [('title', [node['title']])]
    for key, prefix in (
        ('body', ''),
        ('metric', 'metric: '),
        ('ensemble', 'ensemble: '),
    ):
        if node.get(key):
            sections.append((key, textwrap.wrap(prefix + node[key], WRAP)))
    return sections


def sections_height(sections):
    lines = sum(len(lines) for _, lines in sections)
    return lines * ADVANCE + (len(sections) - 1) * GAP + 2 * PADDING


def box_height(node):
    return sections_height(node_sections(node))


def draw_box(ax, x, y, height, kind):
    ax.add_patch(
        FancyBboxPatch(
            (x - WIDTH / 2, y - height / 2),
            WIDTH,
            height,
            boxstyle='round,pad=0.04,rounding_size=0.08',
            zorder=3,
            **BOX_STYLES[kind],
        )
    )


def draw_sections(ax, x, y, height, sections):
    cursor = y + height / 2 - PADDING
    for key, lines in sections:
        ax.text(
            x,
            cursor,
            '\n'.join(lines),
            ha='center',
            va='top',
            linespacing=1.25,
            zorder=4,
            **SECTION_STYLES[key],
        )
        cursor -= len(lines) * ADVANCE + GAP


def draw_node(ax, node):
    sections = node_sections(node)
    height = sections_height(sections)
    draw_box(ax, node['x'], node['y'], height, node['kind'])
    draw_sections(ax, node['x'], node['y'], height, sections)


def anchor(node, side):
    half = box_height(node) / 2 + 0.04
    return (
        (node['x'], node['y'] - half)
        if side == 'bottom'
        else (node['x'], node['y'] + half)
    )


def draw_edge(ax, nodes, edge):
    source, target, kind = nodes[edge[0]], nodes[edge[1]], edge[2]
    style = dict(EDGE_STYLES[kind])
    same_row = abs(source['y'] - target['y']) < 0.5
    start = anchor(source, 'top' if same_row else 'bottom')
    end = anchor(target, 'top')
    ax.annotate(
        '',
        xy=end,
        xytext=start,
        zorder=2,
        arrowprops=dict(
            arrowstyle='-|>',
            color=style['color'],
            linestyle=style['linestyle'],
            lw=style['linewidth'],
            connectionstyle=f'arc3,rad={style["rad"]}',
            shrinkA=0,
            shrinkB=0,
            mutation_scale=12,
        ),
    )


def draw_callout(ax, nodes, callout):
    sections = [
        ('title', [callout['title']]),
        ('body', textwrap.wrap(callout['body'], WRAP)),
    ]
    height = sections_height(sections)
    draw_box(ax, callout['x'], callout['y'], height, 'callout')
    draw_sections(ax, callout['x'], callout['y'], height, sections)
    node = nodes[callout['node']]
    side = 1 if callout['x'] > node['x'] else -1
    ax.plot(
        [
            node['x'] + side * (WIDTH / 2 + 0.05),
            callout['x'] - side * (WIDTH / 2 + 0.05),
        ],
        [node['y'], callout['y']],
        color='#9a7d00',
        linestyle=(0, (1, 2)),
        linewidth=1.4,
        zorder=2,
    )


def draw_legend_boxes(ax, x, y):
    for index, (kind, label) in enumerate(LEGEND_BOXES):
        row = y - index * 0.42
        ax.add_patch(
            FancyBboxPatch(
                (x, row - 0.13),
                0.45,
                0.26,
                boxstyle='round,pad=0.02',
                **BOX_STYLES[kind],
            )
        )
        ax.text(x + 0.6, row, label, va='center', fontsize=8.5)


def draw_legend_edges(ax, x, y):
    for index, (kind, label) in enumerate(LEGEND_EDGES):
        row = y - (len(LEGEND_BOXES) + index) * 0.42
        style = EDGE_STYLES[kind]
        ax.plot(
            [x, x + 0.45],
            [row, row],
            color=style['color'],
            linestyle=style['linestyle'],
            lw=style['linewidth'],
        )
        ax.text(x + 0.6, row, label, va='center', fontsize=8.5)


def draw_legend_texts(ax, x, y, notes):
    row = y - (len(LEGEND_BOXES) + len(LEGEND_EDGES)) * 0.42 - 0.05
    for key, label in notes:
        style = {
            k: v for k, v in SECTION_STYLES[key].items() if k != 'fontsize'
        }
        ax.text(x, row, label, va='top', fontsize=8.5, **style)
        row -= 0.25 * (label.count('\n') + 1) + 0.12


def draw_legend(ax, legend):
    draw_legend_boxes(ax, legend['x'], legend['y'])
    draw_legend_edges(ax, legend['x'], legend['y'])
    draw_legend_texts(ax, legend['x'], legend['y'], legend.get('notes', []))


def canvas_limits(spec):
    nodes = list(spec['nodes'].values()) + spec.get('callouts', [])
    xs = [node['x'] for node in nodes] + [spec['legend']['x']]
    tops = [node['y'] + 1.0 for node in nodes]
    bottoms = [node['y'] - 1.5 for node in nodes]
    return (
        min(xs) - WIDTH / 2 - MARGIN / 2,
        max(xs) + WIDTH / 2 + MARGIN / 2,
        min(bottoms) - MARGIN,
        max(tops) + 2.4,
    )


def draw_header(ax, spec, left, top):
    ax.text(
        left + 0.2,
        top - 0.35,
        spec['title'],
        fontsize=15,
        fontweight='bold',
        va='center',
    )
    ax.text(
        left + 0.2,
        top - 0.75,
        spec.get('subtitle', ''),
        fontsize=9.5,
        va='center',
        color='#333333',
    )


def render(spec, path):
    left, right, bottom, top = canvas_limits(spec)
    fig, ax = plt.subplots(figsize=(right - left, top - bottom))
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    ax.axis('off')
    for edge in spec['edges']:
        draw_edge(ax, spec['nodes'], edge)
    for node in spec['nodes'].values():
        draw_node(ax, node)
    for callout in spec.get('callouts', []):
        draw_callout(ax, spec['nodes'], callout)
    draw_legend(ax, spec['legend'])
    draw_header(ax, spec, left, top)
    fig.savefig(path, dpi=110, bbox_inches='tight', facecolor='white')


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('spec')
    parser.add_argument('output')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_arguments()
    render(load_spec(arguments.spec), arguments.output)
