"""
Nanosecond Leet Detection System

Detects "1337" patterns in high-precision timestamps and awards different
levels of leet achievements based on the position and frequency of occurrence.
"""

import time
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from logger import get_logger


class NanoLeetDetector:
    """
    Detects leet (1337) patterns in nanosecond-precision timestamps.
    
    Achievement levels based on where "1337" appears in the timestamp:
    - Ultimate Leet: Perfect "13:37:13.371337133" format
    - Mega Leet: "1337" appears 3+ times in the timestamp
    - Super Leet: "1337" appears 2 times in the timestamp  
    - Leet: "1337" appears once in hours, minutes, or seconds
    - Nano Leet: "1337" appears only in nanosecond digits
    """
    
    def __init__(self):
        """Initialize the leet detector."""
        self.logger = get_logger("NanoLeetDetector")
        
        # Achievement levels and their criteria
        self.achievement_levels = {
            'ultimate': {
                'name': 'Ultimate Leet!!',
                'emoji': '🏆👑',
                'criteria': 'Perfect 13:37:13.371337133 format',
                'min_count': 1
            },
            'mega': {
                'name': 'Mega Leet!',
                'emoji': '🎯🔥',
                'criteria': '1337 appears 3+ times',
                'min_count': 3
            },
            'super': {
                'name': 'Super Leet!',
                'emoji': '⭐💫',
                'criteria': '1337 appears 2 times',
                'min_count': 2
            },
            'leet': {
                'name': 'Leet!',
                'emoji': '🎊✨',
                'criteria': '1337 appears in time part',
                'min_count': 1
            },
            'nano': {
                'name': 'Nano Leet',
                'emoji': '🔬⚡',
                'criteria': '1337 appears only in nanoseconds',
                'min_count': 1
            }
        }
    
    def get_timestamp_with_nanoseconds(self) -> str:
        """
        Get current timestamp with nanosecond precision.
        
        Returns:
            Formatted timestamp string like "13:37:13.371337133"
        """
        now = datetime.now()
        nanoseconds = time.time_ns() % 1_000_000_000
        
        # Format: HH:MM:SS.nnnnnnnnn
        return f"{now.strftime('%H:%M:%S')}.{nanoseconds:09d}"
    
    def detect_leet_patterns(self, timestamp: str) -> Dict[str, any]:
        """
        Detect leet patterns in a timestamp string.
        
        Args:
            timestamp: Timestamp string like "13:37:13.371337133"
            
        Returns:
            Dictionary with detection results
        """
        # Remove colons and dots to get pure number string for counting
        pure_numbers = re.sub(r'[:.]+', '', timestamp)
        
        # Split timestamp into components
        if '.' in timestamp:
            time_part, nano_part = timestamp.split('.', 1)
        else:
            time_part = timestamp
            nano_part = ""
        
        # Count total occurrences of "1337"
        total_count = len(re.findall(r'1337', pure_numbers))
        
        # Count occurrences in different parts
        time_count = len(re.findall(r'1337', time_part.replace(':', '')))
        nano_count = len(re.findall(r'1337', nano_part))
        
        # Check for ultimate leet pattern (perfect 13:37:13.371337133)
        is_ultimate = self._check_ultimate_pattern(timestamp)
        
        # Find all positions where 1337 occurs
        positions = []
        for match in re.finditer(r'1337', pure_numbers):
            positions.append(match.start())
        
        return {
            'timestamp': timestamp,
            'pure_numbers': pure_numbers,
            'total_count': total_count,
            'time_count': time_count,
            'nano_count': nano_count,
            'is_ultimate': is_ultimate,
            'positions': positions,
            'time_part': time_part,
            'nano_part': nano_part
        }
    
    def _check_ultimate_pattern(self, timestamp: str) -> bool:
        """
        Check if timestamp matches the ultimate leet pattern.
        
        Args:
            timestamp: Timestamp string
            
        Returns:
            True if it matches 13:37:13.371337133 pattern
        """
        # The ultimate pattern: 13:37:13.371337133
        # Hours=13, Minutes=37, Seconds=13, Nanoseconds=371337133
        pattern = r'^13:37:13\.371337133$'
        return bool(re.match(pattern, timestamp))
    
    def determine_achievement_level(self, detection_result: Dict[str, any]) -> Optional[str]:
        """
        Determine the achievement level based on detection results.
        
        Args:
            detection_result: Result from detect_leet_patterns()
            
        Returns:
            Achievement level string or None if no achievement
        """
        # Check for ultimate leet first
        if detection_result['is_ultimate']:
            return 'ultimate'
        
        total_count = detection_result['total_count']
        time_count = detection_result['time_count']
        nano_count = detection_result['nano_count']
        
        # No 1337 found
        if total_count == 0:
            return None
        
        # Mega leet: 3+ occurrences
        if total_count >= 3:
            return 'mega'
        
        # Super leet: exactly 2 occurrences
        if total_count == 2:
            return 'super'
        
        # Regular leet: 1 occurrence in time part
        if time_count > 0:
            return 'leet'
        
        # Nano leet: 1 occurrence only in nanoseconds
        if nano_count > 0:
            return 'nano'
        
        return None
    
    def format_achievement_message(self, nick: str, timestamp: str, achievement_level: str) -> str:
        """
        Format the achievement message for IRC.
        
        Args:
            nick: Nickname who achieved the leet
            timestamp: The timestamp that triggered the achievement
            achievement_level: Level of achievement
            
        Returns:
            Formatted message string
        """
        achievement = self.achievement_levels[achievement_level]
        
        return (f"{achievement['emoji']} {achievement['name']} "
                f"[{nick}] {timestamp}")
    
    def check_message_for_leet(self, nick: str, message_time: Optional[str] = None) -> Optional[Tuple[str, str]]:
        """
        Check if a message timestamp contains leet patterns.
        
        Args:
            nick: Nickname of the message sender
            message_time: Optional timestamp, uses current time if None
            
        Returns:
            Tuple of (achievement_message, achievement_level) or None
        """
        if message_time is None:
            message_time = self.get_timestamp_with_nanoseconds()
        
        detection_result = self.detect_leet_patterns(message_time)
        achievement_level = self.determine_achievement_level(detection_result)
        
        if achievement_level:
            message = self.format_achievement_message(nick, message_time, achievement_level)
            self.logger.info(f"Leet detected: {achievement_level} for {nick} at {message_time}")
            return (message, achievement_level)
        
        return None
    
    def get_achievement_stats(self) -> Dict[str, Dict[str, any]]:
        """
        Get statistics about all achievement levels.
        
        Returns:
            Dictionary with achievement level information
        """
        return self.achievement_levels.copy()


def create_nanoleet_detector() -> NanoLeetDetector:
    """
    Factory function to create a NanoLeetDetector instance.
    
    Returns:
        NanoLeetDetector instance
    """
    return NanoLeetDetector()

