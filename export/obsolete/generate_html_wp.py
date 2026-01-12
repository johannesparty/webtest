#!/usr/bin/env python3
"""
Generate WordPress-friendly HTML documentation from CSV specification files.

Outputs semantic HTML with minimal scoped CSS, designed to inherit WordPress theme styles.
"""

import csv
from collections import defaultdict
from html import escape
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


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


# Minimal scoped CSS - only what WordPress themes typically don't provide
SCOPED_STYLES = """
<style>
/* Scoped styles for export docs - minimal overrides */
#export-docs .nav-links {
    margin-bottom: 1.5em;
    padding: 1em;
    background: #f5f5f5;
    border-radius: 4px;
}
#export-docs .nav-links a {
    display: inline-block;
    margin: 0.25em 0.5em 0.25em 0;
    padding: 0.25em 0.75em;
    background: #e0e0e0;
    border-radius: 3px;
    text-decoration: none;
}
#export-docs .nav-links a:hover {
    background: #4a7c4e;
    color: white;
}
#export-docs table {
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
}
#export-docs th,
#export-docs td {
    padding: 0.5em 0.75em;
    text-align: left;
    border-bottom: 1px solid #ddd;
    vertical-align: top;
}
#export-docs th {
    background: #f9f9f9;
    font-weight: 600;
}
#export-docs code {
    background: #f5f5f5;
    padding: 0.1em 0.4em;
    border-radius: 3px;
    font-size: 0.9em;
}
#export-docs pre {
    background: #f5f5f5;
    padding: 1em;
    border-radius: 4px;
    overflow-x: auto;
}
#export-docs .section {
    margin-bottom: 2em;
}
#export-docs .muted {
    color: #666;
}
#export-docs .json-path {
    color: #666;
    font-size: 0.9em;
    margin-bottom: 1em;
}
</style>
"""


def generate_json_html(data: dict) -> str:
    """Generate WordPress-friendly JSON format documentation."""
    objects = data["objects"]
    fields = data["fields"]
    enum_values = data["enum_values"]

    object_names = {obj.get("name", "") for obj in objects}
    object_desc = {obj.get("name", ""): obj.get("description", "") for obj in objects}

    fields_by_object = defaultdict(list)
    for field in fields:
        fields_by_object[field.get("object", "")].append(field)

    values_by_enum = defaultdict(list)
    for val in enum_values:
        values_by_enum[val.get("enum", "")].append(val)

    # Build parent map for json_path computation
    parent_map = {}
    for field in fields:
        ftype = field.get("type", "")
        fname = field.get("json_name", "")
        parent_obj = field.get("object", "")
        if not fname:
            continue
        is_array = ftype.endswith("[]")
        base_type = ftype[:-2] if is_array else ftype
        if base_type in object_names:
            parent_map[base_type] = (parent_obj, fname, is_array)

    def compute_json_path(obj_name: str) -> str:
        if obj_name in ("Site", "Location"):
            return "sites[]"
        if obj_name not in parent_map:
            return ""
        parent_obj, field_name, is_array = parent_map[obj_name]
        parent_path = compute_json_path(parent_obj)
        suffix = "[]" if is_array else ""
        return f"{parent_path}.{field_name}{suffix}"

    # Merge Location into Site
    if "Location" in fields_by_object and "Site" in fields_by_object:
        fields_by_object["Site"].extend(fields_by_object["Location"])
        del fields_by_object["Location"]

    def is_json_field(f):
        return bool(f.get("json_name"))

    json_objects = []
    for obj in objects:
        name = obj.get("name", "")
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

    content = []

    # Structure overview
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

    content.append('<div class="section" id="overview">')
    content.append("<h2>Overview</h2>")
    content.append("<p>The export API returns site data in JSON format with the following structure:</p>")
    content.append(f'<pre><code>{structure_html}</code></pre>')
    content.append("<p>Fields starting with <code>_</code> are derived fields expanded by the export.</p>")
    content.append("</div>")

    # Object sections
    for obj in json_objects:
        name = obj.get("name", "")
        desc = obj.get("description", "")
        path = compute_json_path(name)
        obj_fields = [f for f in fields_by_object.get(name, []) if is_json_field(f)]

        if not obj_fields:
            continue

        content.append(f'<div class="section" id="obj-{name.lower()}">')
        content.append(f"<h2>{escape(name)}</h2>")
        if desc:
            content.append(f'<p>{escape(desc)}</p>')
        if path:
            content.append(f'<p class="json-path">JSON path: <code>{escape(path)}</code></p>')

        content.append("<table>")
        content.append("<thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>")
        content.append("<tbody>")

        for f in obj_fields:
            fname = f.get("json_name", "")
            ftype = f.get("type", "")
            fdesc = f.get("description", "")

            is_array = ftype.endswith("[]")
            base_type = ftype[:-2] if is_array else ftype

            if is_array:
                fname_html = f'<code>{escape(fname)}[]</code>'
            else:
                fname_html = f'<code>{escape(fname)}</code>'

            if base_type in values_by_enum:
                enum_vals = values_by_enum[base_type]
                raw_values = [v.get("value", "") for v in enum_vals]
                type_html = ", ".join(escape(v) for v in raw_values)
            elif base_type == "boolean":
                type_html = "true, false"
            elif base_type == "datetime":
                type_html = "ISO 8601 DateTime"
            elif base_type in object_names:
                type_html = f'<a href="#obj-{base_type.lower()}">{escape(base_type)}</a>'
            else:
                type_html = escape(base_type)

            content.append(f'<tr><td>{fname_html}</td><td>{type_html}</td><td>{escape(fdesc)}</td></tr>')

        content.append("</tbody></table>")
        content.append("</div>")

    # Assemble - just the content div, no full HTML wrapper
    html = f"""<!-- WordPress Export Docs - JSON Format -->
{SCOPED_STYLES}
<div id="export-docs">
    <h1>LandPKS JSON Export Format</h1>
    <p>Documentation for the JSON format returned by the export API</p>

    <div class="nav-links">
        {" ".join(nav_items)}
        <span class="muted" style="margin-left: 1em;">See also: <a href="csv_format_wp.html">CSV Format</a></span>
    </div>

    {"".join(content)}
</div>
"""
    return html


def generate_csv_html(data: dict) -> str:
    """Generate WordPress-friendly CSV format documentation."""
    fields = data["fields"]
    enum_values = data["enum_values"]

    values_by_enum = defaultdict(list)
    for val in enum_values:
        values_by_enum[val.get("enum", "")].append(val)

    csv_fields = [f for f in fields if f.get("csv_column")]
    fields_by_object = defaultdict(list)
    for f in csv_fields:
        fields_by_object[f.get("object", "")].append(f)

    sections = [
        ("Site", "Site"),
        ("Project", "Project"),
        ("Location", "Location"),
        ("SoilMatches", "Soil Matches"),
        ("EcologicalSite", "Ecological Site"),
        ("SoilData", "Soil Data"),
        ("DepthInterval", "Depth Intervals"),
    ]

    nav_items = []
    for obj_name, display_name in sections:
        if fields_by_object.get(obj_name):
            nav_items.append(f'<a href="#csv-{obj_name.lower()}">{display_name}</a>')

    content = []

    content.append('<div class="section" id="overview">')
    content.append("<h2>Overview</h2>")
    content.append("<p>The CSV export produces <strong>one row per depth interval per site</strong>. Site-level fields repeat on each row.</p>")
    content.append("</div>")

    for obj_name, display_name in sections:
        obj_fields = fields_by_object.get(obj_name, [])
        if not obj_fields:
            continue

        content.append(f'<div class="section" id="csv-{obj_name.lower()}">')
        content.append(f"<h2>{display_name}</h2>")

        if obj_name == "DepthInterval":
            content.append("<p>One row per depth interval. Intervals are determined by the site's depth interval preset.</p>")

        content.append("<table>")
        content.append("<thead><tr><th>CSV Column</th><th>Type</th><th>Description</th></tr></thead>")
        content.append("<tbody>")

        for f in obj_fields:
            csv_col = f.get("csv_column", "")
            ftype = f.get("type", "")
            fdesc = f.get("description", "")

            if ftype in values_by_enum:
                enum_vals = values_by_enum[ftype]
                val_labels = [v.get("label", "") for v in enum_vals]
                type_html = ", ".join(escape(v) for v in val_labels)
            elif ftype == "boolean":
                type_html = "TRUE, FALSE"
            else:
                type_html = escape(ftype)

            content.append(f'<tr><td>{escape(csv_col)}</td><td>{type_html}</td><td>{escape(fdesc)}</td></tr>')

        content.append("</tbody></table>")
        content.append("</div>")

    html = f"""<!-- WordPress Export Docs - CSV Format -->
{SCOPED_STYLES}
<div id="export-docs">
    <h1>LandPKS CSV Export Format</h1>
    <p>Documentation for the CSV format returned by the export API</p>

    <div class="nav-links">
        {" ".join(nav_items)}
        <span class="muted" style="margin-left: 1em;">See also: <a href="json_format_wp.html">JSON Format</a></span>
    </div>

    {"".join(content)}
</div>
"""
    return html


def main():
    print("Loading CSV files...")
    data = load_all_data()

    print("Generating WordPress-friendly JSON format...")
    json_html = generate_json_html(data)
    json_path = SCRIPT_DIR / "json_format_wp.html"
    with open(json_path, "w") as f:
        f.write(json_html)
    print(f"  Written to {json_path}")

    print("Generating WordPress-friendly CSV format...")
    csv_html = generate_csv_html(data)
    csv_path = SCRIPT_DIR / "csv_format_wp.html"
    with open(csv_path, "w") as f:
        f.write(csv_html)
    print(f"  Written to {csv_path}")

    print("Done!")


if __name__ == "__main__":
    main()
