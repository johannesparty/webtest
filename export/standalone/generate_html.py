#!/usr/bin/env python3
"""
Generate HTML documentation from CSV specification files.

Usage:
    python generate_html.py

Reads from CSV files in the same directory:
    - objects.csv      - Object names and descriptions
    - fields.csv       - Field definitions (blank json_name = CSV-only)
    - enum_values.csv  - Enum value labels and raw values

Outputs:
    - json_format.html  - JSON export format documentation
    - csv_format.html   - CSV export format documentation
"""

import csv
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# =============================================================================
# DATA LOADING
# =============================================================================

def load_csv(filename: str) -> list[dict]:
    """Load a CSV file and return as list of dicts."""
    filepath = SCRIPT_DIR / filename
    if not filepath.exists():
        print(f"Warning: {filename} not found")
        return []
    with open(filepath, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_all_data() -> dict:
    """Load all CSV files."""
    return {
        "objects": load_csv("objects.csv"),
        "fields": load_csv("fields.csv"),
        "enum_values": load_csv("enum_values.csv"),
    }


# =============================================================================
# SHARED HTML STYLES
# =============================================================================

HTML_STYLES = """
    <style>
        :root {
            --primary-color: #2c5530;
            --secondary-color: #4a7c4e;
            --bg-color: #ffffff;
            --card-bg: #c7c7c7;
            --border-color: #808080;
            --text-color: #333;
            --text-muted: #666;
            --code-bg: rgba(0, 0, 0, 0);
        }

        * { box-sizing: border-box; }

        body {
            font-family: Roboto, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--bg-color);
            margin: 0;
            padding: 0;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: var(--primary-color);
            color: white;
            padding: 30px 20px;
            margin-bottom: 30px;
        }

        header h1 {
            margin: 0 0 10px 0;
            font-size: 2em;
        }

        header p {
            margin: 0;
            opacity: 0.9;
        }

        nav {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 15px 20px;
            margin-bottom: 25px;
        }

        nav a {
            display: inline-block;
            padding: 6px 14px;
            margin: 3px;
            background: var(--code-bg);
            border-radius: 4px;
            text-decoration: none;
            color: var(--text-color);
            font-size: 0.9em;
        }

        nav a:hover {
            background: var(--secondary-color);
            color: white;
        }

        section {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 25px;
            margin-bottom: 25px;
        }

        h2 {
            color: var(--primary-color);
            border-bottom: 2px solid var(--primary-color);
            padding-bottom: 8px;
            margin-top: 0;
            font-size: 1.4em;
        }

        h3 {
            color: var(--secondary-color);
            margin-top: 25px;
            font-size: 1.1em;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
            table-layout: fixed;
        }

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            vertical-align: top;
            overflow-wrap: break-word;
            word-wrap: break-word;
        }

        th {
            background: var(--code-bg);
            font-weight: 600;
            color: var(--primary-color);
            white-space: nowrap;
        }

        tr:hover { background: var(--bg-color); }

        code {
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "SF Mono", Monaco, "Courier New", monospace;
            font-size: 0.85em;
        }

        td:first-child code {
            display: block;
        }

        .type { color: var(--secondary-color); }
        .enum-link { color: #9933cc; }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: 500;
            margin-left: 5px;
        }

        .badge-required { background: #ffe0e0; color: #cc0000; }
        .badge-derived { background: #e0e0ff; color: #0000cc; }

        .description {
            color: var(--text-muted);
            margin-bottom: 15px;
        }

        .muted { color: var(--text-muted); }

        footer {
            text-align: center;
            padding: 20px;
            color: var(--text-muted);
            font-size: 0.85em;
        }

        footer a { color: var(--secondary-color); }
    </style>
"""


# =============================================================================
# JSON FORMAT HTML
# =============================================================================

def generate_json_html(data: dict) -> str:
    """Generate JSON format documentation."""
    objects = data["objects"]
    fields = data["fields"]
    enum_values = data["enum_values"]

    # Get set of object names and descriptions
    object_names = {obj.get("name", "") for obj in objects}
    object_desc = {obj.get("name", ""): obj.get("description", "") for obj in objects}

    # Group fields by object
    fields_by_object = defaultdict(list)
    for field in fields:
        fields_by_object[field.get("object", "")].append(field)

    # Group enum values by enum (use raw values for JSON)
    values_by_enum = defaultdict(list)
    for val in enum_values:
        values_by_enum[val.get("enum", "")].append(val)

    # Build parent map from fields: {ChildType: (ParentObject, field_name, is_array)}
    # e.g., {Project: (Site, "project", False), Note: (Site, "notes", True)}
    parent_map = {}
    for field in fields:
        ftype = field.get("type", "")
        fname = field.get("json_name", "")
        parent_obj = field.get("object", "")
        if not fname:
            continue
        # Check if it's an object reference
        is_array = ftype.endswith("[]")
        base_type = ftype[:-2] if is_array else ftype
        if base_type in object_names:
            parent_map[base_type] = (parent_obj, fname, is_array)

    def compute_json_path(obj_name: str) -> str:
        """Compute json_path by traversing parent relationships."""
        if obj_name in ("Site", "Location"):
            return "sites[]"
        if obj_name not in parent_map:
            return ""
        parent_obj, field_name, is_array = parent_map[obj_name]
        parent_path = compute_json_path(parent_obj)
        suffix = "[]" if is_array else ""
        return f"{parent_path}.{field_name}{suffix}"

    # Merge Location fields into Site (same JSON path sites[])
    if "Location" in fields_by_object and "Site" in fields_by_object:
        fields_by_object["Site"].extend(fields_by_object["Location"])
        del fields_by_object["Location"]

    def is_json_field(f):
        """Check if field should appear in JSON output (has a json_name)."""
        return bool(f.get("json_name"))

    # Filter to objects that have JSON fields
    json_objects = []
    for obj in objects:
        name = obj.get("name", "")
        # Skip Location since we merged it into Site
        if name == "Location":
            continue
        obj_fields = [f for f in fields_by_object.get(name, []) if is_json_field(f)]
        if obj_fields:
            json_objects.append(obj)

    # Build navigation
    nav_items = ['<a href="#overview">Overview</a>']
    for obj in json_objects:
        name = obj.get("name", "")
        nav_items.append(f'<a href="#obj-{name.lower()}">{name}</a>')

    # Build content
    content = []

    # Structure section - compact hierarchy, field names as links
    def link(name, obj, is_array=False):
        suffix = "[]" if is_array else ""
        return f'<a href="#obj-{obj.lower()}">{name}{suffix}</a>'

    structure_html = f'''{link("sites", "Site", True)}
  {link("project", "Project")}
    {link("soilSettings", "SoilSettings")}
      {link("depthIntervals", "ProjectDepthInterval", True)}
  {link("soilData", "SoilData")}
    {link("_depthIntervals", "DepthInterval", True)}
  {link("notes", "Note", True)}
    {link("author", "Author")}
  {link("soil_id", "SoilMatches")}
    {link("matches", "SoilMatch", True)}
      {link("combinedMatch", "MatchScore")}
      {link("dataMatch", "MatchScore")}
      {link("locationMatch", "MatchScore")}
      {link("soilInfo", "SoilInfo")}
        {link("soilSeries", "SoilSeries")}
        {link("ecologicalSite", "EcologicalSite")}
        {link("landCapabilityClass", "LandCapabilityClass")}
        {link("soilData", "MatchSoilData")}
          {link("depthDependentData", "MatchDepthData", True)}'''

    # Overview section with structure
    content.append('<section id="overview">')
    content.append("<h2>Overview</h2>")
    content.append("<p>The export API returns site data in JSON format with the following structure. Click on field names to jump to their documentation.</p>")
    content.append(f'<pre><code>{structure_html}</code></pre>')
    content.append("<p>Fields starting with <code>_</code> are derived fields expanded by the export for convenience.</p>")
    content.append("</section>")

    # Object sections
    for obj in json_objects:
        name = obj.get("name", "")
        desc = obj.get("description", "")
        path = compute_json_path(name)
        obj_fields = [f for f in fields_by_object.get(name, []) if is_json_field(f)]

        if not obj_fields:
            continue

        content.append(f'<section id="obj-{name.lower()}">')
        content.append(f"<h2>{escape(name)}</h2>")
        if desc:
            content.append(f'<p class="description">{escape(desc)}</p>')
        if path:
            content.append(f'<p class="muted">JSON path: <code>{escape(path)}</code></p>')

        content.append("<table>")
        content.append('<tr><th style="width:20%">Field</th><th style="width:20%">Type</th><th style="width:60%">Description</th></tr>')
        for f in obj_fields:
            fname = f.get("json_name", "")
            ftype = f.get("type", "")
            fdesc = f.get("description", "")

            # Check if array type (ends with [])
            is_array = ftype.endswith("[]")
            base_type = ftype[:-2] if is_array else ftype

            # Field name display - add [] suffix for arrays
            if is_array:
                fname_html = f'<code>{escape(fname)}[]</code>'
            else:
                fname_html = f'<code>{escape(fname)}</code>'

            # Type display - show enum values inline (raw values for JSON)
            if base_type in values_by_enum:
                enum_vals = values_by_enum[base_type]
                raw_values = [v.get("value", "") for v in enum_vals]
                type_html = ", ".join(escape(v) for v in raw_values)
            elif base_type == "boolean":
                type_html = '<span class="type">true, false</span>'
            elif base_type == "datetime":
                type_html = '<span class="type">ISO 8601 DateTime</span>'
            elif base_type in object_names:
                # Link to the referenced object type
                type_html = f'<a href="#obj-{base_type.lower()}">{escape(base_type)}</a>'
            else:
                type_html = f'<span class="type">{escape(base_type)}</span>'

            content.append(f'<tr><td>{fname_html}</td>')
            content.append(f'<td>{type_html}</td>')
            content.append(f'<td>{escape(fdesc)}</td></tr>')
        content.append("</table>")
        content.append("</section>")

    # Assemble HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:400,500,600&display=swap">
    <title>LandPKS JSON Export Format</title>
    {HTML_STYLES}
</head>
<body>
    <header>
        <div class="container">
            <h1>LandPKS JSON Export Format</h1>
            <p>Documentation for the JSON format returned by the export API</p>
        </div>
    </header>
    <div class="container">
        <nav>
            {" ".join(nav_items)}
            <span class="muted" style="margin-left: 20px;">See also: <a href="csv_format.html">CSV Format</a></span>
        </nav>
        {"".join(content)}
        <footer>
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} ·
            <a href="https://github.com/techmatters/terraso-backend">terraso-backend</a>
        </footer>
    </div>
</body>
</html>"""
    return html


# =============================================================================
# CSV FORMAT HTML
# =============================================================================

def generate_csv_html(data: dict) -> str:
    """Generate CSV format documentation."""
    fields = data["fields"]
    enum_values = data["enum_values"]

    # Group enum values by enum
    values_by_enum = defaultdict(list)
    for val in enum_values:
        values_by_enum[val.get("enum", "")].append(val)

    # Get fields that have CSV columns, grouped by object
    csv_fields = [f for f in fields if f.get("csv_column")]
    fields_by_object = defaultdict(list)
    for f in csv_fields:
        fields_by_object[f.get("object", "")].append(f)

    # Section definitions with display names (ordered to match CSV output)
    sections = [
        ("Site", "Site"),
        ("Project", "Project"),
        ("Location", "Location"),
        ("SoilMatches", "Soil Matches"),
        ("EcologicalSite", "Ecological Site"),
        ("SoilData", "Soil Data"),
        ("DepthInterval", "Depth Intervals"),
    ]

    # Build navigation
    nav_items = []
    for obj_name, display_name in sections:
        nav_items.append(f'<a href="#csv-{obj_name.lower()}">{display_name}</a>')

    content = []

    # Overview
    content.append('<section id="overview">')
    content.append("<h2>Overview</h2>")
    content.append("<p>The CSV export produces <strong>one row per depth interval per site</strong>. Site-level fields repeat on each row.</p>")
    content.append("</section>")

    # Generate each section
    for obj_name, display_name in sections:
        obj_fields = fields_by_object.get(obj_name, [])

        if not obj_fields:
            continue

        content.append(f'<section id="csv-{obj_name.lower()}">')
        content.append(f"<h2>{display_name}</h2>")

        if obj_name == "DepthInterval":
            content.append('<p class="description">One row per depth interval. Intervals are determined by the site\'s depth interval preset.</p>')

        content.append("<table>")
        content.append('<tr><th style="width:20%">CSV Column</th><th style="width:20%">Type</th><th style="width:60%">Description</th></tr>')

        # Regular fields
        for f in obj_fields:
            csv_col = f.get("csv_column", "")
            ftype = f.get("type", "")
            fdesc = f.get("description", "")

            if ftype in values_by_enum:
                # Show enum values inline
                enum_vals = values_by_enum[ftype]
                val_labels = [v.get("label", "") for v in enum_vals]
                type_html = ", ".join(escape(v) for v in val_labels)
            elif ftype == "boolean":
                type_html = '<span class="type">TRUE, FALSE</span>'
            else:
                type_html = f'<span class="type">{escape(ftype)}</span>'

            content.append(f'<tr><td>{escape(csv_col)}</td>')
            content.append(f'<td>{type_html}</td>')
            content.append(f'<td>{escape(fdesc)}</td></tr>')

        content.append("</table>")
        content.append("</section>")

    # Assemble HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Roboto:400,500,600&display=swap">
    <title>LandPKS CSV Export Format</title>
    {HTML_STYLES}
</head>
<body>
    <header>
        <div class="container">
            <h1>LandPKS CSV Export Format</h1>
            <p>Documentation for the CSV format returned by the export API</p>
        </div>
    </header>
    <div class="container">
        <nav>
            {" ".join(nav_items)}
            <span class="muted" style="margin-left: 20px;">See also: <a href="json_format.html">JSON Format</a></span>
        </nav>
        {"".join(content)}
        <footer>
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M")} ·
            <a href="https://github.com/techmatters/terraso-backend">terraso-backend</a>
        </footer>
    </div>
</body>
</html>"""
    return html


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("Loading CSV files...")
    data = load_all_data()

    total = sum(len(v) for v in data.values())
    print(f"Loaded {total} total rows")

    print("Generating JSON format documentation...")
    json_html = generate_json_html(data)
    json_path = SCRIPT_DIR / "json_format.html"
    with open(json_path, "w") as f:
        f.write(json_html)
    print(f"  Written to {json_path}")

    print("Generating CSV format documentation...")
    csv_html = generate_csv_html(data)
    csv_path = SCRIPT_DIR / "csv_format.html"
    with open(csv_path, "w") as f:
        f.write(csv_html)
    print(f"  Written to {csv_path}")

    print("Done!")


if __name__ == "__main__":
    main()
