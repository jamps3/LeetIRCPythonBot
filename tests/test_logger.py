#!/usr/bin/env python3
"""
Pytest tests for logger module.
"""

import re

import pytest

import logger as lg


def test_logger_basic_levels_and_timestamp(capsys):
    # Instance with context
    pl = lg.PrecisionLogger("ModuleCtx")
    pl.info("info message")
    pl.error("error message")
    pl.warning("warn message")
    pl.debug("debug message")
    pl.msg("msg event")
    pl.server("server event")

    # Module-level convenience API (with and without context)
    lg.info("i1")
    lg.error("e1")
    lg.warning("w1")
    lg.debug("d1")
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
    assert "[INFO   ]" in joined
    assert "[ERROR  ]" in joined
    assert "[WARNING]" in joined
    assert "[DEBUG  ]" in joined
    assert "[MSG    ]" in joined
    assert "[SERVER ]" in joined
    assert "[ModuleCtx]" in joined
    assert "[CtxA]" in joined and "[X]" in joined
