# -*- coding: utf-8 -*-
"""Single source of truth for suite-wide attribution (2026-07-07, product
owner: "make the author for all of the push buttons and anything else I
create Baboucarr Katim Touray and hard code it so that no one can change
it"). Every pushbutton's `__author__` imports AUTHOR from here instead of
declaring its own literal string, so there is exactly one place this can
ever be edited - never re-type this value directly in a script.py.
"""

AUTHOR = u"Baboucarr Katim Touray"
