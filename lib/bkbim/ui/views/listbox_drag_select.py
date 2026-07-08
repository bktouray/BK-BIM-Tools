# -*- coding: utf-8 -*-
"""Adds click-and-drag multi-select to a WPF ListBox with SelectionMode="Extended",
so the user can drag over multiple items instead of having to hold Ctrl and click
each one individually (product owner, 2026-07-06: "make it possible to just drag
a selection box and select multiple instead of using Ctrl" - for every type-filter
ListBox across the suite: Wall & Opening's wall types, Structural Dimensions'
structural types, and any future one).

WPF's ListBox has no built-in drag-to-multi-select (only single-click, Ctrl+click,
and Shift+click range-select). This wires up preview mouse handlers that, once the
cursor has moved past a small threshold while the left button stays held from a
mouse-down over an item, select every item between that starting item and the one
currently under the cursor - the familiar file-explorer drag-select gesture.
Deliberately layered ON TOP of, not instead of, the existing click/Ctrl+click/
Shift+click behavior: a plain click (press+release with no real movement) is left
alone and falls through to WPF's own default handling, so nothing already working
is taken away.
"""

import clr

clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from System.Windows.Controls import ListBoxItem
from System.Windows.Input import MouseButtonState
from System.Windows.Media import VisualTreeHelper

_DRAG_THRESHOLD_PX = 4.0


def _find_ancestor(element, ancestor_type):
    current = element
    while current is not None and not isinstance(current, ancestor_type):
        current = VisualTreeHelper.GetParent(current)
    return current


def _item_index_at(listbox, point):
    hit = listbox.InputHitTest(point)
    if hit is None:
        return None
    item = _find_ancestor(hit, ListBoxItem)
    if item is None:
        return None
    return listbox.ItemContainerGenerator.IndexFromContainer(item)


def enable_drag_multiselect(listbox):
    """Wires up drag-to-multi-select on `listbox`. Call once per ListBox, after
    its Items have been populated (construction order doesn't otherwise matter).
    """
    state = {u"anchor_index": None, u"anchor_point": None, u"dragging": False}

    def _select_range(anchor, current):
        lo, hi = (anchor, current) if anchor <= current else (current, anchor)
        listbox.SelectedItems.Clear()
        for i in range(lo, hi + 1):
            listbox.SelectedItems.Add(listbox.Items[i])

    def _on_preview_mouse_down(sender, args):
        point = args.GetPosition(listbox)
        index = _item_index_at(listbox, point)
        if index is None:
            return
        state[u"anchor_index"] = index
        state[u"anchor_point"] = point
        state[u"dragging"] = False  # confirmed only once real movement is seen

    def _on_preview_mouse_move(sender, args):
        if args.LeftButton != MouseButtonState.Pressed or state[u"anchor_index"] is None:
            return

        point = args.GetPosition(listbox)
        if not state[u"dragging"]:
            anchor_point = state[u"anchor_point"]
            dx = point.X - anchor_point.X
            dy = point.Y - anchor_point.Y
            if (dx * dx + dy * dy) ** 0.5 < _DRAG_THRESHOLD_PX:
                return
            state[u"dragging"] = True

        index = _item_index_at(listbox, point)
        if index is None:
            return
        _select_range(state[u"anchor_index"], index)
        args.Handled = True

    def _on_preview_mouse_up(sender, args):
        state[u"anchor_index"] = None
        state[u"anchor_point"] = None
        state[u"dragging"] = False

    listbox.PreviewMouseLeftButtonDown += _on_preview_mouse_down
    listbox.PreviewMouseMove += _on_preview_mouse_move
    listbox.PreviewMouseLeftButtonUp += _on_preview_mouse_up
