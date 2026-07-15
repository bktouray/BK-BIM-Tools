# -*- coding: utf-8 -*-
"""A grid's position and orientation for the Renumber Grids utility (product
owner: "Vertical Grids use A-Z then AA, AB and so forth. Horizontal Grids use
numbers from 1, renumbering start from the furthest left and top grid.").

Pure domain data + logic (ADR-0001) - `ref` is an opaque handle the Revit
adapter attaches and reads back, same convention as GridInfo/GridExtentInfo.
Reuses the ORIENTATION_* vocabulary already established by
bkbim.domain.models.grid_info rather than redefining it.
"""

from bkbim.domain.models.grid_info import ORIENTATION_HORIZONTAL, ORIENTATION_VERTICAL


class GridPositionInfo(object):
    """One straight grid's classification for renumbering: which axis it
    runs along, and its position along the perpendicular axis (`coord`) -
    same coord semantics as GridInfo (avg Y for horizontal, avg X for
    vertical). Angled/curved grids don't get one of these - they can't be
    classified as vertical or horizontal, so the Revit adapter skips them.
    """

    def __init__(self, ref, orientation, coord):
        self.ref = ref
        self.orientation = orientation
        self.coord = coord


def letter_name(index):
    """Converts a 0-based index into a spreadsheet-style letter name:
    0->A, 25->Z, 26->AA, 27->AB, ... (bijective base-26, matches "A-Z then
    AA, AB and so forth"). Uses chr() rather than unichr() - unichr() doesn't
    exist under CPython 3 (this module is unit-tested there), and chr() on
    an ASCII codepoint behaves identically on both engines.
    """
    n = index + 1
    result = u""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = u"{0}{1}".format(chr(65 + remainder), result)
    return result


def plan_renumber(grids):
    """Computes the new name for every classifiable grid in `grids`.

    Vertical grids (letters) are ordered left to right (`coord` ascending -
    lower X is further left) starting at A. Horizontal grids (numbers) are
    ordered top to bottom (`coord` descending - higher Y is further up/top)
    starting at 1 - "renumbering start from the furthest left and top grid."

    :param grids: list[GridPositionInfo]
    :rtype: list[(ref, new_name)]
    """
    verticals = sorted(
        (g for g in grids if g.orientation == ORIENTATION_VERTICAL), key=lambda g: g.coord)
    horizontals = sorted(
        (g for g in grids if g.orientation == ORIENTATION_HORIZONTAL),
        key=lambda g: g.coord, reverse=True)

    plan = [(g.ref, letter_name(i)) for i, g in enumerate(verticals)]
    plan.extend((g.ref, u"{0}".format(i + 1)) for i, g in enumerate(horizontals))
    return plan
