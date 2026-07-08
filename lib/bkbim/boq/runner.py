# -*- coding: utf-8 -*-
"""CPython-side worker. Invoked by pybridge.run() as:

    python.exe runner.py <payload.json>

Reads a JSON payload describing an export or split job, performs it with the
vendored openpyxl, and prints a JSON result on stdout. Runs under real CPython
(3.x), never IronPython, so openpyxl is available.
"""

import os
import sys
import io
import json

HERE = os.path.dirname(os.path.abspath(__file__))     # .../lib/bkbim/boq
BKBIM_DIR = os.path.dirname(HERE)                     # .../lib/bkbim
LIB = os.path.dirname(BKBIM_DIR)                      # .../lib
sys.path.insert(0, LIB)                       # for `bkbim.boq`
sys.path.insert(0, os.path.join(LIB, "vendor"))   # for openpyxl

from bkbim.boq.model import Sheet, Extract
from bkbim.boq import xlio


def main():
    with io.open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)

    action = data.get("action", "export")

    if action == "split":
        written = xlio.split_workbook(data["path"], data["out_folder"])
        sys.stdout.write(json.dumps({"written": written}))
        return

    extracts = []
    for ex in data["extracts"]:
        sheets = [
            Sheet(s["name"], s["columns"], s["rows"], s.get("key_col", "Key"))
            for s in ex["sheets"]
        ]
        extracts.append(Extract(ex["label"], sheets))

    summary = xlio.write_extracts(data["path"], extracts, data["mode"])
    sys.stdout.write(json.dumps({"summary": summary}))


if __name__ == "__main__":
    main()
