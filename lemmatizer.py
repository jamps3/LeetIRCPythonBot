import json
import sys
import os
import re
import libvoikko
from collections import defaultdict


class Lemmatizer:
    def __init__(self, data_dir="voikko"):
        # Import Voikko DLL
        if sys.version_info >= (3, 8):
            if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                base_dir = os.path.dirname(os.path.abspath(__file__))
                voikko_path = os.path.join(
                    base_dir, "voikko"
                )  # missä libvoikko-1.dll sijaitsee
                os.add_dll_directory(voikko_path)
        self.v = libvoikko.Voikko("fi")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_baseform(self, word):
        analysis = self.v.analyze(word)
        return analysis[0]["BASEFORM"] if analysis else word.lower()

    def _get_filename(self, server_name):
        safe_name = server_name.replace("/", "_").replace(":", "_")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, f"{safe_name}_words.json")

    def _load_data(self, server_name):
        filename = self._get_filename(server_name)
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return {source: defaultdict(int, data) for source, data in raw.items()}
        return defaultdict(lambda: defaultdict(int))

    def _save_data(self, server_name, data):
        filename = self._get_filename(server_name)
        # Convert defaultdicts to regular dicts for JSON
        data = {source: dict(word_counts) for source, word_counts in data.items()}
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def process_message(self, text, server_name, source_id):
        """
        source_id = kanava tai nick esim. "#kanava" tai "Nimimerkki"
        """
        data = self._load_data(server_name)
        word_counts = data.get(source_id, {})
        words = re.findall(r"\w+", text, re.UNICODE)

        for word in words:
            base = self._get_baseform(word)
            word_counts[base] = word_counts.get(base, 0) + 1

        data[source_id] = word_counts
        self._save_data(server_name, data)

        return word_counts  # voit käyttää tätä debuggaamiseen

    # 🔍 Utility functions
    def get_total_counts(self, server_name):
        """Returns total counts across all sources (e.g., channels/nicks)."""
        counts = self._load_data(server_name)
        total = defaultdict(int)
        for word_counts in counts.values():
            for word, count in word_counts.items():
                total[word] += count
        return dict(sorted(total.items(), key=lambda x: -x[1]))

    def get_counts_for_source(self, server_name, source_id):
        """Returns word counts for a specific source (channel or nick)."""
        counts = self._load_data(server_name)
        if source_id in counts:
            return dict(sorted(counts[source_id].items(), key=lambda x: -x[1]))
        return {}

    def get_top_words(self, server_name, top_n=10):
        """Returns top N most used base words across all sources."""
        total = self.get_total_counts(server_name)
        return list(total.items())[:top_n]
