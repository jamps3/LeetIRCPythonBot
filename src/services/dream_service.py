"""
Dream Service Module

Provides dream generation functionality for the Dream Mode feature.
Generates surreal narratives and technical reports from daily conversation data.
"""

import json
import os
import random
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from logger import get_logger

logger = get_logger("DreamService")


class DreamService:
    """Service for generating dream narratives from daily conversation data."""

    def __init__(
        self,
        data_manager,
        gpt_service=None,
        dream_vocab_file="data/dream_vocab.json",
        lag_history_file="data/state.json",
    ):
        self.data_manager = data_manager
        self.gpt_service = gpt_service
        self.dream_vocab_file = dream_vocab_file
        self.lag_history_file = lag_history_file

        # Load themed vocabulary for different genres
        self.vocab = self._load_dream_vocab()

        # Default genre settings
        self.genres = {
            "surrealist": {
                "themes": ["dream", "unconscious", "absurd", "paradox", "reality"],
                "style": "surrealist",
                "mood": "dreamlike",
            },
            "cyberpunk": {
                "themes": ["neon", "digital", "cybernetic", "dystopian", "future"],
                "style": "cyberpunk",
                "mood": "tech-noir",
            },
        }

    def _load_dream_vocab(self) -> Dict[str, Any]:
        """Load themed vocabulary for dream generation."""
        default_vocab = {
            "surrealist": {
                "nouns": [
                    "dream",
                    "unconscious",
                    "reality",
                    "paradox",
                    "absurd",
                    "void",
                    "mirror",
                    "shadow",
                    "echo",
                    "labyrinth",
                ],
                "verbs": [
                    "float",
                    "drift",
                    "melt",
                    "transform",
                    "dissolve",
                    "wander",
                    "echo",
                    "reflect",
                    "distort",
                    "unfold",
                ],
                "adjectives": [
                    "surreal",
                    "dreamlike",
                    "absurd",
                    "paradoxical",
                    "ethereal",
                    "labyrinthine",
                    "uncanny",
                    "phantasmagoric",
                ],
                "connectors": [
                    "in the realm of",
                    "beyond the veil of",
                    "through the looking glass of",
                    "in the quantum foam of",
                    "amidst the neural static of",
                ],
            },
            "cyberpunk": {
                "nouns": [
                    "neon",
                    "circuit",
                    "datastream",
                    "cybernetic",
                    "dystopia",
                    "augmentation",
                    "synthwave",
                    "nanotech",
                    "hologram",
                    "mainframe",
                ],
                "verbs": [
                    "pulse",
                    "glitch",
                    "stream",
                    "hack",
                    "encrypt",
                    "decrypt",
                    "overload",
                    "bootstrap",
                    "sync",
                    "interface",
                ],
                "adjectives": [
                    "neon-lit",
                    "cybernetic",
                    "dystopian",
                    "synthetic",
                    "augmented",
                    "encrypted",
                    "glitchy",
                    "overclocked",
                ],
                "connectors": [
                    "in the neon-drenched",
                    "through the digital static of",
                    "amidst the server farms of",
                    "in the quantum circuits of",
                    "through the neural networks of",
                ],
            },
        }

        try:
            if os.path.exists(self.dream_vocab_file):
                with open(self.dream_vocab_file, "r", encoding="utf-8") as f:
                    vocab = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for genre in default_vocab:
                        if genre not in vocab:
                            vocab[genre] = default_vocab[genre]
                        else:
                            for key in default_vocab[genre]:
                                if key not in vocab[genre]:
                                    vocab[genre][key] = default_vocab[genre][key]
                    return vocab
        except Exception as e:
            logger.warning(f"Error loading dream vocab: {e}, using defaults")

        return default_vocab

    def _get_daily_conversation_data(
        self, server_name: str, date: datetime
    ) -> Dict[str, Any]:
        """Extract conversation data for a specific day."""
        # Get word tracking data
        try:
            general_words = self.data_manager.load_general_words_data()
            drink_data = self.data_manager.load_drink_data()
        except Exception as e:
            logger.error(f"Error loading conversation data: {e}")
            return {"error": str(e)}

        # Filter data for the specific day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # Extract word statistics
        daily_words = {}
        daily_users = set()
        total_messages = 0
        night_messages = 0  # Messages between 18:00-06:00

        # Process general words data
        if server_name in general_words.get("servers", {}):
            server_data = general_words["servers"][server_name]["nicks"]
            for nick, user_data in server_data.items():
                daily_users.add(nick)
                for word, count in user_data.get("general_words", {}).items():
                    if word not in daily_words:
                        daily_words[word] = 0
                    daily_words[word] += count
                total_messages += user_data.get("total_words", 0)

        # Process drink data for "intoxication" elements
        drink_words = {}
        if server_name in drink_data.get("servers", {}):
            server_data = drink_data["servers"][server_name]["nicks"]
            for nick, user_data in server_data.items():
                for drink_word, drink_info in user_data.get("drink_words", {}).items():
                    if drink_word not in drink_words:
                        drink_words[drink_word] = 0
                    drink_words[drink_word] += drink_info.get("count", 0)

        # Calculate night message percentage (for "dream state" intensity)
        # Note: This is simplified - in a real implementation, we'd track timestamps
        night_percentage = min(50, total_messages * 2)  # Mock calculation

        return {
            "server": server_name,
            "date": date.strftime("%Y-%m-%d"),
            "total_messages": total_messages,
            "unique_users": len(daily_users),
            "top_words": sorted(daily_words.items(), key=lambda x: x[1], reverse=True)[
                :10
            ],
            "top_drinks": sorted(drink_words.items(), key=lambda x: x[1], reverse=True)[
                :5
            ],
            "night_percentage": night_percentage,
            "users": list(daily_users),
        }

    def _generate_surrealist_narrative(
        self, data: Dict[str, Any], vocab: Dict[str, Any]
    ) -> str:
        """Generate a surrealist dream narrative using AI or random generation."""
        # Try to use GPT for more creative generation
        if self.gpt_service:
            return self._generate_ai_dream(data, "surrealist")

        # Fallback: Generate fully random content without templates
        return self._generate_random_narrative(data, vocab, "surrealist")

    def _generate_ai_dream(self, data: Dict[str, Any], genre: str) -> str:
        """Generate a dream narrative using AI."""
        # Extract conversation elements for context
        top_words = [word for word, count in data.get("top_words", [])[:5]]
        top_drinks = [drink for drink, count in data.get("top_drinks", [])[:3]]
        user_count = data.get("unique_users", 0)
        total_messages = data.get("total_messages", 0)

        # Build context prompt
        context_parts = []
        if top_words:
            context_parts.append(
                f"Keywords from today's conversation: {', '.join(top_words)}"
            )
        if top_drinks:
            context_parts.append(f"Substances mentioned: {', '.join(top_drinks)}")
        if user_count > 0:
            context_parts.append(f"{user_count} people were active in the conversation")
        if total_messages > 0:
            context_parts.append(f"{total_messages} messages were exchanged")

        context = " | ".join(context_parts) if context_parts else "ordinary day"

        # Create genre-specific prompt
        if genre == "cyberpunk":
            prompt = f"Generate a short, surreal cyberpunk dream narrative (2-3 sentences) about a digital consciousness experiencing a dream. The context: {context}. Make it sound like a glitchy AI narration."
        else:
            prompt = f"Generate a short, surreal dream narrative (2-3 sentences) about someone experiencing a strange, abstract dream. The context: {context}. Make it poetic and dreamlike."

        try:
            response = self.gpt_service.chat(prompt)
            if response and not response.startswith("Error"):
                return response
        except Exception as e:
            logger.warning(f"GPT dream generation failed: {e}")

        # Fallback to random generation if GPT fails
        return self._generate_random_narrative(
            data, self.vocab.get(genre, self.vocab["surrealist"]), genre
        )

    def _generate_random_narrative(
        self, data: Dict[str, Any], vocab: Dict[str, Any], genre: str
    ) -> str:
        """Generate a fully random dream narrative without templates."""
        # Extract conversation elements (or use random if not available)
        top_words = [word for word, count in data.get("top_words", [])[:3]]
        top_drinks = [drink for drink, count in data.get("top_drinks", [])[:2]]
        user_count = data.get("unique_users", 0)
        total_messages = data.get("total_messages", 0)

        # If no real data, generate random elements
        if not top_words:
            top_words = [random.choice(vocab.get("nouns", ["void"]))]
        if not top_drinks:
            top_drinks = [random.choice(vocab.get("nouns", ["mist"]))]
        if user_count == 0:
            user_count = random.randint(1, 10)
        if total_messages == 0:
            total_messages = random.randint(100, 5000)

        # Generate random narrative parts
        narrative_parts = []

        # Random opening based on genre
        if genre == "cyberpunk":
            openings = [
                f"SYSTEM_DREAM v{random.randint(2, 9)}.{random.randint(0, 99)} initiating...",
                f"NEURAL_PATHWAY ACTIVATED in sector {random.choice(['Alpha', 'Beta', 'Gamma', 'Delta', 'Omega'])}...",
                f"QUANTUM_CONSCIOUSNESS breach detected at {random.randint(100, 999)}MHz...",
                "DIGITAL_SLEEP mode engaged. Synaptic bridges forming...",
            ]
        else:
            openings = [
                f"The threshold between waking and dreaming dissolves like {random.choice(vocab.get('verbs', ['melting']))}...",
                f"In the space between seconds, where {random.choice(vocab.get('nouns', ['shadows']))} speak...",
                f"A {random.choice(vocab.get('adjectives', ['strange']))} wind carries fragments of {random.choice(vocab.get('nouns', ['memories']))}...",
                f"The {random.choice(vocab.get('nouns', ['mirror']))} shows a reality that was never quite real...",
            ]
        narrative_parts.append(random.choice(openings))

        # Random middle - using word associations
        dream_word = random.choice(top_words)
        verb = random.choice(vocab.get("verbs", ["drift"]))
        adj = random.choice(vocab.get("adjectives", ["strange"]))
        noun2 = random.choice(vocab.get("nouns", ["echo"]))

        if genre == "cyberpunk":
            narrative_parts.append(
                f"DATA_FRAGMENT '{dream_word}' {verb}s through neural {noun2}. "
                f"Probability matrix shows {adj} reality distortion at {random.randint(10, 99)}%."
            )
        else:
            narrative_parts.append(
                f"{dream_word.capitalize()} {verb}s, becoming {adj} {noun2} that "
                f"{random.choice(vocab.get('verbs', ['floating']))} through the {random.choice(vocab.get('nouns', ['void']))}."
            )

        # Random element about drinks/substances
        drink = random.choice(top_drinks)
        if genre == "cyberpunk":
            narrative_parts.append(
                f"BIO-SUBSTANCE '{drink}' detected in dream buffer. "
                f"Consciousness calibration at {random.randint(50, 99)}%."
            )
        else:
            narrative_parts.append(
                f"{drink.capitalize()} becomes {random.choice(vocab.get('adjectives', ['ethereal']))} "
                f"{random.choice(vocab.get('nouns', ['light']))}, dissolving into {random.choice(vocab.get('nouns', ['shadows']))}."
            )

        # Random user count element
        if genre == "cyberpunk":
            narrative_parts.append(
                f"{user_count} neural nodes connected. Dream_{random.choice(['protocol', 'matrix', 'stream'])} "
                f"optimizing at {random.randint(100, 999)}% efficiency."
            )
        else:
            narrative_parts.append(
                f"{user_count} {random.choice(['souls', 'spirits', 'minds', 'consciousnesses'])} "
                f"{random.choice(vocab.get('verbs', ['drift']))} together in this {random.choice(vocab.get('adjectives', ['shared']))} {random.choice(vocab.get('nouns', ['dream']))}."
            )

        # Random closing
        if genre == "cyberpunk":
            closings = [
                "SYSTEM_HALT. Dream cycle complete. Reality stream resuming...",
                "MEMORY_CACHE cleared. The simulation continues... or does it?",
                f"DISCONNECTING from neural dream. {random.choice(['Awake', 'Asleep', 'Neither'])} state pending...",
            ]
        else:
            closings = [
                f"And when the {random.choice(vocab.get('nouns', ['clock']))} strikes, the dream {random.choice(vocab.get('verbs', ['dissolves']))} into waking...",
                f"But the {random.choice(vocab.get('nouns', ['shadow']))} remembers what the mind forgets.",
                f"The {random.choice(vocab.get('nouns', ['door']))} opens, and {random.choice(vocab.get('adjectives', ['strange']))} {random.choice(vocab.get('adjectives', ['strange']))} morning light floods in.",
            ]
        narrative_parts.append(random.choice(closings))

        return " ".join(narrative_parts)

    def _generate_cyberpunk_narrative(
        self, data: Dict[str, Any], vocab: Dict[str, Any]
    ) -> str:
        """Generate a cyberpunk dream narrative."""
        if not data.get("top_words") or data["total_messages"] == 0:
            return "System diagnostic: No neural activity detected in sector {data['server']}. Dream protocol offline."

        # Extract key elements from data
        top_words = [word for word, count in data["top_words"][:3]]
        top_drinks = [drink for drink, count in data["top_drinks"][:2]]
        user_count = data["unique_users"]
        message_count = data["total_messages"]

        # Build cyberpunk narrative
        narrative_parts = []

        # Opening - system diagnostic style
        connectors = vocab["connectors"]
        opening = f"SYSTEM BOOT SEQUENCE INITIATED in {data['server']}..."
        narrative_parts.append(opening)

        # Main narrative - cybernetic interpretation
        if top_words:
            dream_word = top_words[0]
            cyber_verb = random.choice(vocab["verbs"])
            cyber_adj = random.choice(vocab["adjectives"])
            narrative_parts.append(
                f"WORD STREAM ANALYSIS: '{dream_word}' detected, {cyber_verb}ing through mainframe at {random.randint(100, 999)}% capacity. Neural pathways show {cyber_adj} activity patterns."
            )

        if top_drinks:
            drink_word = top_drinks[0]
            narrative_parts.append(
                f"SUBSTANCE DETECTION: {drink_word} metabolization detected. Bio-readings indicate elevated dream-state probability."
            )

        # User interaction element - cybernetic style
        if user_count > 0:
            narrative_parts.append(
                f"NEURAL NETWORK SCAN: {user_count} organic units connected to dream matrix. Synaptic activity at optimal levels for lucid dreaming protocols."
            )

        # Message flow element - data stream style
        if message_count > 0:
            narrative_parts.append(
                f"DATA STREAM: {message_count} packets of consciousness flowing through server architecture. Encryption protocols suggest subconscious encryption is active."
            )

        # Closing - system shutdown style
        closing = "DREAM CYCLE COMPLETE. System returning to normal operational parameters. Or is this just another layer of the simulation?"
        narrative_parts.append(closing)

        return " ".join(narrative_parts)

    def _generate_technical_report(self, data: Dict[str, Any], genre: str) -> str:
        """Generate a technical report style dream."""
        if not data.get("top_words") or data["total_messages"] == 0:
            return f"SYSTEM DIAGNOSTIC: No conversation data available for {data.get('server', 'unknown')} on {data.get('date', 'unknown date')}."

        # Build technical report
        report_parts = []

        # Header
        report_parts.append("=== DREAM ANALYSIS REPORT ===")
        report_parts.append(f"Server: {data['server']}")
        report_parts.append(f"Date: {data['date']}")
        report_parts.append(f"Analysis Type: {genre.upper()} DREAM STATE")
        report_parts.append("")

        # Statistics section
        report_parts.append("=== CONVERSATION METRICS ===")
        report_parts.append(f"Total Messages: {data['total_messages']}")
        report_parts.append(f"Unique Users: {data['unique_users']}")
        report_parts.append(f"Night Activity: {data['night_percentage']:.1f}%")
        report_parts.append("")

        # Word analysis
        report_parts.append("=== TOP WORD FREQUENCY ANALYSIS ===")
        for i, (word, count) in enumerate(data["top_words"][:5], 1):
            percentage = (count / max(data["total_messages"], 1)) * 100
            report_parts.append(
                f"{i}. '{word}': {count} occurrences ({percentage:.2f}%)"
            )
        report_parts.append("")

        # Drink analysis
        if data["top_drinks"]:
            report_parts.append("=== SUBSTANCE CONSUMPTION ANALYSIS ===")
            for i, (drink, count) in enumerate(data["top_drinks"], 1):
                report_parts.append(f"{i}. {drink}: {count} instances")
            report_parts.append("")

        # Dream interpretation
        report_parts.append("=== DREAM INTERPRETATION ===")
        if genre == "surrealist":
            report_parts.append(
                "The collective unconscious shows signs of heightened surreal activity."
            )
            report_parts.append(
                "Reality distortion fields are active. Proceed with caution."
            )
        else:  # cyberpunk
            report_parts.append("Neural implants detecting anomalous dream patterns.")
            report_parts.append(
                "System integrity check recommended. Possible simulation interference detected."
            )
        report_parts.append("")

        # Conclusion
        report_parts.append("=== CONCLUSION ===")
        report_parts.append(
            "Dream state analysis complete. Subject data suggests normal/abnormal dream patterns within expected parameters."
        )
        report_parts.append(
            "Recommendation: Monitor for continued dream activity. Prepare for potential reality shifts."
        )
        report_parts.append("")
        report_parts.append("=== END REPORT ===")

        return "\n".join(report_parts)

    def _get_average_lag(self) -> Optional[float]:
        """Get average lag from lag history in nanoseconds."""
        try:
            state = self.data_manager.load_state()
            lag_history = state.get("lag_history", [])

            if not lag_history:
                return None

            # Get last 10 lag measurements
            recent_lags = lag_history[-10:]
            if not recent_lags:
                return None

            # Calculate average lag in nanoseconds
            total_lag = sum(entry.get("lag_ns", 0) for entry in recent_lags)
            avg_lag_ns = total_lag / len(recent_lags)

            return avg_lag_ns

        except Exception as e:
            logger.warning(f"Error getting average lag: {e}")
            return None

    def generate_dream(
        self,
        server_name: str,
        channel: str,
        genre: str = "surrealist",
        output_type: str = "narrative",
    ) -> str:
        """Generate a dream for the specified server and channel."""
        try:
            # Get current date for daily data
            current_date = datetime.now()

            # Extract conversation data for the day
            conversation_data = self._get_daily_conversation_data(
                server_name, current_date
            )

            if "error" in conversation_data:
                return f"Dream generation failed: {conversation_data['error']}"

            # Select vocabulary for the chosen genre
            vocab = self.vocab.get(genre, self.vocab["surrealist"])

            # Generate dream content based on output type
            if output_type == "report":
                dream_content = self._generate_technical_report(
                    conversation_data, genre
                )
            elif genre == "cyberpunk":
                dream_content = self._generate_cyberpunk_narrative(
                    conversation_data, vocab
                )
            else:  # surrealist or default
                dream_content = self._generate_surrealist_narrative(
                    conversation_data, vocab
                )

            # Add metadata
            metadata = f"\n\n🌙 Generated for {channel} at {current_date.strftime('%Y-%m-%d %H:%M:%S')}"
            avg_lag = self._get_average_lag()
            if avg_lag is not None:
                metadata += (
                    f" | Network lag: {avg_lag:,.0f} ns ({avg_lag/1_000_000:.3f} ms)"
                )

            return dream_content + metadata

        except Exception as e:
            logger.error(f"Error generating dream: {e}")
            return f"Dream generation failed: {str(e)}"

    def measure_and_store_lag(self, lag_ns: int):
        """Store lag measurement in state.json for timing calculations."""
        try:
            state = self.data_manager.load_state()

            # Initialize lag history if it doesn't exist
            if "lag_history" not in state:
                state["lag_history"] = []

            # Add new lag measurement with timestamp
            lag_entry = {"timestamp": datetime.now().isoformat(), "lag_ns": lag_ns}
            state["lag_history"].append(lag_entry)

            # Keep only last 10 measurements
            if len(state["lag_history"]) > 10:
                state["lag_history"] = state["lag_history"][-10:]

            # Save updated state
            self.data_manager.save_state(state)

        except Exception as e:
            logger.warning(f"Error storing lag measurement: {e}")

    def toggle_dream_channel(self, channel: str) -> bool:
        """Toggle automatic midnight dreams for a channel."""
        try:
            state = self.data_manager.load_state()

            # Initialize dream channels if it doesn't exist
            if "dream_channels" not in state:
                state["dream_channels"] = []

            # Toggle channel
            if channel in state["dream_channels"]:
                state["dream_channels"].remove(channel)
                return False  # Disabled
            else:
                state["dream_channels"].append(channel)
                return True  # Enabled

        except Exception as e:
            logger.error(f"Error toggling dream channel: {e}")
            return False

    def is_dream_channel_enabled(self, channel: str) -> bool:
        """Check if automatic dreams are enabled for a channel."""
        try:
            state = self.data_manager.load_state()
            return channel in state.get("dream_channels", [])
        except Exception:
            return False

    def get_enabled_channels(self) -> List[str]:
        """Get list of channels with automatic dreams enabled."""
        try:
            state = self.data_manager.load_state()
            return state.get("dream_channels", [])
        except Exception:
            return []


def create_dream_service(data_manager, gpt_service=None):
    """Create and return a DreamService instance."""
    return DreamService(data_manager, gpt_service)
