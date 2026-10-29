# -*- coding: utf-8 -*-
"""Host-document element snapshots and safe selection/view actions."""
import clr
clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
from Autodesk.Revit.DB import (
    Element, ElementId, ElementType, FilteredElementCollector, StorageType,
    Transaction, TransactionStatus, UnitUtils)
from System.Collections.Generic import List


def _id(value):
    return value.Value


def _name(element):
    return Element.Name.GetValue(element) if element is not None else u""


class MasterFilterAdapter(object):
    def __init__(self, uidoc):
        self.uidoc = uidoc
        self.doc = uidoc.Document
        self.selection = list(uidoc.Selection.GetElementIds())
        self.parameters = {}

    def read(self, scope):
        if scope == "Current selection":
            elements = [self.doc.GetElement(eid) for eid in self.selection]
        else:
            if scope == "Active view":
                view_id = self.doc.ActiveView.Id
                if not FilteredElementCollector.IsViewValidForElementIteration(self.doc, view_id):
                    raise ValueError("The active view does not support element collection.")
                collector = FilteredElementCollector(self.doc, view_id)
            elif scope == "Entire project":
                collector = FilteredElementCollector(self.doc)
            else:
                raise ValueError("Unknown element scope.")
            elements = collector.WhereElementIsNotElementType().ToElements()
        records = []
        self.parameters = {}
        for element in elements:
            if element is None or isinstance(element, ElementType) or element.Category is None:
                continue
            element_type = self.doc.GetElement(element.GetTypeId())
            level = self.doc.GetElement(element.LevelId)
            parameter_keys = set()
            records.append({
                "id": _id(element.Id), "element": element,
                "category": element.Category.Name,
                "family": element_type.FamilyName if element_type else u"(No family)",
                "type": _name(element_type) or u"(No type)",
                "level": _name(level) or u"(No level)",
                "parameters": parameter_keys,
            })
            for source, owner in (("Instance", element), ("Type", element_type)):
                if owner is None:
                    continue
                for parameter in owner.Parameters:
                    key = (source, _id(parameter.Id))
                    parameter_keys.add(key)
                    self.parameters[key] = u"{0}: {1} [{2}]".format(
                        source, parameter.Definition.Name, key[1])
        return records

    def value(self, record, key):
        source, parameter_id = key
        owner = record["element"]
        if source == "Type":
            owner = self.doc.GetElement(owner.GetTypeId())
        if owner is None:
            return None
        parameter = next((p for p in owner.Parameters if _id(p.Id) == parameter_id), None)
        if parameter is None:
            return None
        number = None
        if parameter.StorageType == StorageType.String:
            text = parameter.AsString() or u""
        elif parameter.StorageType == StorageType.Double:
            number = parameter.AsDouble()
            if UnitUtils.IsMeasurableSpec(parameter.Definition.GetDataType()):
                number = UnitUtils.ConvertFromInternalUnits(number, parameter.GetUnitTypeId())
            text = parameter.AsValueString() or u"{0}".format(number)
        elif parameter.StorageType == StorageType.Integer:
            number = parameter.AsInteger()
            text = parameter.AsValueString() or u"{0}".format(number)
        elif parameter.StorageType == StorageType.ElementId:
            ref_id = parameter.AsElementId()
            text = parameter.AsValueString() or _name(self.doc.GetElement(ref_id)) or u"{0}".format(_id(ref_id))
        else:
            text = u""
        return {"text": text, "number": number, "has_value": parameter.HasValue}

    def apply(self, records, action):
        if not records:
            raise ValueError("No matching elements. Your current selection was preserved.")
        ids = List[ElementId]([ElementId(row["id"]) for row in records])
        if action == "Isolate":
            view = self.doc.ActiveView
            if not view.CanUseTemporaryVisibilityModes():
                raise ValueError("This view does not support temporary isolation.")
            transaction = Transaction(self.doc, "BK Master Filter - Temporary isolate")
            transaction.Start()
            try:
                view.IsolateElementsTemporary(ids)
                if transaction.Commit() != TransactionStatus.Committed:
                    raise ValueError("Revit did not commit temporary isolation.")
            except Exception:
                if transaction.GetStatus() == TransactionStatus.Started:
                    transaction.RollBack()
                raise
        elif action not in ("Select", "Show"):
            raise ValueError("Unknown result action.")
        if action == "Show":
            self.uidoc.ShowElements(ids)
        self.uidoc.Selection.SetElementIds(ids)


def run(uidoc):
    from bkbim.ui.views.master_filter import MasterFilterWindow
    from bkbim.ui.views.result_dialog import show_result
    try:
        if uidoc is None:
            raise ValueError("Open a Revit project first.")
        if uidoc.Document.IsFamilyDocument:
            raise ValueError("Master Filter works in project documents.")
        adapter = MasterFilterAdapter(uidoc)
        window = MasterFilterWindow(adapter)
        window.ShowDialog()
        if window.result:
            records, action = window.result
            adapter.apply(records, action)
    except Exception as exc:
        show_result("Master Filter", u"{0}".format(exc))
