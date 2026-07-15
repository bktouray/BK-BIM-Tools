# -*- coding: utf-8 -*-
"""Module Manifest + registry (Settings platform design Sec 2.1).

Describes a BK BIM Tools module to the platform as data, so future systems
(Settings' About page today; Ribbon/Help/Updater/Plugin Manager/Licensing/
Workspace Manager/Analytics later) can read one thing instead of each
re-deriving module metadata their own way. Per ADR-0002, only modules with a
real settings page today are actually registered - the schema exists for
every module the roadmap names, the registrations don't.

Several fields (ribbon_panel/ribbon_group/commands/dependencies/
required_revit_version/icon_resource/license_requirement/update_channel) are
accepted and stored but read by no code path yet - same disclosed-placeholder
convention as Standard.mep_max_slope_percent=None: the shape is stable now so
it never needs a breaking change later, the behavior arrives only once a real
consumer needs it. The ribbon itself is NOT generated from these manifests -
bundle.yaml stays the ribbon's own source of truth.
"""


class ModuleManifest(object):
    def __init__(self, module_id, name, version, description, category,
                 settings_pages=None, feature_flags=None, help_url=None,
                 developer_contact=None, min_suite_version=None,
                 experimental=False,
                 ribbon_panel=None, ribbon_group=None, commands=None,
                 dependencies=None, required_revit_version=None,
                 icon_resource=None, license_requirement=None,
                 update_channel=None):
        self.module_id = module_id
        self.name = name
        self.version = version
        self.description = description
        self.category = category
        self.settings_pages = list(settings_pages or [])
        self.feature_flags = dict(feature_flags or {})
        self.help_url = help_url
        self.developer_contact = developer_contact
        self.min_suite_version = min_suite_version
        self.experimental = experimental
        # Reserved - see module docstring.
        self.ribbon_panel = ribbon_panel
        self.ribbon_group = ribbon_group
        self.commands = list(commands or [])
        self.dependencies = list(dependencies or [])
        self.required_revit_version = required_revit_version
        self.icon_resource = icon_resource
        self.license_requirement = license_requirement
        self.update_channel = update_channel

    def __repr__(self):
        return u"<ModuleManifest {0} v{1}>".format(self.module_id, self.version)


class ModuleRegistry(object):
    """module_id -> ModuleManifest. Registration order preserved for stable listing."""

    def __init__(self):
        self._manifests = {}
        self._order = []

    def register(self, manifest):
        if manifest.module_id in self._manifests:
            raise ValueError(u"Module already registered: {0}".format(manifest.module_id))
        self._manifests[manifest.module_id] = manifest
        self._order.append(manifest.module_id)

    def get(self, module_id):
        return self._manifests.get(module_id)

    def all(self):
        return [self._manifests[mid] for mid in self._order]


_registry = ModuleRegistry()


def get_module_registry():
    """Returns the process-wide ModuleRegistry singleton."""
    return _registry
