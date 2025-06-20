#!/usr/bin/env python3
"""
Eurojackpot Service for LeetIRC Bot

This service handles Eurojackpot lottery information using the Magayo API.
Integrated from eurojackpot.py functionality.
"""

import requests
import os
from datetime import datetime
from typing import Dict, Optional
import logging
from dotenv import load_dotenv

load_dotenv()


class EurojackpotService:
    """Service for Eurojackpot lottery information using Magayo API."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = os.getenv("EUROJACKPOT_API_KEY")
        self.next_draw_url = "https://www.magayo.com/api/next_draw.php"
        self.jackpot_url = "https://www.magayo.com/api/jackpot.php"
        self.results_url = "https://www.magayo.com/api/results.php"
        
    def get_week_number(self, date_str: str) -> int:
        """Get ISO week number from date string."""
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.isocalendar()[1]
    
    def _make_request(self, url: str, params: Dict, timeout: int = 10) -> Optional[Dict]:
        """Make HTTP request with Magayo API parameters and return JSON response."""
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"JSON decode error for {url}: {e}")
            return None
    
    def get_next_draw_info(self) -> Dict[str, any]:
        """
        Get information about the next Eurojackpot draw using Magayo API.
        
        Returns:
            Dict with draw date, time and jackpot amount
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'message': 'EUROJACKPOT_API_KEY not configured'
                }
            
            # Get next draw information
            params = {"api_key": self.api_key, "game": "eurojackpot", "format": "json"}
            draw_data = self._make_request(self.next_draw_url, params)
            jackpot_data = self._make_request(self.jackpot_url, params)
            
            if not draw_data or not jackpot_data:
                return {
                    'success': False,
                    'message': 'Could not fetch next draw information'
                }
                
            if draw_data.get("error") != 0 or jackpot_data.get("error") != 0:
                return {
                    'success': False,
                    'message': 'Eurojackpot: Virhe seuraavan arvonnan tietojen hakemisessa.'
                }
            
            # Extract and format information
            draw_date_iso = draw_data["next_draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
            week_number = self.get_week_number(draw_date_iso)
            jackpot = jackpot_data["jackpot"]
            currency = jackpot_data["currency"]
            
            success_message = f"Seuraava Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Päävoitto: {jackpot} {currency}"
            
            return {
                'success': True,
                'message': success_message,
                'date': draw_date,
                'week_number': week_number,
                'jackpot': jackpot,
                'currency': currency
            }
            
        except Exception as e:
            self.logger.error(f"Error getting next draw info: {e}")
            return {
                'success': False,
                'message': f'Eurojackpot: Virhe {str(e)}'
            }
    
    def get_last_results(self) -> Dict[str, any]:
        """
        Get the last drawn Eurojackpot numbers and results using Magayo API.
        
        Returns:
            Dict with last draw results
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'message': 'EUROJACKPOT_API_KEY not configured'
                }
            
            # Get latest draw results
            params = {"api_key": self.api_key, "game": "eurojackpot", "format": "json"}
            data = self._make_request(self.results_url, params)
            
            if not data:
                return {
                    'success': False,
                    'message': 'Could not fetch latest draw results'
                }
                
            if data.get("error") != 0:
                return {
                    'success': False,
                    'message': f"Eurojackpot: Virhe {data.get('error')}."
                }
            
            # Extract and format information
            draw_date_iso = data["draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
            week_number = self.get_week_number(draw_date_iso)
            numbers = data["results"].split(",")
            main = " ".join(numbers[:5])
            euro = " ".join(numbers[5:])
            jackpot = data.get("jackpot", "Tuntematon")
            currency = data.get("currency", "")
            
            success_message = f"Viimeisin Eurojackpot-arvonta: {draw_date} (viikko {week_number}) | Numerot: {main} + {euro} | Suurin voitto: {jackpot} {currency}"
            
            return {
                'success': True,
                'message': success_message,
                'date': draw_date,
                'week_number': week_number,
                'numbers': numbers,
                'main_numbers': main,
                'euro_numbers': euro,
                'jackpot': jackpot,
                'currency': currency
            }
            
        except Exception as e:
            self.logger.error(f"Error getting last results: {e}")
            return {
                'success': False,
                'message': f'Eurojackpot: Virhe {str(e)}'
            }
    
    def get_draw_by_date(self, date_str: str) -> Dict[str, any]:
        """
        Get Eurojackpot draw results for a specific date.
        
        Args:
            date_str: Date string in format DD.MM.YY
            
        Returns:
            Dict with draw results for the specified date
        """
        try:
            if not self.api_key:
                return {
                    'success': False,
                    'message': 'EUROJACKPOT_API_KEY not configured'
                }
            
            # Parse and validate date
            try:
                query_date = datetime.strptime(date_str, "%d.%m.%y").strftime("%Y-%m-%d")
            except ValueError:
                return {
                    'success': False,
                    'message': "Eurojackpot: Virheellinen päivämäärä. Käytä muotoa PP.KK.VV."
                }
            
            # Get draw results for specific date
            params = {
                "api_key": self.api_key,
                "game": "eurojackpot",
                "draw": query_date,
                "format": "json",
            }
            data = self._make_request(self.results_url, params)
            
            if not data:
                return {
                    'success': False,
                    'message': 'Could not fetch draw results'
                }
                
            if data.get("error") != 0:
                return {
                    'success': False,
                    'message': f"Eurojackpot: Arvontaa ei löytynyt päivämäärälle {date_str} tai sen jälkeen."
                }
            
            # Extract and format information
            draw_date_iso = data["draw"]
            draw_date = datetime.strptime(draw_date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
            week_number = self.get_week_number(draw_date_iso)
            numbers = data["results"].split(",")
            main = " ".join(numbers[:5])
            euro = " ".join(numbers[5:])
            jackpot = data.get("jackpot", "Tuntematon")
            currency = data.get("currency", "")
            
            success_message = f"Eurojackpot-arvonta {draw_date} (viikko {week_number}): {main} + {euro} | Suurin voitto: {jackpot} {currency}"
            
            return {
                'success': True,
                'message': success_message,
                'date': draw_date,
                'week_number': week_number,
                'numbers': numbers,
                'main_numbers': main,
                'euro_numbers': euro,
                'jackpot': jackpot,
                'currency': currency
            }
            
        except Exception as e:
            self.logger.error(f"Error getting draw by date: {e}")
            return {
                'success': False,
                'message': f'Eurojackpot: Virhe {str(e)}'
            }
    
    def get_combined_info(self) -> str:
        """
        Get combined information showing both latest and next draw.
        
        Returns:
            str: Combined message with latest and next draw info
        """
        latest_result = self.get_last_results()
        next_result = self.get_next_draw_info()
        
        if latest_result['success'] and next_result['success']:
            return f"{latest_result['message']}\n{next_result['message']}"
        elif latest_result['success']:
            return latest_result['message']
        elif next_result['success']:
            return next_result['message']
        else:
            return "Eurojackpot: Tietojen hakeminen epäonnistui."
    
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


def eurojackpot_command(arg=None) -> str:
    """
    Main Eurojackpot command function matching original eurojackpot.py functionality.
    
    Args:
        arg: Optional argument (date string in DD.MM.YY format)
        
    Returns:
        str: Formatted Eurojackpot information
    """
    service = get_eurojackpot_service()
    
    if arg is None:
        # Return combined info (latest + next draw)
        return service.get_combined_info()
    else:
        # Return draw for specific date
        result = service.get_draw_by_date(arg)
        return result['message']

