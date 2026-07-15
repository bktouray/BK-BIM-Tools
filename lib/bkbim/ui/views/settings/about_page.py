# -*- coding: utf-8 -*-
"""Settings page controller for 'About' - read-only suite info + the
registered-module list (Settings platform design Sec 2.1: "Today's only
real manifest consumer is the Settings window's About page"). Reads
ModuleRegistry directly rather than through a page-specific copy, so it
always reflects whatever modules have actually registered a manifest -
currently just Office Standards.
"""

from System.Windows import FontWeights, TextWrapping, Thickness
from System.Windows.Controls import StackPanel, TextBlock

from bkbim.core.branding import AUTHOR, COMPANY_NAME
from bkbim.core.manifest import get_module_registry
from bkbim.core.settings_registry import SettingsPageDescriptor

_LINKTREE_URL = u"https://linktr.ee/itz_bktouray"


class AboutPage(object):
    def build(self):
        panel = StackPanel()

        heading = TextBlock()
        heading.Text = u"BK BIM Tools"
        heading.FontSize = 18
        heading.FontWeight = FontWeights.SemiBold
        panel.Children.Add(heading)

        subheading = TextBlock()
        subheading.Text = u"by {0}".format(COMPANY_NAME)
        subheading.Margin = Thickness(0, 2, 0, 12)
        panel.Children.Add(subheading)

        author_block = TextBlock()
        author_block.Text = u"Author: {0}".format(AUTHOR)
        author_block.Margin = Thickness(0, 0, 0, 4)
        panel.Children.Add(author_block)

        link_block = TextBlock()
        link_block.Text = u"Links & contact: {0}".format(_LINKTREE_URL)
        link_block.TextWrapping = TextWrapping.Wrap
        link_block.Margin = Thickness(0, 0, 0, 16)
        panel.Children.Add(link_block)

        modules_heading = TextBlock()
        modules_heading.Text = u"Registered modules"
        modules_heading.FontWeight = FontWeights.SemiBold
        modules_heading.Margin = Thickness(0, 0, 0, 4)
        panel.Children.Add(modules_heading)

        manifests = get_module_registry().all()
        if not manifests:
            empty_block = TextBlock()
            empty_block.Text = u"(none registered yet)"
            panel.Children.Add(empty_block)
        else:
            for manifest in manifests:
                row = TextBlock()
                row.Text = u"{0}  v{1} - {2}".format(manifest.name, manifest.version, manifest.description)
                row.TextWrapping = TextWrapping.Wrap
                row.Margin = Thickness(0, 0, 0, 4)
                panel.Children.Add(row)

        return panel


def register(registry):
    registry.register(SettingsPageDescriptor(
        page_id=u"about",
        category=u"About",
        title=u"About",
        description=u"Suite information and registered modules.",
        page_factory=AboutPage,
        keywords=[u"about", u"version", u"author", u"help"],
    ))
