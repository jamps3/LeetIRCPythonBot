"""
GPT Chat Service Module

Provides AI chat functionality using OpenAI's GPT models with conversation history.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import APIError, AuthenticationError, OpenAI, RateLimitError

# Load .env if available
load_dotenv(override=True)


class GPTService:
    """Service for handling GPT chat conversations with history."""

    def __init__(
        self,
        api_key: str,
        history_file: str = "conversation_history.json",
        history_limit: int = 100,
    ):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.history_file = history_file
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
        self.conversation_history = self._load_conversation_history()

    def _load_conversation_history(self) -> List[Dict[str, str]]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                if isinstance(history, list) and all(
                    "role" in m and "content" in m for m in history
                ):
                    return history
            except Exception as e:
                print(f"Error loading conversation history: {e}")
        return self.default_history.copy()

    def _save_conversation_history(self):
        max_total = self.history_limit + 1  # include system prompt
        if len(self.conversation_history) > max_total:
            self.conversation_history = [
                self.conversation_history[0]
            ] + self.conversation_history[-self.history_limit :]
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving conversation history: {e}")

    def _correct_outdated_dates(self, text: str) -> str:
        current_date = datetime.now()
        months = [
            "tammikuuta",
            "helmikuuta",
            "maaliskuuta",
            "huhtikuuta",
            "toukokuuta",
            "kesäkuuta",
            "heinäkuuta",
            "elokuuta",
            "syyskuuta",
            "lokakuuta",
            "marraskuuta",
            "joulukuuta",
        ]
        today_fi = (
            f"{current_date.day}. {months[current_date.month - 1]} {current_date.year}"
        )

        patterns = [
            r"Tänään on \d{1,2}\. \w+ \d{4}",
            r"today is \w+ \d{1,2}, \d{4}",
            r"current date is \d{1,2}\. \w+ \d{4}",
            r"Nykyinen päivämäärä on \d{1,2}\. \w+ \d{4}",
            r"Päivämäärä on \d{1,2}\. \w+ \d{4}",
            r"Olemme nyt \d{1,2}\. \w+ \d{4}",
        ]
        for pat in patterns:
            text = re.sub(pat, today_fi, text, flags=re.IGNORECASE)
        return text

    def _build_transcript(self, latest_user: Dict[str, str]) -> str:
        parts: List[str] = []
        for msg in self.conversation_history:
            if msg["role"] == "system":
                parts.append(f"System: {msg['content']}")
        for msg in [
            m for m in self.conversation_history if m["role"] in ("user", "assistant")
        ][-15:]:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content']}")
        if latest_user:
            parts.append(f"User: {latest_user['content']}")
        # Encourage multiline IRC-friendly output; bot_manager will wrap to ~450 bytes per line
        parts.append(
            "Assistant: (Keep answers concise for IRC. Use multiple short lines separated by newlines. Aim for each line to be under ~450 characters. Avoid markdown.)"
        )
        return "\n".join(parts)

    def chat(self, message: str, sender: str = "user") -> str:
        user_message = {
            "role": "user",
            "content": f"{sender}: {message}" if sender != "user" else message,
        }
        self.conversation_history.append(user_message)

        try:
            transcript = self._build_transcript(user_message)
            response = self.client.responses.create(model=self.model, input=transcript)
            reply = (response.output_text or "").strip()
            if not reply:
                reply = "Sorry, I'm having trouble connecting to the AI service."

            # Uncomment if you want to correct dates in the reply, gpt-5-mini handles dates well
            # reply = self._correct_outdated_dates(reply)

            self.conversation_history.append({"role": "assistant", "content": reply})
            self._save_conversation_history()
            # Format the reply for IRC
            reply = reply.replace("\n", " ").strip()
            return reply

        except RateLimitError:
            return "Sorry, I'm currently rate limited. Please try again later."
        except AuthenticationError:
            return "Authentication error with AI service."
        except APIError as e:
            print(f"OpenAI API error: {e}")
            return f"Sorry, AI service error: {e}"
        except Exception as e:
            print(f"Unexpected error: {e}")
            return f"Sorry, something went wrong: {e}"

    def reset_conversation(self) -> str:
        self.conversation_history = self.default_history.copy()
        self._save_conversation_history()
        return "Conversation history has been reset."

    def get_conversation_stats(self) -> Dict[str, Any]:
        total = len(self.conversation_history) - 1
        users = sum(1 for m in self.conversation_history if m["role"] == "user")
        bots = sum(1 for m in self.conversation_history if m["role"] == "assistant")
        return {
            "total_messages": total,
            "user_messages": users,
            "assistant_messages": bots,
            "history_file": self.history_file,
        }

    def set_system_prompt(self, prompt: str) -> str:
        if (
            self.conversation_history
            and self.conversation_history[0]["role"] == "system"
        ):
            self.conversation_history[0]["content"] = prompt
        else:
            self.conversation_history.insert(0, {"role": "system", "content": prompt})
        self._save_conversation_history()
        return f"System prompt updated: {prompt[:50]}..."


def create_gpt_service(
    api_key: str, history_file="conversation_history.json", history_limit=100
) -> GPTService:
    return GPTService(api_key, history_file, history_limit)
