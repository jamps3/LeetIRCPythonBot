"""
GPT Chat Service Module

Provides AI chat functionality using OpenAI's GPT models with conversation history.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import openai


class GPTService:
    """Service for handling GPT chat conversations with history."""

    def __init__(
        self,
        api_key: str,
        history_file: str = "conversation_history.json",
        history_limit: int = 100,
    ):
        """
        Initialize GPT service.

        Args:
            api_key: OpenAI API key
            history_file: Path to conversation history file
            history_limit: Maximum number of messages to keep in conversation history (default: 100)
        """
        self.api_key = api_key
        self.history_file = history_file
        self.history_limit = history_limit

        # Initialize OpenAI client
        self.client = openai.OpenAI(api_key=api_key)

        # Default conversation history with system prompt
        self.default_history = [
            {
                "role": "system",
                "content": "You are a helpful assistant who knows about Finnish beer culture. You respond in a friendly, short and tight manner. If you don't know something, just say so. Keep responses brief, we are on IRC.",
            }
        ]

        # Load existing conversation history
        self.conversation_history = self._load_conversation_history()

    def _load_conversation_history(self) -> List[Dict[str, str]]:
        """Load conversation history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    # Validate history format
                    if isinstance(history, list) and all(
                        isinstance(msg, dict) and "role" in msg and "content" in msg
                        for msg in history
                    ):
                        return history
                    else:
                        print(
                            f"Invalid history format in {self.history_file}, using default"
                        )
                        return self.default_history.copy()
            else:
                print(f"History file {self.history_file} not found, using default")
                return self.default_history.copy()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading conversation history: {e}, using default")
            return self.default_history.copy()

    def _save_conversation_history(self):
        """Save conversation history to file."""
        try:
            # Keep only the configured limit of messages plus system prompt to avoid growing too large
            # history_limit includes both user and assistant messages, but not the system prompt
            max_total_messages = self.history_limit + 1  # +1 for system prompt

            if len(self.conversation_history) > max_total_messages:
                # Keep system prompt (first message) and last N messages up to limit
                messages_to_keep = self.history_limit
                self.conversation_history = [
                    self.conversation_history[0]
                ] + self.conversation_history[-messages_to_keep:]

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving conversation history: {e}")
    
    def _correct_outdated_dates(self, response: str) -> str:
        """
        Correct outdated dates in GPT responses with current date.
        
        Args:
            response: GPT response text
            
        Returns:
            Corrected response with current date
        """
        # Get current date in Finnish format
        current_date = datetime.now()
        
        # Finnish month names
        finnish_months = [
            "tammikuuta", "helmikuuta", "maaliskuuta", "huhtikuuta",
            "toukokuuta", "kesäkuuta", "heinäkuuta", "elokuuta",
            "syyskuuta", "lokakuuta", "marraskuuta", "joulukuuta"
        ]
        
        current_finnish_date = f"{current_date.day}. {finnish_months[current_date.month - 1]} {current_date.year}"
        
        # Common patterns for outdated dates that GPT might use
        outdated_patterns = [
            # Match "Tänään on [date]" pattern
            r"Tänään on \d{1,2}\. \w+ \d{4}",
            # Match "today is [date]" pattern (in case it responds in English)
            r"today is \w+ \d{1,2}, \d{4}",
            # Match "current date is [date]" pattern
            r"current date is \d{1,2}\. \w+ \d{4}",
            # Match "Nykyinen päivämäärä on [date]" pattern
            r"Nykyinen päivämäärä on \d{1,2}\. \w+ \d{4}",
            # Match "Päivämäärä on [date]" pattern
            r"Päivämäärä on \d{1,2}\. \w+ \d{4}",
            # Match "Olemme nyt [date]" pattern
            r"Olemme nyt \d{1,2}\. \w+ \d{4}",
            # Don't match specific outdated date that GPT commonly uses as we don't know if it's in another context
            # r"\b22\. lokakuuta 2023\b",
        ]
        
        corrected_response = response
        
        for pattern in outdated_patterns:
            if re.search(pattern, corrected_response, re.IGNORECASE):
                if "tänään on" in corrected_response.lower():
                    # Replace "Tänään on [old date]" with current date
                    corrected_response = re.sub(
                        r"Tänään on \d{1,2}\. \w+ \d{4}",
                        f"Tänään on {current_finnish_date}",
                        corrected_response,
                        flags=re.IGNORECASE
                    )
                elif "current date" in corrected_response.lower():
                    # Replace "current date is [old date]" with current date
                    corrected_response = re.sub(
                        r"current date is \d{1,2}\. \w+ \d{4}",
                        f"current date is {current_finnish_date}",
                        corrected_response,
                        flags=re.IGNORECASE
                    )
                else:
                    # Replace any standalone old date with current date
                    corrected_response = re.sub(
                        pattern,
                        current_finnish_date,
                        corrected_response,
                        flags=re.IGNORECASE
                    )
                    
        return corrected_response

    def chat(self, message: str, sender: str = "user") -> str:
        """
        Send a message to GPT and get a response.

        Args:
            message: User message
            sender: Username of the sender (for context)

        Returns:
            GPT response string
        """
        try:
            # Add user message to history
            user_message = {
                "role": "user",
                "content": f"{sender}: {message}" if sender != "user" else message,
            }
            self.conversation_history.append(user_message)

            # Make API call to OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Available: gpt-4o, gpt-4.1-mini etc.
                messages=self.conversation_history,
                max_tokens=150,  # Keep responses concise for IRC
                temperature=0.7,  # Adjust for creativity
                presence_penalty=0.2,  # Encourage new topics
                frequency_penalty=0.2,  # Reduce repetition
            )

            # Extract response
            gpt_response = response.choices[0].message.content.strip()
            
            # Apply date correction to fix outdated dates
            corrected_response = self._correct_outdated_dates(gpt_response)

            # Add assistant response to history (use corrected version)
            assistant_message = {"role": "assistant", "content": corrected_response}
            self.conversation_history.append(assistant_message)

            # Save updated history
            self._save_conversation_history()

            return corrected_response

        except openai.RateLimitError:
            return "Sorry, I'm currently rate limited. Please try again later."
        except openai.AuthenticationError:
            return "Authentication error with AI service."
        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
            return "Sorry, I'm having trouble connecting to the AI service."
        except Exception as e:
            print(f"Unexpected error in GPT chat: {e}")
            return "Sorry, something went wrong with my AI processing."

    def reset_conversation(self) -> str:
        """Reset conversation history to default."""
        self.conversation_history = self.default_history.copy()
        self._save_conversation_history()
        return "Conversation history has been reset."

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about the current conversation."""
        total_messages = len(self.conversation_history) - 1  # Exclude system prompt
        user_messages = sum(
            1 for msg in self.conversation_history if msg["role"] == "user"
        )
        assistant_messages = sum(
            1 for msg in self.conversation_history if msg["role"] == "assistant"
        )

        return {
            "total_messages": total_messages,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "history_file": self.history_file,
        }

    def set_system_prompt(self, prompt: str) -> str:
        """Update the system prompt."""
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
    api_key: str,
    history_file: str = "conversation_history.json",
    history_limit: int = 100,
) -> GPTService:
    """
    Factory function to create a GPT service instance.

    Args:
        api_key: OpenAI API key
        history_file: Path to conversation history file
        history_limit: Maximum number of messages to keep in conversation history

    Returns:
        GPTService instance
    """
    return GPTService(api_key, history_file, history_limit)
