# -*- coding: utf-8 -*-
"""Code-behind for AutoTagOptions.xaml - a single tag-type picker (Auto Tag
has nothing else to configure per run; view selection happens earlier via
view_selection_prompt.pick_target_views, same as every dimensioning tool).

Columns can offer tag types from TWO distinct tag categories (Column Tags
and Structural Column Tags - see tag_type_reader.py's docstring) - when that
happens each entry is prefixed with its own tag category name so it's
unambiguous which one a given type is; every other Auto Mark category only
ever has one tag category, so no prefix is added there.
"""

import os

from pyrevit import forms

from bkbim.ui.tokens import resolve_tokens_path


class AutoTagOptionsResult(object):
    def __init__(self, tag_type):
        self.tag_type = tag_type


def _label_for(tag_type, distinct_category_names, type_name_fn):
    name = type_name_fn(tag_type)
    if len(distinct_category_names) > 1:
        try:
            return u"{0}: {1}".format(tag_type.Category.Name, name)
        except Exception:
            return name
    return name


class AutoTagOptionsWindow(forms.WPFWindow):
    def __init__(self, tag_types, type_name_fn):
        xaml_path = os.path.join(os.path.dirname(__file__), "AutoTagOptions.xaml")
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, xaml_path)

        self._tag_types = tag_types
        self.result = None

        distinct_category_names = set()
        for tt in tag_types:
            try:
                distinct_category_names.add(tt.Category.Name)
            except Exception:
                pass

        for tt in tag_types:
            self.TagTypeCombo.Items.Add(_label_for(tt, distinct_category_names, type_name_fn))
        if tag_types:
            self.TagTypeCombo.SelectedIndex = 0

        self.RunButton.Click += self._on_run
        self.CancelButton.Click += self._on_cancel

    def _on_run(self, sender, args):
        index = self.TagTypeCombo.SelectedIndex
        tag_type = self._tag_types[index] if 0 <= index < len(self._tag_types) else None
        if tag_type is None:
            self.result = None
        else:
            self.result = AutoTagOptionsResult(tag_type=tag_type)
        self.Close()

    def _on_cancel(self, sender, args):
        self.result = None
        self.Close()


def show_auto_tag_options(tag_types, type_name_fn):
    """Shows the modal options window.

    Returns an AutoTagOptionsResult, or None if the user cancelled.
    """
    window = AutoTagOptionsWindow(tag_types, type_name_fn)
    window.ShowDialog()
    return window.result
