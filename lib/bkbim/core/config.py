# -*- coding: utf-8 -*-
"""Immutable, environment-facing configuration (SAD Sec 4.1).

Distinct from core.settings: Config is developer/deployment-facing (endpoints, engine
selection, paths) and is not meant to be edited by end users through the UI.
"""


class Config(object):
    """Frozen-by-convention config snapshot. Build a new one to change values; don't mutate."""

    def __init__(self, mcp_host=u"127.0.0.1", mcp_port=48884, engine=u"ironpython2.7",
                 extension_root=None):
        # CLAUDE.md: always 127.0.0.1 for the Routes server, never localhost.
        self.mcp_host = mcp_host
        self.mcp_port = mcp_port
        self.engine = engine
        self.extension_root = extension_root

    @property
    def mcp_base_url(self):
        return u"http://{0}:{1}".format(self.mcp_host, self.mcp_port)


_config = Config()


def get_config():
    """Returns the process-wide Config. Phase 0: a single default; later may read a file."""
    return _config


def set_config(config):
    """Replaces the process-wide Config (e.g. at extension startup)."""
    global _config
    _config = config
