#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Make .wfl snippets from a val.jsonl file.

Each line in val.jsonl is a JSON object with keys:
  - "input": <str> (ignored here)
  - "output": <dict> possibly containing:
        - Steps: <list>            # preferred
        - workflowSteps: <list>    # fallback
        - Name, Description, Scope, Schedule, Timeout, Version (optional)

For each line, we create a .wfl file with the following structure:

# Metadata:

## Tags

## Scopes
### All Systems
### All Windows Servers

## Custom fields

## Scripts

## Tasks

## Files

## Workflows

# Data:
{"Name": "...", "Description": "...", "Scope": "...", "Schedule": null, "Steps": [...], "Timeout": 12, "Version": 1}

Usage:
    python make_wfl_snippets.py --input val.jsonl --outdir ./snippets

Notes:
- Blank lines are ignored.
- Lines that fail JSON parsing are reported and skipped.
- Filenames are derived from "Name" (slugified); fallback to snippet_<n>.wfl
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---- Static template parts ----------------------------------------------------

TEMPLATE_HEADER = """# Metadata:

## Tags

## Scopes
### All Systems
### All Windows Servers

## Custom fields

## Scripts

## Tasks

## Files

## Workflows
"""

TEMPLATE_DATA = {
    "Name": "test",
    "Description": "success message formats.",
    "Scope": "All Systems",
    "Schedule": None,
    "Steps": [],
    "Timeout": 12,
    "Version": 1,
}

# ---- Helpers -----------------------------------------------------------------

_slug_re = re.compile(r"[^a-z0-9]+", re.IGNORECASE)

def slugify(name: str, fallback: str) -> str:
    """
    Convert a string to a filesystem-friendly slug; return fallback if empty.
    """
    s = name.strip().lower()
    s = _slug_re.sub("-", s).strip("-")
    return s or fallback

def coalesce_steps(output: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Prefer 'Steps', else 'workflowSteps'. Return None if neither is present or invalid.
    """
    if isinstance(output.get("Steps"), list):
        return output["Steps"]
    if isinstance(output.get("workflowSteps"), list):
        return output["workflowSteps"]
    return None

def build_data_block(output: Dict[str, Any], keep_template_defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the '# Data:' JSON object by merging template defaults with
    fields from 'output' (when present). Always inject Steps from
    'Steps' or 'workflowSteps'.
    """
    data = dict(keep_template_defaults)  # copy

    steps = coalesce_steps(output)
    if steps is None:
        raise ValueError("Neither 'Steps' nor 'workflowSteps' found as a list in 'output'.")

    data["Steps"] = steps

    # Optionally carry over common metadata fields if present; otherwise keep template defaults
    # for key in ("Name", "Description", "Scope", "Schedule", "Timeout", "Version"):
    #     if key in output and output[key] is not None:
    #         data[key] = output[key]

    return data

def render_wfl_text(data_obj: Dict[str, Any]) -> str:
    """
    Render the final .wfl text with header + '# Data:' + compact JSON.
    """
    # Compact JSON (no extra spaces/newlines) to mirror your example
    json_payload = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
    return f"{TEMPLATE_HEADER}\n# Data:\n{json_payload}\n"

# ---- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Create .wfl snippets from a val.jsonl file.")
    ap.add_argument("--input", "-i", type=Path, required=True, help="Path to val.jsonl")
    ap.add_argument("--outdir", "-o", type=Path, required=True, help="Directory to write .wfl files")
    ap.add_argument("--prefix", default="", help="Optional filename prefix (before slug).")
    ap.add_argument("--dry-run", action="store_true", help="Parse and show summary without writing files.")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    total = 0
    written = 0
    errors = 0

    with args.input.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue

            total += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[line {lineno}] JSON parse error: {e}")
                errors += 1
                continue

            output = row.get("output")
            if not isinstance(output, dict):
                print(f"[line {lineno}] Missing or invalid 'output' object.")
                errors += 1
                continue

            try:
                data_obj = build_data_block(output, TEMPLATE_DATA)
            except Exception as e:
                print(f"[line {lineno}] {e}")
                errors += 1
                continue

            name_for_file = f"snippet-{lineno}"
            slug = slugify(name_for_file, f"snippet-{lineno}")
            filename = f"{args.prefix}{slug}.wfl"
            wfl_text = render_wfl_text(data_obj)

            if args.dry_run:
                print(f"[line {lineno}] Would write: {filename} (Steps: {len(data_obj.get('Steps', []))})")
            else:
                (args.outdir / filename).write_text(wfl_text, encoding="utf-8")
                written += 1

    if args.dry_run:
        print(f"\nDone (dry run). Parsed lines: {total}, would write: {total - errors}, errors: {errors}")
    else:
        print(f"\nDone. Parsed lines: {total}, written: {written}, errors: {errors}, output dir: {args.outdir}")

if __name__ == "__main__":
    main()
