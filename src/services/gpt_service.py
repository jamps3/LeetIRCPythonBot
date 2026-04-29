"""
GPT Chat Service Module

Provides AI chat functionality using OpenAI's GPT models with conversation history.
"""

import json
import os
from typing import Any, Dict, List

from openai import APIError as OpenAIAPIError
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import OpenAI
from openai import RateLimitError as OpenAIRateLimitError

from src.config import CONVERSATION_HISTORY_FILE
from src.logger import get_logger

logger = get_logger("GPTService")


# Custom exception classes that properly inherit from Exception
class RateLimitError(Exception):
    """Rate limit error for AI service."""

    def __init__(self, message, response=None, body=None):
        super().__init__(message)
        self.response = response
        self.body = body


class AuthenticationError(Exception):
    """Authentication error for AI service."""

    def __init__(self, message, response=None, body=None):
        super().__init__(message)
        self.response = response
        self.body = body


class APIError(Exception):
    """API error for AI service."""

    def __init__(self, message, request=None, body=None):
        super().__init__(message)
        self.request = request
        self.body = body


class GPTService:
    """Service for handling GPT chat conversations with history."""

    def __init__(
        self,
        api_key: str = "",
        history_file: str = None,
        history_limit: int = 100,
    ):
        # Prefer explicitly provided key; fall back to environment (.env)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.4")
        self.history_file = (
            history_file if history_file is not None else CONVERSATION_HISTORY_FILE
        )
        self.history_limit = history_limit

        self.default_history = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant who knows about Finnish beer culture. "
                    "Respond in a friendly, short and tight manner. "
                    "If you don't know something, just say so. "
                    "Keep responses brief, we are on IRC."
                ),
            }
        ]
        self.conversation_histories = self._load_conversation_histories()

    def _load_conversation_histories(self) -> Dict[str, List[Dict[str, str]]]:
        """Load conversation histories from file, supporting both old format and new channel-specific format."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Handle old single-history format for migration
                if isinstance(data, list):
                    # Migrate old format to new format with "global" key
                    histories = {"global": data}
                    # Save migrated format
                    self._save_conversation_histories(histories)
                    return histories
                elif isinstance(data, dict):
                    # New format - validate each history
                    validated_histories = {}
                    for key, history in data.items():
                        if isinstance(history, list) and all(
                            isinstance(msg, dict) and "role" in msg and "content" in msg
                            for msg in history
                        ):
                            validated_histories[key] = history
                        else:
                            get_logger(__name__).warning(
                                f"Invalid history format for {key}, skipping"
                            )
                    # If no valid histories found, return default
                    return (
                        validated_histories
                        if validated_histories
                        else {"global": self.default_history.copy()}
                    )
            except Exception as e:
                get_logger(__name__).error(f"Error loading conversation histories: {e}")

        # Return default history for global key
        return {"global": self.default_history.copy()}

    def _save_conversation_histories(self):
        """Save all conversation histories to file, trimming each history first."""
        # Trim all histories before saving
        trimmed_histories = {}
        for key, history in self.conversation_histories.items():
            trimmed_histories[key] = self._trim_conversation_history(history)

        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(trimmed_histories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            get_logger(__name__).error(f"Error saving conversation histories: {e}")

    def _get_conversation_history(
        self, network: str = None, channel: str = None
    ) -> List[Dict[str, str]]:
        """Get conversation history for specific network/channel."""
        key = f"{network}/{channel}" if network and channel else "global"
        return self.conversation_histories.get(key, self.default_history.copy())

    def _set_conversation_history(
        self, history: List[Dict[str, str]], network: str = None, channel: str = None
    ):
        """Set conversation history for specific network/channel."""
        key = f"{network}/{channel}" if network and channel else "global"
        # Trim history to fit limits
        trimmed_history = self._trim_conversation_history(history)
        self.conversation_histories[key] = trimmed_history
        self._save_conversation_histories()

    def _trim_conversation_history(
        self, history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Trim conversation history to fit within limits."""
        max_total = self.history_limit + 1  # include system prompt
        if len(history) > max_total:
            # Keep system prompt and most recent messages
            return [history[0]] + history[-(max_total - 1) :]  # noqa: E203
        return history

    def _build_transcript(
        self, latest_user: Dict[str, str], network: str = None, channel: str = None
    ) -> str:
        # Get the conversation history for this network/channel
        history = self._get_conversation_history(network, channel)

        parts: List[str] = []
        for msg in history:
            if msg["role"] == "system":
                parts.append(f"System: {msg['content']}")

        # Add teachings context if available (max 100 items total with conversation history)
        teachings_context = self._get_teachings_context(
            max_items=100, network=network, channel=channel
        )
        if teachings_context:
            parts.append(teachings_context)

        for msg in [m for m in history if m["role"] in ("user", "assistant")][-15:]:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content']}")
        if latest_user:
            parts.append(f"User: {latest_user['content']}")
        # Encourage multiline IRC-friendly output; bot_manager will wrap to ~450 bytes per line
        parts.append(
            "Assistant: (Keep answers concise for IRC. Use multiple short lines separated by newlines. Aim for each line to be under ~450 characters. Avoid markdown.)"
        )
        return "\n".join(parts)

    def _get_teachings_context(
        self, max_items: int = 100, network: str = None, channel: str = None
    ) -> str:
        """Get teachings formatted for AI context."""
        try:
            from src.word_tracking.data_manager import get_data_manager

            data_manager = get_data_manager()
            teachings = data_manager.get_teachings_for_context(
                max_items, network, channel
            )
            if teachings:
                return "Teachings:\n" + "\n".join(
                    f"- {content}" for content in teachings
                )
        except Exception as e:
            get_logger(__name__).error(f"Error loading teachings for context: {e}")
        return ""

    def chat(
        self,
        message: str,
        sender: str = "user",
        network: str = None,
        channel: str = None,
    ) -> str:
        # Get the conversation history for this network/channel
        history = self._get_conversation_history(network, channel)

        user_message = {
            "role": "user",
            "content": f"{sender}: {message}" if sender != "user" else message,
        }
        history.append(user_message)

        try:
            transcript = self._build_transcript(user_message, network, channel)
            response = self.client.responses.create(model=self.model, input=transcript)
            reply = (response.output_text or "").strip()
            if not reply:
                reply = "Sorry, I'm having trouble connecting to the AI service."

            history.append({"role": "assistant", "content": reply})
            self._set_conversation_history(history, network, channel)
            # Format the reply for IRC
            reply = reply.replace("\n", " ").strip()
            return reply

        except RateLimitError:
            return "Sorry, I'm currently rate limited. Please try again later."
        except AuthenticationError:
            return "Authentication error with AI service."
        except APIError as e:
            get_logger(__name__).error(f"OpenAI API error: {e}")
            return f"Sorry, AI service error: {e}"
        except Exception as e:
            get_logger(__name__).error(f"Unexpected error: {e}")
            return f"Sorry, something went wrong: {e}"

    def reset_conversation(self, network: str = None, channel: str = None) -> str:
        """Reset conversation history for specific network/channel or global."""
        self._set_conversation_history(self.default_history.copy(), network, channel)
        return "Conversation history has been reset."

    def get_conversation_stats(
        self, network: str = None, channel: str = None
    ) -> Dict[str, Any]:
        """Get conversation statistics for specific network/channel or global."""
        history = self._get_conversation_history(network, channel)
        total = len(history) - 1  # Subtract system message
        users = sum(1 for m in history if m["role"] == "user")
        bots = sum(1 for m in history if m["role"] == "assistant")
        return {
            "total_messages": total,
            "user_messages": users,
            "assistant_messages": bots,
            "history_file": self.history_file,
        }

    def set_system_prompt(
        self, prompt: str, network: str = None, channel: str = None
    ) -> str:
        """Set system prompt for specific network/channel or global."""
        history = self._get_conversation_history(network, channel)
        if history and history[0]["role"] == "system":
            history[0]["content"] = prompt
        else:
            history.insert(0, {"role": "system", "content": prompt})
        self._set_conversation_history(history, network, channel)
        return f"System prompt updated: {prompt[:50]}..."


def create_gpt_service(
    api_key: str, history_file=None, history_limit=100
) -> GPTService:
    return GPTService(api_key, history_file, history_limit)
