# -*- coding: utf-8 -*-
"""BKBimError hierarchy (SAD Sec 5). Domain/app code raises these, never a bare Exception,
so the app layer can wrap failures in a Result with a predictable, user-facing message.
"""


class BKBimError(Exception):
    """Base class for all BK BIM Tools errors."""


class ValidationError(BKBimError):
    """Raised when input/state fails a precondition (e.g. wrong view type, empty selection)."""


class AdapterError(BKBimError):
    """Raised when the Revit adapter cannot complete an operation against the model."""
