# -*- coding: utf-8 -*-
"""Keep every PCC Blinding pad's Mark in sync with its associated
footing's Mark ("PCC-<footing mark>"), live - fires whenever a footing's
Mark (or anything else about it) is edited directly in Revit (Properties
palette, schedule, anywhere), not just right after running the PCC
Blinding tool. Product owner, 2026-07-14: "I want the mark of the PCC to
auto update when I change the mark of the associated footing."

The pad<->footing link is derived from geometry (matching plan center +
the pad's own top touching the footing's own bottom - see
bkbim.automation.blinding.find_associated_blinding_pad), not a stored id,
since both were placed from the exact same footprint math when the PCC
Blinding tool ran.

Only reacts when Operation == TransactionCommitted - Revit disallows
starting a new transaction from a DocumentChanged handler fired for an
Undo/Redo replay (Operation == TransactionUndone/TransactionRedone), so
those are skipped entirely rather than risking an exception mid-undo. Only
does the more expensive doc-wide pad search when at least one modified
element is actually a non-pad Structural Foundation instance - kept
defensive (swallow everything) so a hook failure can never disrupt the
user's actual edit.
"""
try:
    from pyrevit import EXEC_PARAMS, DB

    from bkbim.automation.blinding import is_blinding_pad, sync_mark_from_footing

    args = getattr(EXEC_PARAMS, "event_args", None) or globals().get("__eventargs__")
    if args is not None and args.Operation == DB.Events.UndoRedoOperationType.TransactionCommitted:
        doc = args.GetDocument()

        footings = []
        for eid in args.GetModifiedElementIds():
            elem = doc.GetElement(eid)
            if elem is None or not isinstance(elem, DB.FamilyInstance):
                continue
            cat = elem.Category
            if cat is None or cat.Id != DB.ElementId(DB.BuiltInCategory.OST_StructuralFoundation):
                continue
            if is_blinding_pad(elem):
                continue  # a pad changing its own Mark must never re-trigger a footing sync
            footings.append(elem)

        if footings:
            t = DB.Transaction(doc, "Sync PCC Blinding Marks")
            t.Start()
            try:
                for footing in footings:
                    sync_mark_from_footing(doc, footing)
                t.Commit()
            except Exception:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
except Exception:
    pass
