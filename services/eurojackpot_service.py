#!/usr/bin/env python3
"""
Eurojackpot Service for LeetIRC Bot

This service handles Eurojackpot lottery information including:
- Getting next draw date, time and jackpot amount
- Getting last drawn numbers, date and jackpot winners
"""

import requests
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import logging


class EurojackpotService:
    """Service for Eurojackpot lottery information."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_base_url = "https://www.veikkaus.fi/api"
        self.eurojackpot_game_id = "eurojackpot"
        
    def _make_request(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """Make HTTP request and return JSON response."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error for {url}: {e}")
            return None
    
    def get_next_draw_info(self) -> Dict[str, any]:
        """
        Get information about the next Eurojackpot draw.
        
        Returns:
            Dict with draw date, time and jackpot amount
        """
        try:
            # Get next draw information
            url = f"{self.api_base_url}/draw-games/v1/games/{self.eurojackpot_game_id}/draws/next"
            data = self._make_request(url)
            
            if not data:
                return {
                    'success': False,
                    'message': 'Could not fetch next draw information'
                }
            
            # Extract information
            draw_time = data.get('drawTime')
            jackpot = data.get('jackpot', {})
            
            if not draw_time:
                return {
                    'success': False,
                    'message': 'Draw time not found in response'
                }
            
            # Parse draw time (ISO format)
            try:
                dt = datetime.fromisoformat(draw_time.replace('Z', '+00:00'))
                # Convert to local time (assuming Finnish time zone)
                # Note: This is a simple approach, in production you'd want proper timezone handling
                local_dt = dt + timedelta(hours=2)  # Finland is UTC+2 (or UTC+3 in summer)
                
                formatted_date = local_dt.strftime('%d.%m.%Y')
                formatted_time = local_dt.strftime('%H:%M')
                
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Error parsing draw time {draw_time}: {e}")
                return {
                    'success': False,
                    'message': 'Error parsing draw time'
                }
            
            # Format jackpot amount
            jackpot_amount = jackpot.get('amount', 0)
            jackpot_currency = jackpot.get('currency', 'EUR')
            
            # Format amount in millions
            if jackpot_amount >= 1000000:
                jackpot_text = f"{jackpot_amount / 1000000:.1f} miljoonaa {jackpot_currency}"
            else:
                jackpot_text = f"{jackpot_amount:,} {jackpot_currency}".replace(',', ' ')
            
            success_message = (
                f"🎰 Seuraava Eurojackpot: {formatted_date} klo {formatted_time} "
                f"| Potti: {jackpot_text}"
            )
            
            return {
                'success': True,
                'message': success_message,
                'date': formatted_date,
                'time': formatted_time,
                'jackpot_amount': jackpot_amount,
                'jackpot_text': jackpot_text
            }
            
        except Exception as e:
            self.logger.error(f"Error getting next draw info: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_last_results(self) -> Dict[str, any]:
        """
        Get the last drawn Eurojackpot numbers and results.
        
        Returns:
            Dict with last draw results
        """
        try:
            # Get latest draw results
            url = f"{self.api_base_url}/draw-games/v1/games/{self.eurojackpot_game_id}/draws/latest"
            data = self._make_request(url)
            
            if not data:
                return {
                    'success': False,
                    'message': 'Could not fetch latest draw results'
                }
            
            # Extract draw information
            draw_time = data.get('drawTime')
            results = data.get('results', {})
            primary_numbers = results.get('primary', [])
            secondary_numbers = results.get('secondary', [])
            
            if not draw_time or not primary_numbers:
                return {
                    'success': False,
                    'message': 'Draw results incomplete'
                }
            
            # Parse draw time
            try:
                dt = datetime.fromisoformat(draw_time.replace('Z', '+00:00'))
                local_dt = dt + timedelta(hours=2)  # Finland timezone adjustment
                formatted_date = local_dt.strftime('%d.%m.%Y')
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Error parsing draw time {draw_time}: {e}")
                formatted_date = "Unknown date"
            
            # Format numbers
            primary_str = " - ".join(f"{num:02d}" for num in sorted(primary_numbers))
            secondary_str = " - ".join(f"{num:02d}" for num in sorted(secondary_numbers))
            
            # Get prize information if available
            prize_info = data.get('prizeBreakdown', [])
            jackpot_winners = 0
            
            # Look for first prize (jackpot) winners
            for prize in prize_info:
                if prize.get('prizeRank') == 1:
                    jackpot_winners = prize.get('winners', 0)
                    break
            
            # Format message
            numbers_text = f"{primary_str} + {secondary_str}"
            winners_text = f"{jackpot_winners} jackpot-voittajaa" if jackpot_winners != 1 else "1 jackpot-voittaja"
            
            success_message = (
                f"🎰 Viimeisin Eurojackpot ({formatted_date}): "
                f"{numbers_text} | {winners_text}"
            )
            
            return {
                'success': True,
                'message': success_message,
                'date': formatted_date,
                'primary_numbers': primary_numbers,
                'secondary_numbers': secondary_numbers,
                'jackpot_winners': jackpot_winners,
                'numbers_text': numbers_text
            }
            
        except Exception as e:
            self.logger.error(f"Error getting last results: {e}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_frequent_numbers(self, limit: int = 10) -> Dict[str, any]:
        """
        Get most frequently drawn numbers (this would require historical data).
        
        Note: This is a placeholder implementation. In a real implementation,
        you would need to collect historical data or use an API that provides
        frequency statistics.
        
        Returns:
            Dict with frequently drawn numbers
        """
        # Placeholder implementation with mock data
        # In reality, you'd need to collect historical data
        mock_frequent_primary = [7, 14, 21, 28, 35]
        mock_frequent_secondary = [3, 7]
        
        primary_str = " - ".join(f"{num:02d}" for num in mock_frequent_primary)
        secondary_str = " - ".join(f"{num:02d}" for num in mock_frequent_secondary)
        
        return {
            'success': True,
            'message': f"🎰 Yleisimmät numerot (esimerkki): {primary_str} + {secondary_str}",
            'primary_numbers': mock_frequent_primary,
            'secondary_numbers': mock_frequent_secondary,
            'note': 'This is mock data - real implementation would need historical data collection'
        }


# Global service instance
_eurojackpot_service = None

def get_eurojackpot_service() -> EurojackpotService:
    """Get the global Eurojackpot service instance."""
    global _eurojackpot_service
    if _eurojackpot_service is None:
        _eurojackpot_service = EurojackpotService()
    return _eurojackpot_service


def get_eurojackpot_numbers() -> str:
    """
    Get Eurojackpot information (next draw by default).
    
    Returns:
        str: Formatted message with Eurojackpot information
    """
    service = get_eurojackpot_service()
    result = service.get_next_draw_info()
    return result['message']


def get_eurojackpot_results() -> str:
    """
    Get last Eurojackpot draw results.
    
    Returns:
        str: Formatted message with last draw results
    """
    service = get_eurojackpot_service()
    result = service.get_last_results()
    return result['message']

