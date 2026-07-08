# -*- coding: utf-8 -*-
import os

from bkbim.core import logging as bklog


class _RecordingSink(bklog.LogSink):
    def __init__(self):
        self.records = []

    def emit(self, level, logger_name, message):
        self.records.append((level, logger_name, message))


def test_logger_dispatches_to_configured_sinks():
    sink = _RecordingSink()
    bklog.configure(sinks=[sink], level=bklog.LEVEL_INFO)
    logger = bklog.get_logger(u"test.logger")

    logger.info(u"hello {0}", u"world")

    assert len(sink.records) == 1
    level, name, message = sink.records[0]
    assert level == bklog.LEVEL_INFO
    assert name == u"test.logger"
    assert message == u"hello world"


def test_logger_respects_level_threshold():
    sink = _RecordingSink()
    bklog.configure(sinks=[sink], level=bklog.LEVEL_WARNING)
    logger = bklog.get_logger(u"test.logger")

    logger.debug(u"suppressed")
    logger.info(u"also suppressed")
    logger.warning(u"kept")

    assert len(sink.records) == 1
    assert sink.records[0][2] == u"kept"


def test_file_sink_never_raises_on_bad_path(tmp_path):
    bad_path = os.path.join(str(tmp_path), "nonexistent-dir", "log.txt")
    sink = bklog.FileSink(bad_path)
    sink.emit(bklog.LEVEL_ERROR, u"test", u"should not raise")


def test_file_sink_writes_line(tmp_path):
    path = os.path.join(str(tmp_path), "log.txt")
    sink = bklog.FileSink(path)
    sink.emit(bklog.LEVEL_ERROR, u"test.logger", u"boom")

    with open(path, "r") as f:
        content = f.read()
    assert "ERROR" in content
    assert "boom" in content
