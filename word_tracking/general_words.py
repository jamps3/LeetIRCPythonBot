"""
General Words Tracking

Handles general word counting functionality (renamed from tamagotchi).
Provides server-specific word tracking and statistics.
"""

import re
from datetime import datetime
from typing import Dict, List, Any
from collections import Counter

from .data_manager import DataManager


class GeneralWords:
    """General word counting and tracking functionality."""

    def __init__(self, data_manager: DataManager, lemmatizer=None):
        """
        Initialize the general words tracker.

        Args:
            data_manager: DataManager instance for data persistence
            lemmatizer: Optional lemmatizer instance for advanced word processing
        """
        self.data_manager = data_manager
        self.lemmatizer = lemmatizer

    def process_message(self, server: str, nick: str, text: str, target: str = None):
        """
        Process a message for general word tracking.

        Args:
            server: Server name
            nick: User nickname
            text: Message text
            target: Channel or target where message was sent
        """
        # Skip messages starting with commands
        if text.startswith("!"):
            return

        # Extract words from text
        words = re.findall(r"\b\w+\b", text.lower())

        if not words:
            return

        # Update word statistics
        self._update_word_stats(server, nick, words, target)

        # If lemmatizer is available, also process with it
        if self.lemmatizer:
            try:
                self.lemmatizer.process_message(
                    text, server_name=server, source_id=target or nick
                )
            except Exception as e:
                print(f"Error in lemmatizer processing: {e}")

    def _update_word_stats(
        self, server: str, nick: str, words: List[str], target: str = None
    ):
        """
        Update word statistics for a user.

        Args:
            server: Server name
            nick: User nickname
            words: List of words to count
            target: Channel or target where message was sent
        """
        data = self.data_manager.load_general_words_data()

        # Ensure structure exists
        if "servers" not in data:
            data["servers"] = {}

        if server not in data["servers"]:
            data["servers"][server] = {"nicks": {}}

        if "nicks" not in data["servers"][server]:
            data["servers"][server]["nicks"] = {}

        if nick not in data["servers"][server]["nicks"]:
            data["servers"][server]["nicks"][nick] = {
                "general_words": {},
                "first_seen": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "total_words": 0,
                "channels": {},
            }

        user_data = data["servers"][server]["nicks"][nick]

        # Update word counts
        for word in words:
            if word not in user_data["general_words"]:
                user_data["general_words"][word] = 0
            user_data["general_words"][word] += 1

        # Update channel-specific stats if target is provided
        if target:
            if "channels" not in user_data:
                user_data["channels"] = {}
            if target not in user_data["channels"]:
                user_data["channels"][target] = {"word_count": 0}
            user_data["channels"][target]["word_count"] += len(words)

        # Update totals and timestamps
        user_data["last_activity"] = datetime.now().isoformat()
        user_data["total_words"] = sum(user_data["general_words"].values())

        # Save data
        self.data_manager.save_general_words_data(data)

    def get_user_stats(self, server: str, nick: str) -> Dict[str, Any]:
        """
        Get general word statistics for a specific user.

        Args:
            server: Server name
            nick: User nickname

        Returns:
            Dictionary containing user's word statistics
        """
        data = self.data_manager.load_general_words_data()

        try:
            user_data = data["servers"][server]["nicks"][nick]
            return {
                "nick": nick,
                "server": server,
                "total_words": user_data.get("total_words", 0),
                "general_words": user_data.get("general_words", {}),
                "channels": user_data.get("channels", {}),
                "first_seen": user_data.get("first_seen", ""),
                "last_activity": user_data.get("last_activity", ""),
            }
        except KeyError:
            return {
                "nick": nick,
                "server": server,
                "total_words": 0,
                "general_words": {},
                "channels": {},
                "first_seen": "",
                "last_activity": "",
            }

    def get_user_top_words(
        self, server: str, nick: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top words for a specific user.

        Args:
            server: Server name
            nick: User nickname
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing word statistics
        """
        user_stats = self.get_user_stats(server, nick)
        general_words = user_stats["general_words"]

        # Create list of word stats
        word_list = [
            {"word": word, "count": count} for word, count in general_words.items()
        ]

        # Sort by count and return top results
        return sorted(word_list, key=lambda x: x["count"], reverse=True)[:limit]

    def get_server_stats(self, server: str) -> Dict[str, Any]:
        """
        Get general word statistics for an entire server.

        Args:
            server: Server name

        Returns:
            Dictionary containing server's word statistics
        """
        data = self.data_manager.load_general_words_data()

        if server not in data.get("servers", {}):
            return {
                "server": server,
                "total_users": 0,
                "total_words": 0,
                "top_users": [],
                "top_words": [],
            }

        server_data = data["servers"][server]["nicks"]

        # Calculate totals
        total_users = len(server_data)
        total_words = sum(user.get("total_words", 0) for user in server_data.values())

        # Get top users
        top_users = sorted(
            [(nick, user.get("total_words", 0)) for nick, user in server_data.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Get top words across all users
        all_words = Counter()
        for user_data in server_data.values():
            general_words = user_data.get("general_words", {})
            all_words.update(general_words)

        top_words = [(word, count) for word, count in all_words.most_common(10)]

        return {
            "server": server,
            "total_users": total_users,
            "total_words": total_words,
            "top_users": top_users,
            "top_words": top_words,
        }

    def search_word(self, word: str) -> Dict[str, Any]:
        """
        Search for statistics about a specific word across all servers.

        Args:
            word: The word to search for

        Returns:
            Dictionary containing statistics for the word
        """
        data = self.data_manager.load_general_words_data()
        word = word.lower()

        results = {"word": word, "total_occurrences": 0, "users": [], "servers": {}}

        for server_name, server_data in data.get("servers", {}).items():
            server_total = 0
            server_users = []

            for nick, user_data in server_data.get("nicks", {}).items():
                general_words = user_data.get("general_words", {})
                if word in general_words:
                    user_total = general_words[word]

                    server_total += user_total
                    results["total_occurrences"] += user_total

                    user_info = {
                        "nick": nick,
                        "server": server_name,
                        "count": user_total,
                    }

                    server_users.append(user_info)
                    results["users"].append(user_info)

            if server_total > 0:
                results["servers"][server_name] = {
                    "total": server_total,
                    "users": server_users,
                }

        # Sort users by count
        results["users"] = sorted(
            results["users"], key=lambda x: x["count"], reverse=True
        )

        return results

    def get_leaderboard(
        self, server: str = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get leaderboard of most active users.

        Args:
            server: Server name (if None, returns global leaderboard)
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing user statistics
        """
        data = self.data_manager.load_general_words_data()

        users = []

        if server:
            # Server-specific leaderboard
            if server in data.get("servers", {}):
                server_data = data["servers"][server]["nicks"]
                for nick, user_data in server_data.items():
                    users.append(
                        {
                            "nick": nick,
                            "server": server,
                            "total_words": user_data.get("total_words", 0),
                        }
                    )
        else:
            # Global leaderboard
            for server_name, server_data in data.get("servers", {}).items():
                for nick, user_data in server_data.get("nicks", {}).items():
                    users.append(
                        {
                            "nick": nick,
                            "server": server_name,
                            "total_words": user_data.get("total_words", 0),
                        }
                    )

        # Sort by total words and return top results
        return sorted(users, key=lambda x: x["total_words"], reverse=True)[:limit]
