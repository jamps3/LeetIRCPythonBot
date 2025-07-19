"""
Enhanced Drink Tracker

Tracks drink words with specific drinks, timestamps, and privacy controls.
Supports per-server tracking and rich statistics.
"""

import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .data_manager import DataManager


class DrinkTracker:
    """Enhanced drink word tracking with specific drinks and timestamps."""

    def __init__(self, data_manager: DataManager):
        """
        Initialize the drink tracker.

        Args:
            data_manager: DataManager instance for data persistence
        """
        self.data_manager = data_manager

        # Define drink words to track
        self.drink_words = {
            "krak",
            "kr1k",
            "kr0k",
            "narsk",
            "parsk",
            "tlup",
            "marsk",
            "tsup",
            "plop",
            "tsirp",
        }

        # Regex pattern for detecting drink words with specific drinks
        # Matches: "krak (Karhu 5,5%)" or "krak (karhu)" or just "krak"
        self.drink_pattern = re.compile(
            r"\b(" + "|".join(self.drink_words) + r")\s*(?:\(\s*([^)]+)\s*\))?",
            re.IGNORECASE,
        )

    def process_message(
        self, server: str, nick: str, text: str
    ) -> List[Tuple[str, str]]:
        """
        Process a message for drink words.

        Args:
            server: Server name
            nick: User nickname
            text: Message text

        Returns:
            List of tuples (drink_word, specific_drink) found in the message
        """
        # Check if user has opted out
        if self.data_manager.is_user_opted_out(server, nick):
            return []

        # Find all drink word matches
        matches = []
        for match in self.drink_pattern.finditer(text):
            drink_word = match.group(1).lower()
            specific_drink = match.group(2) if match.group(2) else "unspecified"

            # Clean up specific drink name
            if specific_drink != "unspecified":
                specific_drink = specific_drink.strip()

            matches.append((drink_word, specific_drink))

            # Record the drink word
            self._record_drink_word(server, nick, drink_word, specific_drink)

        return matches

    def _record_drink_word(
        self, server: str, nick: str, drink_word: str, specific_drink: str
    ):
        """
        Record a drink word occurrence.

        Args:
            server: Server name
            nick: User nickname
            drink_word: The drink word (e.g., "krak")
            specific_drink: The specific drink (e.g., "Karhu 5,5%")
        """
        data = self.data_manager.load_drink_data()

        # Ensure structure exists
        if "servers" not in data:
            data["servers"] = {}

        if server not in data["servers"]:
            data["servers"][server] = {"nicks": {}}

        if "nicks" not in data["servers"][server]:
            data["servers"][server]["nicks"] = {}

        if nick not in data["servers"][server]["nicks"]:
            data["servers"][server]["nicks"][nick] = {
                "drink_words": {},
                "first_seen": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "total_drink_words": 0,
            }

        user_data = data["servers"][server]["nicks"][nick]

        # Ensure drink word structure exists
        if drink_word not in user_data["drink_words"]:
            user_data["drink_words"][drink_word] = {
                "total": 0,
                "drinks": {},
                "timestamps": [],
            }

        drink_data = user_data["drink_words"][drink_word]

        # Update counts
        drink_data["total"] += 1
        if specific_drink not in drink_data["drinks"]:
            drink_data["drinks"][specific_drink] = 0
        drink_data["drinks"][specific_drink] += 1

        # Add timestamp
        timestamp = datetime.now().isoformat()
        drink_data["timestamps"].append(
            {"time": timestamp, "specific_drink": specific_drink}
        )

        # Keep only last 100 timestamps to prevent excessive growth
        if len(drink_data["timestamps"]) > 100:
            drink_data["timestamps"] = drink_data["timestamps"][-100:]

        # Update user totals
        user_data["last_activity"] = timestamp
        user_data["total_drink_words"] = sum(
            dw["total"] for dw in user_data["drink_words"].values()
        )

        # Save data
        self.data_manager.save_drink_data(data)

    def get_user_stats(self, server: str, nick: str) -> Dict[str, Any]:
        """
        Get drink statistics for a specific user.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Dictionary containing user's drink statistics
        """
        data = self.data_manager.load_drink_data()

        try:
            user_data = data["servers"][server]["nicks"][nick]
            return {
                "nick": nick,
                "server": server,
                "total_drink_words": user_data.get("total_drink_words", 0),
                "drink_words": user_data.get("drink_words", {}),
                "first_seen": user_data.get("first_seen", ""),
                "last_activity": user_data.get("last_activity", ""),
            }
        except KeyError:
            return {
                "nick": nick,
                "server": server,
                "total_drink_words": 0,
                "drink_words": {},
                "first_seen": "",
                "last_activity": "",
            }

    def get_server_stats(self, server: str) -> Dict[str, Any]:
        """
        Get drink statistics for an entire server.

        Args:
            server: Server name

        Returns:
            Dictionary containing server's drink statistics
        """
        data = self.data_manager.load_drink_data()

        if server not in data.get("servers", {}):
            return {
                "server": server,
                "total_users": 0,
                "total_drink_words": 0,
                "top_users": [],
            }

        server_data = data["servers"][server]["nicks"]

        # Calculate totals
        total_users = len(server_data)
        total_drink_words = sum(
            user.get("total_drink_words", 0) for user in server_data.values()
        )

        # Get top users
        top_users = sorted(
            [
                (nick, user.get("total_drink_words", 0))
                for nick, user in server_data.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "server": server,
            "total_users": total_users,
            "total_drink_words": total_drink_words,
            "top_users": top_users,
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """
        Get global drink statistics across all servers.

        Returns:
            Dictionary containing global drink statistics
        """
        data = self.data_manager.load_drink_data()

        total_users = 0
        total_drink_words = 0
        server_stats = []
        global_top_users = []

        for server_name, server_data in data.get("servers", {}).items():
            nicks = server_data.get("nicks", {})
            server_users = len(nicks)
            server_total = sum(
                user.get("total_drink_words", 0) for user in nicks.values()
            )

            total_users += server_users
            total_drink_words += server_total

            server_stats.append(
                {
                    "server": server_name,
                    "users": server_users,
                    "total_drink_words": server_total,
                }
            )

            # Add users to global top list
            for nick, user_data in nicks.items():
                global_top_users.append(
                    {
                        "nick": nick,
                        "server": server_name,
                        "total": user_data.get("total_drink_words", 0),
                    }
                )

        # Sort global top users
        global_top_users = sorted(
            global_top_users, key=lambda x: x["total"], reverse=True
        )[:10]

        return {
            "total_users": total_users,
            "total_drink_words": total_drink_words,
            "servers": server_stats,
            "top_users": global_top_users,
        }

    def search_drink_word(self, drink_word: str) -> Dict[str, Any]:
        """
        Search for statistics about a specific drink word.

        Args:
            drink_word: The drink word to search for

        Returns:
            Dictionary containing statistics for the drink word
        """
        data = self.data_manager.load_drink_data()
        drink_word = drink_word.lower()

        results = {
            "drink_word": drink_word,
            "total_occurrences": 0,
            "users": [],
            "servers": {},
        }

        for server_name, server_data in data.get("servers", {}).items():
            server_total = 0
            server_users = []

            for nick, user_data in server_data.get("nicks", {}).items():
                drink_words = user_data.get("drink_words", {})
                if drink_word in drink_words:
                    user_total = drink_words[drink_word]["total"]
                    drinks = drink_words[drink_word]["drinks"]

                    server_total += user_total
                    results["total_occurrences"] += user_total

                    user_info = {
                        "nick": nick,
                        "server": server_name,
                        "total": user_total,
                        "drinks": drinks,
                    }

                    server_users.append(user_info)
                    results["users"].append(user_info)

            if server_total > 0:
                results["servers"][server_name] = {
                    "total": server_total,
                    "users": server_users,
                }

        # Sort users by total
        results["users"] = sorted(
            results["users"], key=lambda x: x["total"], reverse=True
        )

        return results

    def search_specific_drink(self, specific_drink: str) -> Dict[str, Any]:
        """
        Search for statistics about a specific drink.

        Args:
            specific_drink: The specific drink to search for

        Returns:
            Dictionary containing statistics for the specific drink
        """
        data = self.data_manager.load_drink_data()
        specific_drink_lower = specific_drink.lower()

        results = {
            "specific_drink": specific_drink,
            "total_occurrences": 0,
            "users": [],
            "drink_words": Counter(),
        }

        for server_name, server_data in data.get("servers", {}).items():
            for nick, user_data in server_data.get("nicks", {}).items():
                user_total = 0
                user_drink_words = {}

                for drink_word, drink_data in user_data.get("drink_words", {}).items():
                    for drink_name, count in drink_data.get("drinks", {}).items():
                        if drink_name.lower() == specific_drink_lower:
                            user_total += count
                            user_drink_words[drink_word] = count
                            results["drink_words"][drink_word] += count

                if user_total > 0:
                    results["total_occurrences"] += user_total
                    results["users"].append(
                        {
                            "nick": nick,
                            "server": server_name,
                            "total": user_total,
                            "drink_words": user_drink_words,
                        }
                    )

        # Sort users by total
        results["users"] = sorted(
            results["users"], key=lambda x: x["total"], reverse=True
        )

        return results

    def get_user_top_drinks(
        self, server: str, nick: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top drink words for a specific user.

        Args:
            server: Server name
            nick: User nickname
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing drink word statistics
        """
        user_stats = self.get_user_stats(server, nick)
        drink_words = user_stats["drink_words"]

        # Create list of drink word stats
        drink_list = []
        for drink_word, data in drink_words.items():
            drink_list.append(
                {
                    "drink_word": drink_word,
                    "total": data["total"],
                    "drinks": data["drinks"],
                    "most_common_drink": (
                        max(data["drinks"].items(), key=lambda x: x[1])[0]
                        if data["drinks"]
                        else "unspecified"
                    ),
                }
            )

        # Sort by total and return top results
        return sorted(drink_list, key=lambda x: x["total"], reverse=True)[:limit]

    def get_drink_word_breakdown(
        self, server: str, limit: int = 10
    ) -> List[Tuple[str, int, str]]:
        """
        Get breakdown of drink words for a server with top users.

        Args:
            server: Server name
            limit: Maximum number of results to return

        Returns:
            List of tuples (drink_word, total_count, top_user)
        """
        data = self.data_manager.load_drink_data()

        if server not in data.get("servers", {}):
            return []

        server_data = data["servers"][server]["nicks"]
        drink_word_stats = {}

        # Collect statistics for each drink word
        for nick, user_data in server_data.items():
            for drink_word, drink_data in user_data.get("drink_words", {}).items():
                if drink_word not in drink_word_stats:
                    drink_word_stats[drink_word] = {"total": 0, "users": []}

                total = drink_data["total"]
                drink_word_stats[drink_word]["total"] += total
                drink_word_stats[drink_word]["users"].append((nick, total))

        # Create breakdown list
        breakdown = []
        for drink_word, stats in drink_word_stats.items():
            # Find top user for this drink word
            top_user = (
                max(stats["users"], key=lambda x: x[1])[0]
                if stats["users"]
                else "unknown"
            )
            breakdown.append((drink_word, stats["total"], top_user))

        # Sort by total count and return top results
        return sorted(breakdown, key=lambda x: x[1], reverse=True)[:limit]

    def handle_opt_out(self, server: str, nick: str) -> str:
        """
        Handle user opt-out request (!antikrak command).

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Response message for the user
        """
        if self.data_manager.is_user_opted_out(server, nick):
            # User is already opted out, opt them back in
            self.data_manager.set_user_opt_out(server, nick, opt_out=False)
            return f"{nick}: Olet nyt takaisin mukana juomien seurannassa! 🍺"
        else:
            # Opt user out
            self.data_manager.set_user_opt_out(server, nick, opt_out=True)
            return f"{nick}: Olet nyt poissa juomien seurannasta. Käytä !antikrak uudelleen palataksesi mukaan."
