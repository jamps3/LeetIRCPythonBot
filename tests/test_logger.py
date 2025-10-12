#!/usr/bin/env python3
"""
Pytest tests for logger module.
"""

import builtins
import re

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

    lg.log("with extra", level="INFO", context="CtxA")
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


def test_safe_print_fallback_and_sanitize(monkeypatch, capsys):
    calls = {"n": 0}

    def fake_print(text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnicodeEncodeError("utf-8", "x", 0, 1, "test")
        # second call succeeds; capture via capsys
        return None

    monkeypatch.setattr(builtins, "print", fake_print)
    # With explicit fallback
    lg.log("🤖 hi", fallback_text="[BOT] hi")
    out = capsys.readouterr().out
    assert "[BOT] hi" in out

    # Without fallback (sanitizes)
    calls["n"] = 0
    lg.log("🤖 hi")
    out2 = capsys.readouterr().out
    # Should print a sanitized version (no emoji)
    assert "hi" in out2
