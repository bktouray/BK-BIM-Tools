# -*- coding: utf-8 -*-
"""Modal filtering workspace; Revit actions run only after the window closes."""
import os
from pyrevit import forms
from bkbim.ui.tokens import resolve_tokens_path
from bkbim.app.commands.master_filter_command import run
from bkbim.domain.filtering.rules import OPERATORS, validate_rule
from bkbim.domain.filtering.choices import cascade


class MasterFilterWindow(forms.WPFWindow):
    def __init__(self, adapter):
        self.merge_resource_dict(resolve_tokens_path())
        forms.WPFWindow.__init__(self, os.path.join(os.path.dirname(__file__), "MasterFilter.xaml"))
        self.adapter = adapter
        self.result = None
        self.records = []
        self.rules = []
        self._parameter_keys = []
        self._loading = False
        self._lists = (("category", self.CategoryList), ("family", self.FamilyList),
                       ("type", self.TypeList), ("level", self.LevelList))
        for label in ("Active view", "Current selection", "Entire project"):
            self.ScopeCombo.Items.Add(label)
        for operator in OPERATORS:
            self.OperatorCombo.Items.Add(operator)
        self.OperatorCombo.SelectedIndex = 0
        for mode in ("Match all rules", "Match any rule"):
            self.ModeCombo.Items.Add(mode)
        self.ModeCombo.SelectedIndex = 0
        self.ScopeCombo.SelectionChanged += self._load
        for key, control in self._lists:
            control.SelectionChanged += self._on_choice_changed
        self.ModeCombo.SelectionChanged += self._invalidate
        self.AddRuleButton.Click += self._add_rule
        self.RemoveRuleButton.Click += self._remove_rule
        self.ClearButton.Click += self._clear
        self.PreviewButton.Click += self._preview
        self.SelectButton.Click += lambda s, e: self._finish("Select")
        self.ShowButton.Click += lambda s, e: self._finish("Show")
        self.IsolateButton.Click += lambda s, e: self._finish("Isolate")
        self.CancelButton.Click += lambda s, e: self.Close()
        self.ScopeCombo.SelectedIndex = 0

    def _invalidate(self, sender=None, args=None):
        if self._loading:
            return
        self.PreviewList.Items.Clear()
        self.CountText.Text = u"{0} candidate elements. Preview to see matches.".format(
            len(getattr(self, "_candidates", self.records)))
        self.StatusText.Text = u""

    def _on_choice_changed(self, sender=None, args=None):
        if self._loading:
            return
        self._refresh_choices()
        self._invalidate()

    def _refresh_choices(self):
        selections = dict((key, list(control.SelectedItems)) for key, control in self._lists)
        options, selected, candidates, parameter_keys = cascade(self.records, selections)
        previous_parameter = None
        index = self.ParameterCombo.SelectedIndex
        if 0 <= index < len(self._parameter_keys):
            previous_parameter = self._parameter_keys[index]
        self._loading = True
        try:
            for key, control in self._lists:
                # Leave unchanged controls intact to preserve Ctrl/Shift selection.
                if list(control.Items) == options[key]:
                    continue
                control.Items.Clear()
                for label in options[key]:
                    control.Items.Add(label)
                for label in selected[key]:
                    control.SelectedItems.Add(label)
            entries = sorted(
                ((key, self.adapter.parameters[key]) for key in parameter_keys),
                key=lambda pair: pair[1].lower())
            self.ParameterCombo.Items.Clear()
            self._parameter_keys = [entry[0] for entry in entries]
            for key, label in entries:
                self.ParameterCombo.Items.Add(label)
            if previous_parameter in self._parameter_keys:
                self.ParameterCombo.SelectedIndex = self._parameter_keys.index(previous_parameter)
            elif entries:
                self.ParameterCombo.SelectedIndex = 0
            self._candidates = candidates
        finally:
            self._loading = False

    def _load(self, sender, args):
        self._loading = True
        self.records = []
        self._candidates = []
        self.rules = []
        self.RulesList.Items.Clear()
        self.ParameterCombo.Items.Clear()
        for key, control in self._lists:
            control.Items.Clear()
        try:
            self.records = self.adapter.read(self.ScopeCombo.SelectedItem)
            self._refresh_choices()
            error = u""
        except Exception as exc:
            self.records = []
            self._parameter_keys = []
            self.ParameterCombo.Items.Clear()
            for key, control in self._lists:
                control.Items.Clear()
            error = u"Could not read scope: {0}".format(exc)
        finally:
            self._loading = False
        self._invalidate()
        self.StatusText.Text = error

    def _add_rule(self, sender, args):
        if self.ParameterCombo.SelectedIndex < 0:
            self.StatusText.Text = "Choose a parameter first."
            return
        rule = {"parameter": self._parameter_keys[self.ParameterCombo.SelectedIndex],
                "operator": self.OperatorCombo.SelectedItem, "value": self.ValueBox.Text}
        try:
            validate_rule(rule)
        except ValueError as exc:
            self.StatusText.Text = str(exc)
            return
        self.rules.append(rule)
        self.RulesList.Items.Add(u"{0} | {1} | {2}".format(
            self.ParameterCombo.SelectedItem, rule["operator"], rule["value"]))
        self._invalidate()

    def _remove_rule(self, sender, args):
        index = self.RulesList.SelectedIndex
        if index >= 0:
            del self.rules[index]
            self.RulesList.Items.RemoveAt(index)
            self._invalidate()

    def _clear(self, sender, args):
        self._loading = True
        try:
            for key, control in self._lists:
                control.UnselectAll()
        finally:
            self._loading = False
        self.rules = []
        self.RulesList.Items.Clear()
        self.ValueBox.Text = u""
        self._refresh_choices()
        self._invalidate()

    def _evaluate(self):
        criteria = dict((key, list(control.SelectedItems)) for key, control in self._lists)
        return run(self.records, criteria, self.rules,
                   "all" if self.ModeCombo.SelectedIndex == 0 else "any", self.adapter.value)

    def _preview(self, sender=None, args=None):
        result = self._evaluate()
        self.PreviewList.Items.Clear()
        self.StatusText.Text = result.message
        if not result.success:
            return None
        self.CountText.Text = result.message
        for row in result.value[:500]:
            self.PreviewList.Items.Add(u"{id} | {category} | {family} | {type} | {level}".format(**row))
        if len(result.value) > 500:
            self.StatusText.Text += " Preview shows the first 500; actions include every match."
        return result.value

    def _finish(self, action):
        rows = self._preview()
        if not rows:
            if rows is not None:
                self.StatusText.Text = "No matches. Adjust your filters; selection is preserved."
            return
        self.result = (rows, action)
        self.Close()
