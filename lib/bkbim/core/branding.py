# -*- coding: utf-8 -*-
"""Single source of truth for suite-wide attribution (2026-07-07, product
owner: "make the author for all of the push buttons and anything else I
create Baboucarr Katim Touray and hard code it so that no one can change
it"). Every pushbutton's `__author__`/`__authors__` must still be a literal
string in its own script.py - pyRevit reads them via static AST parsing
(ast.literal_eval), which throws on an imported name - so this can't be
imported into those fields. It documents the canonical value every one of
those literals must match by hand, and is safe to import anywhere else
(About dialogs, log messages) where real execution applies.
"""

AUTHOR = u"Baboucarr Katim Touray"
COMPANY_NAME = u"BK Designs"
