# app.py  ──  interactive accounting mind-map (parent values auto-calculated)

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import dash
from dash import dcc, html, Input, Output, State
import dash_cytoscape as cyto

#
# ───────────────────────── 1.  DATA MODEL ─────────────────────────
#

LEAF_NODES = {
    # Assets
    "Cash": 10_000,
    "AR": 12_000,
    "Inventory": 8_000,
    "PPE": 40_000,
    "Intangibles": 5_000,
    # Liabilities
    "AP": 7_000,
    "NotesPayable": 6_000,
    "LongTermDebt": 20_000,
    # Income
    "OperatingIncome": 15_000,
    "NonOperatingIncome": 3_000,
    # Expenses
    "COGS": 9_000,
    "SGA": 4_000,
    "Depreciation": 2_000,
    "InterestExp": 1_000,
}

# Parent/child relationships for automatic roll-ups
TREE = {
    # Assets branch
    "CurrentAssets": ["Cash", "AR", "Inventory"],
    "NonCurrentAssets": ["PPE", "Intangibles"],
    "Assets": ["CurrentAssets", "NonCurrentAssets"],
    # Liabilities branch
    "CurrentLiabilities": ["AP", "NotesPayable"],
    "NonCurrentLiabilities": ["LongTermDebt"],
    "Liabilities": ["CurrentLiabilities", "NonCurrentLiabilities"],
    # Income & Expense branch
    "Income": ["OperatingIncome", "NonOperatingIncome"],
    "Expenses": ["COGS", "SGA", "Depreciation", "InterestExp"],
}
ROOTS = ["Assets", "Liabilities", "Income", "Expenses"]

#
# ──────────────────────── 2.  BUILD CYTOSCAPE GRAPH ────────────────────────
#

def make_node(_id, _class):
    return {"data": {"id": _id, "label": _id.replace("_", " ")}, "classes": _class}

def make_edge(src, tgt):
    return {"data": {"source": src, "target": tgt}}

elements = []

# classes for colouring
CLASS_MAP = {
    "Assets": "asset", "CurrentAssets": "asset", "NonCurrentAssets": "asset",
    "Cash": "asset", "AR": "asset", "Inventory": "asset", "PPE": "asset", "Intangibles": "asset",
    "Liabilities": "liability", "CurrentLiabilities": "liability", "NonCurrentLiabilities": "liability",
    "AP": "liability", "NotesPayable": "liability", "LongTermDebt": "liability",
    "Equity": "equity",
    "Income": "income", "OperatingIncome": "income", "NonOperatingIncome": "income",
    "Expenses": "expense", "COGS": "expense", "SGA": "expense", "Depreciation": "expense", "InterestExp": "expense",
    "Equation": "center",
}

# Nodes
all_nodes = set(LEAF_NODES) | set(TREE) | {"Equity", "Equation"}
for nid in all_nodes:
    elements.append(make_node(nid, CLASS_MAP.get(nid, "asset")))

# Edges
for parent, kids in TREE.items():
    for k in kids:
        elements.append(make_edge(parent, k))
# Top-level edges & equation
for top in ROOTS:
    elements.extend([make_edge("Equation", top)])
elements.append(make_edge("Equation", "Equity"))

#
# ───────────────────────── 3.  DASH APP ─────────────────────────
#

app = dash.Dash(__name__)

def slider(nid, value, disabled=False):
    return html.Div(
        style={"marginBottom": "18px"},
        children=[
            html.Label(nid.replace("_", " "), htmlFor=f"slider-{nid}"),
            dcc.Slider(
                id=f"slider-{nid}",
                min=0,
                max=200_000,
                step=1_000,
                value=value,
                disabled=disabled,
                updatemode="drag",
                tooltip={"placement": "bottom"},
                marks={0: "0", 50_000: "50k", 100_000: "100k", 150_000: "150k", 200_000: "200k"},
            ),
        ],
    )

leaf_sliders = [slider(n, v) for n, v in LEAF_NODES.items()]
# computed nodes start at zero; they'll update immediately via callback
computed_nodes = sorted(all_nodes - LEAF_NODES.keys() - {"Equation"})
computed_sliders = [slider(n, 0, disabled=True) for n in computed_nodes]

sidebar = html.Div(
    style={
        "flex": "0 0 320px",
        "minWidth": "320px",
        "maxWidth": "320px",
        "overflowY": "auto",
        "padding": "12px",
        "boxSizing": "border-box",
        "borderRight": "1px solid #ccc",
    },
    children=[html.H3("Adjust leaf values")] + leaf_sliders + [html.H3("Computed totals")] + computed_sliders,
)

graph_panel = html.Div(
    style={"flex": "1", "padding": "10px"},
    children=[
        cyto.Cytoscape(
            id="mindmap",
            elements=elements,
            stylesheet=[
                {
                    "selector": "node",
                    "style": {
                        "label": "data(label)",
                        "font-size": "10px",
                        "text-valign": "center",
                        "text-halign": "center",
                        "width": "50px",
                        "height": "50px",
                    },
                },
                {"selector": ".center", "style": {"background-color": "#8390FA"}},
                {"selector": ".asset", "style": {"background-color": "#7FB069"}},
                {"selector": ".liability", "style": {"background-color": "#F28D35"}},
                {"selector": ".equity", "style": {"background-color": "#6A4C93"}},
                {"selector": ".income", "style": {"background-color": "#4281A4"}},
                {"selector": ".expense", "style": {"background-color": "#D64161"}},
                {"selector": "edge", "style": {"line-color": "#999", "width": 1.5}},
            ],
            layout={
                "name": "breadthfirst",
                "roots": "[id = 'Equation']",
                "spacingFactor": 1.0,
                "avoidOverlap": True,
            },
            style={"width": "100%", "height": "100%", "border": "1px solid #ccc"},
            minZoom=0.5,
            maxZoom=2,
        )
    ],
)

app.layout = html.Div(style={"display": "flex", "height": "100vh"}, children=[sidebar, graph_panel])

#
# ───────────────────────── 4.  CALLBACKS ─────────────────────────
#

leaf_inputs = [Input(f"slider-{nid}", "value") for nid in LEAF_NODES]
computed_outputs = [Output(f"slider-{nid}", "value") for nid in computed_nodes]
mindmap_out = Output("mindmap", "stylesheet")

@app.callback(mindmap_out, *computed_outputs, *leaf_inputs)
def update_graph_and_totals(*vals):
    #  split incoming values
    leaf_vals = dict(zip(LEAF_NODES, vals[-len(LEAF_NODES):]))

    # roll-up helper
    def total(node):
        if node in LEAF_NODES:
            return leaf_vals[node]
        if node in TREE:
            return sum(total(ch) for ch in TREE[node])
        if node == "Equity":
            assets = total("Assets")
            liabilities = total("Liabilities")
            income = total("Income")
            expenses = total("Expenses")
            return assets + income - expenses - liabilities
        return 0

    # compute every parent
    computed_vals = {nid: total(nid) for nid in computed_nodes}

    # resize node circles
    all_values = list(leaf_vals.values()) + list(computed_vals.values())
    max_val = max(all_values) or 1
    stylesheet = graph_panel.children[0].stylesheet[:]

    for nid, v in {**leaf_vals, **computed_vals}.items():
        size = 30 + (v / max_val) * 70
        stylesheet.append({"selector": f"node[id = '{nid}']", "style": {"width": f"{size:.0f}px", "height": f"{size:.0f}px"}})

    # return order: mind-map stylesheet, then each computed slider value
    return (stylesheet, *[computed_vals[n] for n in computed_nodes])

#
# ───────────────────────── 5.  RUN ─────────────────────────
#

if __name__ == "__main__":
    app.run(debug=True)
