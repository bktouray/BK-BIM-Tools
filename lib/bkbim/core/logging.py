# -*- coding: utf-8 -*-
"""Structured logging (SAD Sec 4.1). Retires the AutoDims monolith's DEBUG global and
scattered output.print_md calls with named loggers + swappable sinks.
"""

import threading

LEVEL_DEBUG = 10
LEVEL_INFO = 20
LEVEL_WARNING = 30
LEVEL_ERROR = 40

_LEVEL_NAMES = {
    LEVEL_DEBUG: u"DEBUG",
    LEVEL_INFO: u"INFO",
    LEVEL_WARNING: u"WARNING",
    LEVEL_ERROR: u"ERROR",
}


class LogSink(object):
    """Base sink; override emit()."""

    def emit(self, level, logger_name, message):
        raise NotImplementedError


class ConsoleSink(LogSink):
    """Writes to stdout - picked up by pyRevit's output window.

    NOT used by default (see _LoggerFactory) since pyRevit auto-opens its
    Output window the instant anything is printed, and the product owner
    found that popping up on every run - already redundant with the
    forms.alert() result summary every command shows - more annoying than
    useful (2026-07-06: "I have to go close them every time"). Still
    available to opt back into for live debugging via
    `logging.configure(sinks=[ConsoleSink()])`.
    """

    def emit(self, level, logger_name, message):
        print(u"[{0}] {1}: {2}".format(_LEVEL_NAMES.get(level, level), logger_name, message))


class FileSink(LogSink):
    """Appends log lines to a file.

    Stubbed for Phase 0: wired via configure(), not enabled by default. Never raises -
    a logging failure must not crash the caller.
    """

    def __init__(self, path):
        self.path = path

    def emit(self, level, logger_name, message):
        line = u"[{0}] {1}: {2}\n".format(_LEVEL_NAMES.get(level, level), logger_name, message)
        try:
            with open(self.path, "a") as f:
                f.write(line)
        except Exception:
            pass


class Logger(object):
    """Named logger; dispatches to every sink registered on the factory at/above its level."""

    def __init__(self, name, sinks, level):
        self.name = name
        self._sinks = sinks
        self.level = level

    def log(self, level, message, *args):
        if level < self.level:
            return
        text = message.format(*args) if args else message
        for sink in self._sinks:
            sink.emit(level, self.name, text)

    def debug(self, message, *args):
        self.log(LEVEL_DEBUG, message, *args)

    def info(self, message, *args):
        self.log(LEVEL_INFO, message, *args)

    def warning(self, message, *args):
        self.log(LEVEL_WARNING, message, *args)

    def error(self, message, *args):
        self.log(LEVEL_ERROR, message, *args)


class _LoggerFactory(object):
    """Suite-wide registry of sinks; get_logger() hands out named Loggers sharing them."""

    _lock = threading.Lock()

    def __init__(self):
        # Silent by default - see ConsoleSink's docstring for why. log()/info()/
        # etc. calls are still safe no-ops with zero sinks registered.
        self.sinks = []
        self.level = LEVEL_INFO

    def configure(self, sinks=None, level=None):
        with self._lock:
            if sinks is not None:
                self.sinks = list(sinks)
            if level is not None:
                self.level = level

    def get_logger(self, name):
        return Logger(name, self.sinks, self.level)


_factory = _LoggerFactory()


def get_logger(name):
    """Returns a named Logger bound to the suite's current sinks/level."""
    return _factory.get_logger(name)


def configure(sinks=None, level=None):
    """Replaces/extends sinks and level suite-wide. Call once at extension startup."""
    _factory.configure(sinks=sinks, level=level)
