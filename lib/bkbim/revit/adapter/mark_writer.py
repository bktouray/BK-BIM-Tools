# -*- coding: utf-8 -*-
"""Writes the instance "Mark" parameter (BuiltInParameter.ALL_MODEL_MARK) -
the port `auto_mark_command.run()` calls once per (ref, mark_value)
assignment the domain planner produced. No Transaction handling here - same
convention as every other writer in this codebase (SAD Sec 4.4): the caller
(mark_flow.py) owns the Transaction, this class just performs one `param.Set`
per call and reports whether it worked.
"""

import clr

clr.AddReference("RevitAPI")

from Autodesk.Revit.DB import BuiltInParameter


class RevitMarkWriter(object):
    def __init__(self, doc):
        self._doc = doc

    def write(self, ref, mark_value):
        """`ref` is an ElementId (see MarkTypeGroup.instance_refs).
        Returns True if the Mark parameter was set, False if the element
        couldn't be resolved, has no Mark parameter, or it's read-only.
        """
        element = self._doc.GetElement(ref)
        if element is None:
            return False
        try:
            param = element.get_Parameter(BuiltInParameter.ALL_MODEL_MARK)
        except Exception:
            return False
        if param is None or param.IsReadOnly:
            return False
        try:
            param.Set(mark_value)
            return True
        except Exception:
            return False
