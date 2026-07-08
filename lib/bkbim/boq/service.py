# -*- coding: utf-8 -*-
"""High-level orchestration shared by every BOQ export button.

Runs on pyRevit's IronPython engine: prompts the user, collects the Revit data
via the extractors, then hands the Excel writing off to CPython through
``pybridge`` (which runs the vendored openpyxl). A button just calls
``run_export([...labels...])``.
"""

import os
import datetime

from pyrevit import forms, script

from bkbim.boq import rvt, extractors, pybridge

logger = script.get_logger()

DEFAULT_NAME = "BKDesigns_BOQ"


def _scope_prompt():
    choice = forms.CommandSwitchWindow.show(
        ["All  (used + unused)", "Used only"],
        message="What should the export include?",
    )
    if not choice:
        return None
    return "all" if choice.startswith("All") else "used"


def _timestamped(path):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    root, ext = os.path.splitext(path)
    return "{}_{}{}".format(root, stamp, ext)


def _save_prompt(default_name):
    path = forms.save_file(file_ext="xlsx", default_name=default_name)
    if not path:
        return None, None
    if os.path.exists(path):
        choice = forms.alert(
            "A workbook already exists here:\n\n{}\n\n"
            "Merge will update matched rows by Revit UniqueId, add new ones, "
            "flag removed ones, and KEEP any extra columns you/the QS added "
            "(rates, prices, notes).".format(os.path.basename(path)),
            title="File exists",
            options=["Merge into existing file", "Create new timestamped file"],
        )
        if not choice:
            return None, None
        if choice.startswith("Merge"):
            return path, "merge"
        return _timestamped(path), "new"
    return path, "new"


def _extract_to_payload(extracts, path, mode):
    return {
        "action": "export",
        "path": path,
        "mode": mode,
        "extracts": [
            {
                "label": ex.label,
                "sheets": [
                    {
                        "name": s.name,
                        "columns": s.columns,
                        "key_col": s.key_col,
                        "rows": s.rows,
                    }
                    for s in ex.sheets
                ],
            }
            for ex in extracts
        ],
    }


def run_export(labels, default_name=None):
    """Export the given category labels. ``labels`` is a list of REGISTRY keys."""
    doc = rvt.get_doc()
    if not doc:
        forms.alert("No active Revit document.", title="BOQ Export", ok=True)
        return

    scope = _scope_prompt()
    if scope is None:
        return

    path, mode = _save_prompt(default_name or DEFAULT_NAME)
    if not path:
        return

    extracts = []
    with forms.ProgressBar(title="Extracting {value} of {max_value}",
                           cancellable=True) as pb:
        total = len(labels)
        for i, label in enumerate(labels, start=1):
            if pb.cancelled:
                return
            pb.update_progress(i, total)
            try:
                extracts.append(extractors.run(doc, label, scope))
            except Exception as e:
                logger.error("Failed extracting %s: %s", label, e)
                forms.alert("Failed extracting {}:\n{}".format(label, e),
                            title="BOQ Export", ok=True)

    if not extracts:
        return

    try:
        result = pybridge.run(_extract_to_payload(extracts, path, mode))
        summary = result.get("summary", [])
    except Exception as e:
        logger.error("Excel write failed: %s", e)
        forms.alert("Could not write the workbook:\n{}".format(e),
                    title="BOQ Export", ok=True)
        return

    lines = ["Saved to:", path, ""]
    for item in summary:
        sheet_name, n, counts = item[0], item[1], item[2]
        detail = ", ".join("{} {}".format(v, k) for k, v in counts.items() if k)
        lines.append("- {}: {} rows{}".format(
            sheet_name, n, ("  ({})".format(detail) if detail else "")))
    if forms.alert("\n".join(lines), title="Export complete",
                   options=["Open folder", "Done"]) == "Open folder":
        try:
            os.startfile(os.path.dirname(path))
        except Exception:
            pass


def run_split():
    """Split-workbook tool: explode each sheet into its own file."""
    src = forms.pick_file(file_ext="xlsx", title="Pick the workbook to split")
    if not src:
        return
    out = forms.pick_folder(title="Pick a folder for the split files")
    if not out:
        return
    try:
        result = pybridge.run({"action": "split", "path": src, "out_folder": out})
        written = result.get("written", [])
    except Exception as e:
        forms.alert("Split failed:\n{}".format(e), title="BOQ Export", ok=True)
        return
    if forms.alert("Wrote {} files to:\n{}".format(len(written), out),
                   title="Split complete",
                   options=["Open folder", "Done"]) == "Open folder":
        try:
            os.startfile(out)
        except Exception:
            pass


def run_master():
    """Master export: multi-select categories, then export."""
    labels = forms.SelectFromList.show(
        [lbl for lbl, _ in extractors.REGISTRY],
        title="Select categories to export",
        multiselect=True,
        button_name="Export selected",
    )
    if not labels:
        return
    run_export(list(labels), default_name="BKDesigns_BOQ")
