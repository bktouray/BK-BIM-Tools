# -*- coding: utf-8 -*-
import pytest

from bkbim.core.errors import AdapterError, BKBimError, ValidationError


def test_validation_and_adapter_errors_are_bkbim_errors():
    assert issubclass(ValidationError, BKBimError)
    assert issubclass(AdapterError, BKBimError)


def test_bkbim_error_is_catchable_as_exception():
    with pytest.raises(BKBimError):
        raise ValidationError(u"empty selection")
