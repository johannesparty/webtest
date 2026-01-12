#!/usr/bin/env python3
"""Generate a visual hierarchy diagram of the JSON export structure."""

import csv
from pathlib import Path

DOCS_DIR = Path(__file__).parent


def load_csv(filename: str) -> list[dict]:
    with open(DOCS_DIR / filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_tree():
    """Build tree structure from fields.csv."""
    fields = load_csv("fields.csv")
    objects = load_csv("objects.csv")
    enum_values = load_csv("enum_values.csv")

    object_names = {obj["name"] for obj in objects}
    object_desc = {obj["name"]: obj["description"] for obj in objects}

    # Group enum values by enum name
    values_by_enum = {}
    for val in enum_values:
        enum_name = val.get("enum", "")
        if enum_name not in values_by_enum:
            values_by_enum[enum_name] = []
        values_by_enum[enum_name].append(val.get("value", ""))

    # Build children map: parent -> [(field_name, child_type, is_array)]
    children = {}
    # Build primitive fields map: parent -> [(field_name, type_display, description)]
    primitives = {}

    for field in fields:
        ftype = field["type"]
        fname = field["json_name"]
        parent = field["object"]
        fdesc = field["description"]

        if not fname:
            continue

        is_array = ftype.endswith("[]")
        base_type = ftype[:-2] if is_array else ftype

        if base_type in object_names:
            # Object reference
            if parent not in children:
                children[parent] = []
            children[parent].append((fname, base_type, is_array))
        else:
            # Primitive field - compute display type
            if base_type in values_by_enum:
                type_display = ", ".join(values_by_enum[base_type])
            elif base_type == "boolean":
                type_display = "true, false"
            elif base_type == "datetime":
                type_display = "ISO 8601 DateTime"
            else:
                type_display = base_type

            if parent not in primitives:
                primitives[parent] = []
            primitives[parent].append((fname, type_display, fdesc))

    # Merge Location fields into Site (they appear at the same level in JSON)
    if "Location" in primitives and "Site" in primitives:
        primitives["Site"].extend(primitives["Location"])
        del primitives["Location"]

    return children, primitives, object_desc


def generate_html(children: dict, primitives: dict, descriptions: dict) -> str:
    """Generate HTML with nested boxes."""

    # Color palette for depth levels
    colors = [
        "#e8f5e9",  # Light green
        "#fff3e0",  # Light orange
        "#e3f2fd",  # Light blue
        "#fce4ec",  # Light pink
        "#f3e5f5",  # Light purple
        "#e0f7fa",  # Light cyan
        "#fff8e1",  # Light amber
        "#efebe9",  # Light brown
    ]

    border_colors = [
        "#4caf50",  # Green
        "#ff9800",  # Orange
        "#2196f3",  # Blue
        "#e91e63",  # Pink
        "#9c27b0",  # Purple
        "#00bcd4",  # Cyan
        "#ffc107",  # Amber
        "#795548",  # Brown
    ]

    def escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def render_node(obj_name: str, field_name: str = None, is_array: bool = False, depth: int = 0) -> str:
        color = colors[depth % len(colors)]
        border = border_colors[depth % len(border_colors)]
        desc = descriptions.get(obj_name, "")

        label = field_name or obj_name
        if is_array:
            label += "[]"

        # Build primitive fields HTML
        fields_html = ""
        if obj_name in primitives:
            field_rows = []
            for fname, ftype, fdesc in primitives[obj_name]:
                field_rows.append(
                    f'<tr><td class="pfield-name">{escape_html(fname)}</td>'
                    f'<td class="pfield-type">{escape_html(ftype)}</td>'
                    f'<td class="pfield-desc">{escape_html(fdesc)}</td></tr>'
                )
            fields_html = f'<table class="fields">{"".join(field_rows)}</table>'

        # Build children HTML
        child_html = ""
        if obj_name in children:
            child_items = []
            for child_field, child_type, child_is_array in children[obj_name]:
                child_items.append(render_node(child_type, child_field, child_is_array, depth + 1))
            child_html = f'<div class="children">{"".join(child_items)}</div>'

        return f'''<div class="node" style="background: {color}; border-color: {border};">
            <div class="header">
                <span class="field-name">{label}</span>
                <span class="type-name">{obj_name}</span>
            </div>
            {f'<div class="desc">{escape_html(desc)}</div>' if desc else ''}
            {fields_html}
            {child_html}
        </div>'''

    # Start with Site as root
    tree_html = render_node("Site", "sites", is_array=True, depth=0)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:400,500,600&display=swap">
    <title>LandPKS JSON Export Hierarchy</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            color: #2c5530;
            margin-bottom: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .node {{
            border: 2px solid;
            border-radius: 8px;
            padding: 12px;
            margin: 8px 0;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .field-name {{
            font-weight: 600;
            font-size: 1em;
            color: #333;
        }}
        .type-name {{
            font-size: 0.85em;
            color: #666;
            font-style: italic;
        }}
        .desc {{
            font-size: 0.8em;
            color: #555;
            margin-bottom: 8px;
            padding: 4px 8px;
        }}
        .children {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }}
        .children > .node {{
            flex: 1 1 auto;
            min-width: 200px;
        }}
        /* Collapse deeply nested to vertical */
        .children .children .children {{
            flex-direction: column;
        }}
        .children .children .children > .node {{
            min-width: unset;
        }}
        .legend {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .legend-title {{
            font-weight: 600;
            margin-bottom: 8px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 15px;
            font-size: 0.9em;
        }}
        .legend-item code {{
            background: #eee;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .fields {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8em;
            margin: 8px 0;
        }}
        .fields td {{
            padding: 4px 8px;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            vertical-align: top;
        }}
        .fields tr:last-child td {{
            border-bottom: none;
        }}
        .pfield-name {{
            font-weight: 500;
            color: #333;
            white-space: nowrap;
            width: 20%;
        }}
        .pfield-type {{
            color: #666;
            font-style: italic;
            width: 20%;
        }}
        .pfield-desc {{
            color: #555;
            width: 60%;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>LandPKS JSON Export Hierarchy</h1>
        <div class="legend">
            <div class="legend-title">Legend</div>
            <span class="legend-item"><code>field_name</code> - JSON field name</span>
            <span class="legend-item"><em>TypeName</em> - Object type</span>
            <span class="legend-item"><code>[]</code> - Array field</span>
        </div>
        {tree_html}
    </div>
</body>
</html>'''


def main():
    children, primitives, descriptions = build_tree()
    html = generate_html(children, primitives, descriptions)

    output_path = DOCS_DIR / "hierarchy.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    main()
