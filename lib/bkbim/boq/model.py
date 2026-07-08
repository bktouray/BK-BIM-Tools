# -*- coding: utf-8 -*-
"""Pure-Python data model shared by extractors and the Excel writer.

Deliberately free of any Revit/pyRevit imports so the Excel layer can be unit
tested outside Revit.
"""

KEY = "Key"
STATUS = "Status"


class Sheet(object):
    def __init__(self, name, columns, rows, key_col=KEY):
        self.name = name            # short suffix, e.g. "Used" / "Unused"
        self.columns = columns      # ordered list incl. Key + Status
        self.rows = rows            # list of dict
        self.key_col = key_col


class Extract(object):
    def __init__(self, label, sheets):
        self.label = label          # category label, e.g. "Walls"
        self.sheets = sheets        # list[Sheet]
