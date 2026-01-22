import json
import os
import re
import sys
from collections import defaultdict

import logger

# Try to import Voikko with proper error handling
try:
    import libvoikko

    VOIKKO_AVAILABLE = True
except ImportError:
    VOIKKO_AVAILABLE = False


class Lemmatizer:
    def __init__(self, data_dir="voikko"):
        self.voikko_enabled = False
        self.v = None
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        # Try to initialize Voikko if available
        if VOIKKO_AVAILABLE:
            try:
                # Import Voikko DLL on Windows
                if sys.version_info >= (3, 8):
                    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        voikko_path = os.path.join(base_dir, "voikko")
                        if os.path.exists(voikko_path):
                            os.add_dll_directory(voikko_path)

                # Try to initialize Voikko
                self.v = libvoikko.Voikko("fi")
                self.voikko_enabled = True
                logger.info("Voikko lemmatizer initialized successfully")

            except Exception as e:
                logger.error(
                    f"Voikko initialization failed: {e}, using simple word normalization"
                )
                self.voikko_enabled = False
                self.v = None
        else:
            logger.warning(
                "Voikko not available - using simple word normalization", "Lemmatizer"
            )

    def __del__(self):
        """Properly clean up Voikko resources."""
        if self.v is not None:
            try:
                self.v.terminate()
            except Exception:
                # Ignore cleanup errors during shutdown
                pass
            finally:
                self.v = None

    def _get_baseform(self, word):
        """Get base form of a word using Voikko or simple normalization."""
        if self.voikko_enabled and self.v:
            try:
                analysis = self.v.analyze(word)
                return analysis[0]["BASEFORM"] if analysis else word.lower()
            except Exception:
                # Fallback to simple normalization if Voikko fails
                return self._simple_normalize(word)
        else:
            # Use simple normalization when Voikko is not available
            return self._simple_normalize(word)

    def _simple_normalize(self, word):
        """Simple word normalization for Finnish text when Voikko is not available."""
        word = word.lower().strip()

        # Skip very short words or numbers
        if len(word) < 2 or word.isdigit():
            return word

        # Basic Finnish plural and case ending removal
        # This is a simplified approach, not as accurate as Voikko

        # Remove common plural endings
        if word.endswith(("ien", "jen", "ten", "den", "nen")):
            if len(word) > 5:
                word = word[:-3]
        elif word.endswith(("it", "at", "et", "ut", "yt", "öt", "ät")):
            if len(word) > 4:
                word = word[:-2]

        # Remove common case endings (simplified)
        if word.endswith(("lla", "llä", "ssa", "ssä", "sta", "stä", "aan", "ään")):
            if len(word) > 5:
                word = word[:-3]
        elif word.endswith(("na", "nä", "ta", "tä", "la", "lä", "ra", "rä")):
            if len(word) > 4:
                word = word[:-2]
        elif word.endswith(("n", "a", "ä", "i")):
            if len(word) > 3:
                word = word[:-1]

        return word

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


# Global Voikko instance
_voikko_instance = None


def _get_voikko():
    global _voikko_instance
    if _voikko_instance is None and VOIKKO_AVAILABLE:
        try:
            _voikko_instance = libvoikko.Voikko("fi")
        except Exception as e:
            logger.error(f"Failed to initialize Voikko: {e}")
            _voikko_instance = None
    return _voikko_instance


def analyze_word(word):
    """Analyze a word using Voikko and return the analyses."""
    v = _get_voikko()
    if v:
        try:
            analyses = v.analyze(word)
            return analyses
        except Exception as e:
            logger.error(f"Error analyzing word {word}: {e}")
            return []
    else:
        # Fallback: simple check if word looks Finnish (alphabetic, len > 2)
        if word.isalpha() and len(word) > 2:
            return [{"BASEFORM": word.lower()}]  # Mock analysis
        return []
