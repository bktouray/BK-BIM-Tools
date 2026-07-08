# -*- coding: utf-8 -*-
"""Adds lib/ to sys.path so tests can `import bkbim` without installing the package.

Mirrors the pattern used by revit-mcp-python.extension/tests - pure bkbim.core/domain
tests run under plain CPython, no Revit or pyRevit required (SAD Sec 6 testing strategy).
"""

import os
import sys

_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
