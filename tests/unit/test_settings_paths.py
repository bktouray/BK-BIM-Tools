# -*- coding: utf-8 -*-
from bkbim.core.settings_paths import office_standards_path, project_settings_path, user_settings_path


class _FakeDoc(object):
    def __init__(self, title):
        self.Title = title


def test_office_standards_path_is_under_appdata_pyrevit():
    path = office_standards_path()
    assert path.endswith(u"bkbim_office_standards.json")
    assert u"pyRevit" in path


def test_office_standards_path_is_stable_across_calls():
    assert office_standards_path() == office_standards_path()


def test_user_settings_path_is_under_appdata_pyrevit():
    path = user_settings_path()
    assert path.endswith(u"bkbim_user_settings.json")
    assert u"pyRevit" in path


def test_user_settings_path_differs_from_office_standards_path():
    assert user_settings_path() != office_standards_path()


def test_project_settings_path_includes_sanitized_doc_title():
    path = project_settings_path(_FakeDoc(u"BKD-2026-008 STH DD"))
    assert u"BKD_2026_008_STH_DD" in path
    assert path.endswith(u".json")


def test_project_settings_path_differs_per_document():
    a = project_settings_path(_FakeDoc(u"Project A"))
    b = project_settings_path(_FakeDoc(u"Project B"))
    assert a != b


def test_project_settings_path_falls_back_for_blank_title():
    path = project_settings_path(_FakeDoc(u""))
    assert u"untitled" in path
