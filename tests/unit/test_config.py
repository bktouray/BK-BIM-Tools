# -*- coding: utf-8 -*-
from bkbim.core.config import Config, get_config, set_config


def test_default_config_uses_127_0_0_1_never_localhost():
    cfg = Config()
    assert cfg.mcp_host == u"127.0.0.1"
    assert cfg.mcp_port == 48884
    assert cfg.mcp_base_url == u"http://127.0.0.1:48884"


def test_get_set_config_roundtrip():
    original = get_config()
    try:
        custom = Config(mcp_host=u"127.0.0.1", mcp_port=9999)
        set_config(custom)
        assert get_config() is custom
        assert get_config().mcp_base_url == u"http://127.0.0.1:9999"
    finally:
        set_config(original)
