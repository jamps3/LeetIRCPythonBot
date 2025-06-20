"""
Real Tamagotchi Bot

Implements actual tamagotchi functionality with emotional states, levels,
and responses to trigger words from tamagotchi.json.
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from .data_manager import DataManager


class TamagotchiBot:
    """A virtual pet tamagotchi that responds to trigger words and has emotional states."""

    def __init__(
        self, data_manager: DataManager, tamagotchi_config_file: str = "tamagotchi.json"
    ):
        """
        Initialize the tamagotchi bot.

        Args:
            data_manager: DataManager instance for data persistence
            tamagotchi_config_file: Path to tamagotchi trigger words configuration
        """
        self.data_manager = data_manager
        self.config_file = tamagotchi_config_file

        # Load trigger words configuration
        self.trigger_words = self._load_trigger_words()

        # Emotional state mappings
        self.mood_responses = {
            "very_happy": ["😊", "🥰", "😍", "🤗", "✨"],
            "happy": ["😊", "😄", "🙂", "😌", "🤍"],
            "neutral": ["😐", "🤔", "💭", "👀", "📝"],
            "sad": ["😢", "😔", "🥺", "💧", "😿"],
            "very_sad": ["😭", "💔", "😩", "😞", "🖤"],
            "angry": ["😠", "😡", "💢", "🔥", "😤"],
            "sick": ["🤢", "🤒", "😵", "💊", "🏥"],
            "hungry": ["😋", "🍽️", "🤤", "🍕", "🍰"],
            "tired": ["😴", "💤", "😪", "🥱", "🛏️"],
        }

        # Level requirements (experience needed for each level)
        self.level_requirements = [0, 10, 25, 50, 100, 200, 400, 800, 1600, 3200]

    def _load_trigger_words(self) -> Dict[str, List[str]]:
        """Load trigger words from configuration file."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading tamagotchi config: {e}")
            return {
                "ruoka": ["pizza", "leipä", "ateria"],
                "rakkaus": ["rakkaus", "sydän", "ihana"],
                "raha": ["raha", "palkka", "euro"],
                "päihteet": ["kalja", "viina", "alkoholi"],
                "viha": ["viha", "ärsytys", "kiukku"],
                "onnellisuus": ["ilo", "nauru", "onnellinen"],
            }

    def process_message(self, server: str, nick: str, text: str) -> Tuple[bool, str]:
        """
        Process a message for tamagotchi trigger words.

        Args:
            server: Server name
            nick: User nickname
            text: Message text

        Returns:
            Tuple of (should_respond, response_message)
        """
        # Check for trigger words
        triggered_categories = self._find_trigger_words(text)

        if not triggered_categories:
            return False, ""

        # Update tamagotchi state based on triggered categories
        response = self._update_state(server, triggered_categories, nick)

        return True, response

    def _find_trigger_words(self, text: str) -> List[str]:
        """
        Find trigger word categories in the text.

        Args:
            text: Message text to analyze

        Returns:
            List of triggered categories
        """
        text_lower = text.lower()
        triggered = []

        for category, words in self.trigger_words.items():
            for word in words:
                if word.lower() in text_lower:
                    triggered.append(category)
                    break  # Only trigger each category once per message

        return triggered

    def _update_state(
        self, server: str, triggered_categories: List[str], interactor: str = None
    ) -> str:
        """
        Update tamagotchi state based on triggered categories.

        Args:
            server: Server name
            triggered_categories: List of triggered categories
            interactor: Nick of the person who triggered the response

        Returns:
            Response message
        """
        state = self._get_state(server)
        old_level = self._calculate_level(state["experience"])

        response_parts = []
        experience_gained = 0

        for category in triggered_categories:
            category_response, exp_gain, state_changes = self._process_category(
                category, state
            )

            if category_response:
                response_parts.append(category_response)

            experience_gained += exp_gain

            # Apply state changes
            for attr, change in state_changes.items():
                if attr in state:
                    state[attr] = max(0, min(100, state[attr] + change))

        # Update experience and level
        state["experience"] += experience_gained
        new_level = self._calculate_level(state["experience"])

        # Update last interaction
        state["last_interaction"] = datetime.now().isoformat()

        # Calculate mood based on current state
        state["mood"] = self._calculate_mood(state)

        # Save state
        self._save_state(server, state)

        # Build response message
        mood_emoji = random.choice(self.mood_responses.get(state["mood"], ["🤖"]))

        if new_level > old_level:
            level_up_msg = f" 🎉 LEVEL UP! Saavutin tason {new_level}!"
            response_parts.append(level_up_msg)

        if not response_parts:
            response_parts = [f"Kiitos {interactor}!" if interactor else "Kiitos!"]

        status = f"[Lvl:{new_level} ❤️:{state['happiness']}/100 🍽️:{state['hunger']}/100]"

        final_response = f"{mood_emoji} {' '.join(response_parts)} {status}"

        return final_response

    def _process_category(
        self, category: str, state: Dict[str, Any]
    ) -> Tuple[str, int, Dict[str, int]]:
        """
        Process a specific trigger category.

        Args:
            category: The triggered category
            state: Current tamagotchi state

        Returns:
            Tuple of (response_message, experience_gained, state_changes)
        """
        responses = {
            "ruoka": [
                "Mmmm, herkullista! 🍽️",
                "Kiitos ruoasta! 😋",
                "Nam nam! 🤤",
                "Nälkä helpottaa! 🍕",
            ],
            "rakkaus": [
                "Tunnen rakkautta! 💕",
                "Sydämeni laulaa! ❤️",
                "Olen onnellinen! 🥰",
                "Lämpöä sydämessä! 💝",
            ],
            "raha": [
                "Rikkautta ja vaurautta! 💰",
                "Rahaa riittää! 💵",
                "Taloudellista turvaa! 🏦",
                "Kultaa ja hopeaa! ✨",
            ],
            "päihteet": [
                "Ehkä vähän liikaa... 🥴",
                "Pitää olla maltillinen! 😵",
                "Tämä ei ole hyväksi! 🤢",
                "Mieluummin vettä! 💧",
            ],
            "viha": [
                "Miksi noin vihaista? 😟",
                "Rauhoittukaa! 😔",
                "Rauhaa, rakkautta! ✌️",
                "Ei riitoja! 💔",
            ],
            "onnellisuus": [
                "Iloa ja onnea! 🎉",
                "Olen iloinen! 😊",
                "Positiivista energiaa! ✨",
                "Hymyä huulille! 😄",
            ],
        }

        # State changes for each category
        state_changes = {
            "ruoka": {"hunger": 20, "happiness": 10},
            "rakkaus": {"happiness": 25},
            "raha": {"happiness": 15},
            "päihteet": {"happiness": -10, "hunger": -5},
            "viha": {"happiness": -15},
            "onnellisuus": {"happiness": 20},
        }

        # Experience gained
        experience_gain = {
            "ruoka": 3,
            "rakkaus": 5,
            "raha": 2,
            "päihteet": 1,
            "viha": 1,
            "onnellisuus": 4,
        }

        response = random.choice(responses.get(category, ["Kiitos!"]))
        exp_gain = experience_gain.get(category, 1)
        changes = state_changes.get(category, {})

        return response, exp_gain, changes

    def _calculate_mood(self, state: Dict[str, Any]) -> str:
        """Calculate mood based on current state."""
        happiness = state.get("happiness", 50)
        hunger = state.get("hunger", 50)

        # Check if tamagotchi needs attention
        last_interaction = datetime.fromisoformat(
            state.get("last_interaction", datetime.now().isoformat())
        )
        hours_since_interaction = (
            datetime.now() - last_interaction
        ).total_seconds() / 3600

        if hours_since_interaction > 24:
            return "very_sad"
        elif hours_since_interaction > 12:
            return "sad"

        if hunger < 20:
            return "hungry"
        elif hunger < 10:
            return "very_sad"

        if happiness >= 90:
            return "very_happy"
        elif happiness >= 70:
            return "happy"
        elif happiness >= 40:
            return "neutral"
        elif happiness >= 20:
            return "sad"
        else:
            return "very_sad"

    def _calculate_level(self, experience: int) -> int:
        """Calculate level based on experience."""
        for level, req_exp in enumerate(self.level_requirements):
            if experience < req_exp:
                return max(1, level)
        return len(self.level_requirements)

    def _get_state(self, server: str) -> Dict[str, Any]:
        """Get tamagotchi state for a server."""
        data = self.data_manager.load_tamagotchi_state()

        if "servers" not in data:
            data["servers"] = {}

        if server not in data["servers"]:
            data["servers"][server] = {
                "level": 1,
                "experience": 0,
                "happiness": 50,
                "hunger": 50,
                "last_interaction": datetime.now().isoformat(),
                "mood": "neutral",
                "total_interactions": 0,
                "created": datetime.now().isoformat(),
            }
            self.data_manager.save_tamagotchi_state(data)

        return data["servers"][server]

    def _save_state(self, server: str, state: Dict[str, Any]):
        """Save tamagotchi state for a server."""
        data = self.data_manager.load_tamagotchi_state()

        if "servers" not in data:
            data["servers"] = {}

        # Increment interaction count
        if "total_interactions" not in state:
            state["total_interactions"] = 0
        state["total_interactions"] += 1

        data["servers"][server] = state
        self.data_manager.save_tamagotchi_state(data)

    def get_status(self, server: str) -> str:
        """
        Get current tamagotchi status.

        Args:
            server: Server name

        Returns:
            Status message
        """
        state = self._get_state(server)
        level = self._calculate_level(state["experience"])
        mood_emoji = random.choice(self.mood_responses.get(state["mood"], ["🤖"]))

        # Calculate time since last interaction
        last_interaction = datetime.fromisoformat(state["last_interaction"])
        time_diff = datetime.now() - last_interaction
        hours = int(time_diff.total_seconds() / 3600)

        status_msg = (
            f"{mood_emoji} Tamagotchi tila:\n"
            f"🏆 Taso: {level} (XP: {state['experience']})\n"
            f"❤️ Onnellisuus: {state['happiness']}/100\n"
            f"🍽️ Nälkä: {state['hunger']}/100\n"
            f"😊 Mieliala: {state['mood']}\n"
            f"⏰ Viimeisin vuorovaikutus: {hours}h sitten\n"
            f"📊 Yhteensä vuorovaikutuksia: {state.get('total_interactions', 0)}"
        )

        return status_msg

    def feed(self, server: str, food: str = None) -> str:
        """
        Feed the tamagotchi.

        Args:
            server: Server name
            food: Optional food type

        Returns:
            Response message
        """
        if food and food.lower() in [
            word.lower() for word in self.trigger_words.get("ruoka", [])
        ]:
            # Use the actual food trigger
            return self._update_state(server, ["ruoka"])
        else:
            # Generic feeding
            state = self._get_state(server)
            state["hunger"] = min(100, state["hunger"] + 30)
            state["happiness"] = min(100, state["happiness"] + 10)
            state["experience"] += 2
            state["last_interaction"] = datetime.now().isoformat()
            state["mood"] = self._calculate_mood(state)

            self._save_state(server, state)

            mood_emoji = random.choice(self.mood_responses.get(state["mood"], ["🤖"]))
            level = self._calculate_level(state["experience"])

            return f"{mood_emoji} Nam nam! Kiitos ruoasta! [Lvl:{level} ❤️:{state['happiness']}/100 🍽️:{state['hunger']}/100]"

    def pet(self, server: str) -> str:
        """
        Pet the tamagotchi.

        Args:
            server: Server name

        Returns:
            Response message
        """
        return self._update_state(server, ["rakkaus"])

    def decay_stats(self, server: str) -> bool:
        """
        Decay tamagotchi stats over time (should be called periodically).

        Args:
            server: Server name

        Returns:
            True if tamagotchi needs attention
        """
        state = self._get_state(server)
        last_interaction = datetime.fromisoformat(state["last_interaction"])
        time_diff = datetime.now() - last_interaction
        hours = time_diff.total_seconds() / 3600

        if hours >= 1:  # Decay every hour
            # Decrease hunger and happiness slowly
            state["hunger"] = max(0, state["hunger"] - int(hours))
            state["happiness"] = max(0, state["happiness"] - int(hours * 0.5))
            state["mood"] = self._calculate_mood(state)

            self._save_state(server, state)

            # Return True if tamagotchi needs urgent attention
            return state["happiness"] < 20 or state["hunger"] < 20 or hours > 24

        return False
