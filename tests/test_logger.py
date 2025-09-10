#!/usr/bin/env python3
"""
Pytest tests for logger module.
"""

import importlib
import os
import re

import pytest


def reload_logger_with_debug(value: str):
    os.environ["DEBUG_MODE"] = value
    import logger as lg

    return importlib.reload(lg)


def test_logger_basic_levels_and_timestamp(capsys):
    lg = reload_logger_with_debug("true")

    # Instance with context
    pl = lg.PrecisionLogger("ModuleCtx")
    pl.info("info message")
    pl.error("error message")
    pl.warning("warn message")
    pl.debug("debug message")  # should print when DEBUG_MODE=true
    pl.msg("msg event")
    pl.server("server event")

    # Module-level convenience API (with and without context)
    lg.info("i1")
    lg.error("e1")
    lg.warning("w1")
    lg.debug("d1")  # uses log("DEBUG", ...) path
    lg.msg("m1")
    lg.server("s1")

    lg.log("with extra", level="INFO", context="CtxA", extra_context="X")
    lg.log("no ctx", level="WARNING")

    out = capsys.readouterr().out.strip().splitlines()
    assert out, "Expected some output from logger"

    # First line should contain a high-precision timestamp like [YYYY-mm-dd HH:MM:SS.NNNNNNNNN]
    assert re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{9}\] ", out[0])

    # Check that various levels and contexts appear
    joined = "\n".join(out)
    assert "[INFO]" in joined
    assert "[ERROR]" in joined
    assert "[WARNING]" in joined
    assert "[DEBUG]" in joined
    assert "[MSG]" in joined
    assert "[SERVER]" in joined
    assert "[ModuleCtx]" in joined
    assert "[CtxA]" in joined and "[X]" in joined


def test_get_logger_and_debug_off_behavior(capsys):
    lg = reload_logger_with_debug("false")

    # get_logger without context returns singleton
    g1 = lg.get_logger()
    g2 = lg.get_logger("")
    assert g1 is g2

    # get_logger with context returns new instance
    cx = lg.get_logger("NewCtx")
    assert cx is not g1

    # debug() should be suppressed when DEBUG_MODE=false
    cx.debug("should not print")
    # Other levels still print
    cx.info("will print")

    out = capsys.readouterr().out
    assert "will print" in out
    assert "should not print" not in out
