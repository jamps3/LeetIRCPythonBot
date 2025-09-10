#!/usr/bin/env python3
"""
GPT Service Test Suite - Pytest

Covers all code paths in services/gpt_service.py to achieve 100% coverage.
"""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

# Ensure project root on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

# Import the module under test via package path to ensure coverage gets collected
from services import gpt_service as gpt_mod
from services.gpt_service import GPTService, create_gpt_service


class FakeResponse:
    def __init__(self, text: str | None):
        self.output_text = text


class FakeClient:
    def __init__(self, text: str | None = "ok"):
        self._text = text
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, model: str, input: str):  # noqa: A002 - match signature in code
        # Minimal API-compatible return
        return FakeResponse(self._text)


def make_service(
    tmp_path,
    *,
    api_key="k",
    model_env: str | None = None,
    history_file_name="hist.json",
    history_limit=100,
    reply_text="ok",
):
    # Control environment with complete isolation
    env_patch = {
        "OPENAI_API_KEY": api_key,
    }
    if model_env is not None:
        env_patch["OPENAI_MODEL"] = model_env

    history_file = tmp_path / history_file_name

    with patch.object(gpt_mod, "OpenAI", return_value=FakeClient(reply_text)):
        # Use complete environment isolation - clear=True means only our patch is used
        if model_env is None:
            # When model_env is None, completely exclude OPENAI_MODEL from environment
            with patch.dict(os.environ, env_patch, clear=True):
                svc = GPTService(
                    api_key="",
                    history_file=str(history_file),
                    history_limit=history_limit,
                )
        else:
            # When model_env is set, include it in the environment
            with patch.dict(os.environ, env_patch, clear=True):
                svc = GPTService(
                    api_key="",
                    history_file=str(history_file),
                    history_limit=history_limit,
                )
    return svc, history_file


def test_init_uses_env_api_key_and_model(tmp_path):
    svc, _ = make_service(tmp_path, api_key="ENV_KEY", model_env="my-model")
    assert svc.api_key == "ENV_KEY"
    assert svc.model == "my-model"
    assert svc.conversation_history and svc.conversation_history[0]["role"] == "system"


def test_init_model_default_when_env_missing(tmp_path):
    svc, _ = make_service(tmp_path, api_key="ENV_KEY", model_env=None)
    assert svc.model == "gpt-5-mini"


def test_load_conversation_history_missing_file_falls_back_to_default(tmp_path):
    svc, history_file = make_service(tmp_path)[0:2]
    assert not os.path.exists(history_file)
    # On fresh service, conversation_history was loaded in __init__ already
    assert svc.conversation_history[0]["role"] == "system"


def test_load_conversation_history_valid_file(tmp_path):
    svc, history_file = make_service(tmp_path)[0:2]
    # Write a valid history
    data = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    history_file.write_text(json.dumps(data), encoding="utf-8")
    # Force reload
    loaded = GPTService(api_key="", history_file=str(history_file)).conversation_history
    assert loaded == data


def test_load_conversation_history_corrupt_file(tmp_path):
    svc, history_file = make_service(tmp_path)[0:2]
    history_file.write_text("{", encoding="utf-8")  # invalid JSON
    # Force reload - should fallback to default
    loaded = GPTService(api_key="", history_file=str(history_file)).conversation_history
    assert loaded[0]["role"] == "system"


def test_load_conversation_history_invalid_structure(tmp_path):
    svc, history_file = make_service(tmp_path)[0:2]
    history_file.write_text(
        json.dumps({"role": "user"}), encoding="utf-8"
    )  # not a list
    loaded = GPTService(api_key="", history_file=str(history_file)).conversation_history
    assert loaded[0]["role"] == "system"


def test_save_conversation_history_trims_to_limit(tmp_path):
    svc, history_file = make_service(tmp_path, history_limit=2)
    # Create many messages
    svc.conversation_history = [
        {"role": "system", "content": "sys"},
    ] + [{"role": "user", "content": f"u{i}"} for i in range(10)]

    svc._save_conversation_history()

    saved = json.loads(history_file.read_text(encoding="utf-8"))
    # system + last 2 user messages
    assert len(saved) == 3
    assert saved[0]["role"] == "system"
    assert [m["content"] for m in saved[1:]] == ["u8", "u9"]


def test_save_conversation_history_handles_io_error(tmp_path, monkeypatch):
    svc, history_file = make_service(tmp_path)

    def bad_open(*args, **kwargs):
        raise OSError("fail")

    # Mock the built-in open function
    import builtins

    monkeypatch.setattr(builtins, "open", bad_open)
    # Should not raise
    svc._save_conversation_history()


def test_build_transcript_includes_system_and_last_15_and_prompt(tmp_path):
    svc, _ = make_service(tmp_path)
    # Build history: 1 system + 20 alternating messages
    svc.conversation_history = [{"role": "system", "content": "SYS"}]
    for i in range(20):
        role = "user" if i % 2 == 0 else "assistant"
        svc.conversation_history.append({"role": role, "content": f"m{i}"})

    transcript = svc._build_transcript({"role": "user", "content": "latest"})
    lines = transcript.split("\n")
    # System line present
    assert any(line.startswith("System: ") for line in lines)
    # Only last 15 user/assistant messages appear (20 -> take last 15 m5..m19)
    joined = "\n".join(lines)
    assert "m4" not in joined and "m5" in joined and "m19" in joined
    # Latest user included
    assert any(line.endswith("latest") for line in lines)
    # Instruction line present
    assert lines[-1].startswith("Assistant: (Keep answers concise for IRC.")


def test_chat_normal_flow_and_reply_formatting(tmp_path):
    svc, _ = make_service(tmp_path, reply_text="Hello\nWorld")
    out = svc.chat("What up?")
    assert out == "Hello World"  # newline replaced by space
    # History appended and saved
    assert svc.conversation_history[-1]["role"] == "assistant"


def test_chat_empty_reply_uses_default_error_message(tmp_path):
    svc, _ = make_service(tmp_path, reply_text=None)
    out = svc.chat("Hi")
    assert out.startswith("Sorry, I'm having trouble connecting")


def test_chat_ratelimit_error(tmp_path):
    svc, _ = make_service(tmp_path)

    def raise_rl(*a, **k):
        # Create a minimal mock response object for RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        raise gpt_mod.RateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit"}},
        )

    svc.client.responses.create = raise_rl
    assert svc.chat("hi").startswith("Sorry, I'm currently rate limited")


def test_chat_auth_error(tmp_path):
    svc, _ = make_service(tmp_path)

    def raise_auth(*a, **k):
        mock_response = Mock()
        mock_response.status_code = 401
        raise gpt_mod.AuthenticationError(
            "Authentication failed",
            response=mock_response,
            body={"error": {"message": "Auth error"}},
        )

    svc.client.responses.create = raise_auth
    assert svc.chat("hi").startswith("Authentication error with AI service")


def test_chat_api_error(tmp_path, capsys):
    svc, _ = make_service(tmp_path)

    def raise_api(*a, **k):
        mock_request = Mock()
        mock_request.url = "https://api.openai.com/v1/chat/completions"
        mock_request.method = "POST"
        raise gpt_mod.APIError(
            "API Error occurred",
            request=mock_request,
            body={"error": {"message": "API error"}},
        )

    svc.client.responses.create = raise_api
    msg = svc.chat("hi")
    assert msg.startswith("Sorry, AI service error:")


def test_chat_unexpected_error(tmp_path, capsys):
    svc, _ = make_service(tmp_path)

    def raise_err(*a, **k):
        raise RuntimeError("x")

    svc.client.responses.create = raise_err
    msg = svc.chat("hi")
    assert msg.startswith("Sorry, something went wrong:")


def test_reset_conversation(tmp_path):
    svc, _ = make_service(tmp_path)
    svc.conversation_history.append({"role": "user", "content": "x"})
    with patch.object(svc, "_save_conversation_history") as sp:
        res = svc.reset_conversation()
        sp.assert_called_once()
    assert res == "Conversation history has been reset."
    assert (
        svc.conversation_history[0]["role"] == "system"
        and len(svc.conversation_history) == 1
    )


def test_get_conversation_stats(tmp_path):
    svc, _ = make_service(tmp_path)
    svc.conversation_history.extend(
        [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ]
    )
    stats = svc.get_conversation_stats()
    assert stats["total_messages"] == 2
    assert stats["user_messages"] == 1
    assert stats["assistant_messages"] == 1


def test_set_system_prompt_update_and_insert(tmp_path):
    svc, _ = make_service(tmp_path)
    # Update existing
    msg = svc.set_system_prompt("NEW PROMPT")
    assert svc.conversation_history[0]["content"] == "NEW PROMPT"
    assert msg.startswith("System prompt updated: NEW PROMPT")

    # Remove system and test insert
    svc.conversation_history.pop(0)
    svc.set_system_prompt("AGAIN")
    assert svc.conversation_history[0]["role"] == "system"
    assert svc.conversation_history[0]["content"] == "AGAIN"


def test_factory_function_returns_service(tmp_path):
    with patch.object(gpt_mod, "OpenAI", return_value=FakeClient("ok")):
        svc = create_gpt_service(
            api_key="X", history_file=str(tmp_path / "h.json"), history_limit=5
        )
    assert isinstance(svc, GPTService)


def test_chat_with_sender_parameter(tmp_path):
    """Test chat method with sender parameter formats message correctly"""
    svc, _ = make_service(tmp_path, reply_text="response")
    out = svc.chat("hello", sender="alice")
    assert out == "response"
    # Check that message was formatted with sender
    user_msg = svc.conversation_history[-2]  # -1 is assistant, -2 is user
    assert user_msg["content"] == "alice: hello"


def test_chat_without_sender_parameter(tmp_path):
    """Test chat method without sender parameter"""
    svc, _ = make_service(tmp_path, reply_text="response")
    out = svc.chat("hello")  # no sender param, defaults to "user"
    assert out == "response"
    # Check that message was not formatted with sender when sender="user"
    user_msg = svc.conversation_history[-2]
    assert user_msg["content"] == "hello"


def test_load_conversation_history_missing_role_or_content(tmp_path):
    """Test loading history with invalid message structure (missing role/content)"""
    svc, history_file = make_service(tmp_path)[0:2]
    # Write history missing required fields
    invalid_data = [
        {"role": "system"},  # missing content
        {"content": "hello"},  # missing role
    ]
    history_file.write_text(json.dumps(invalid_data), encoding="utf-8")
    loaded = GPTService(api_key="", history_file=str(history_file)).conversation_history
    # Should fallback to default
    assert loaded[0]["role"] == "system"
    assert len(loaded) == 1


def test_build_transcript_with_empty_latest_user(tmp_path):
    """Test _build_transcript with empty latest_user parameter"""
    svc, _ = make_service(tmp_path)
    transcript = svc._build_transcript({})
    lines = transcript.split("\n")
    # Should still include system and instruction lines
    assert any(line.startswith("System: ") for line in lines)
    assert lines[-1].startswith("Assistant: (Keep answers concise for IRC.")


def test_save_conversation_history_no_trimming_needed(tmp_path):
    """Test save when history is within limit"""
    svc, history_file = make_service(tmp_path, history_limit=10)
    # History is small, no trimming needed
    svc.conversation_history = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    svc._save_conversation_history()
    saved = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(saved) == 2
    assert saved[0]["role"] == "system"
    assert saved[1]["content"] == "hi"


def test_explicit_api_key_overrides_env(tmp_path):
    """Test that explicit API key parameter overrides environment"""
    env_patch = {"OPENAI_API_KEY": "env_key"}
    history_file = tmp_path / "hist.json"

    with patch.object(gpt_mod, "OpenAI", return_value=FakeClient("ok")):
        with patch.dict(os.environ, env_patch, clear=False):
            svc = GPTService(api_key="explicit_key", history_file=str(history_file))

    assert svc.api_key == "explicit_key"
