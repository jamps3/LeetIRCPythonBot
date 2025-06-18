"""
Tests for ElectricityService module.

Tests electricity price functionality including API integration,
command parsing, and message formatting.
"""

import unittest
from unittest.mock import patch, Mock
import json
from datetime import datetime, timedelta
from io import StringIO

from services.electricity_service import ElectricityService, create_electricity_service


class TestElectricityService(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.service = ElectricityService(self.api_key)
    
    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        self.assertEqual(self.service.api_key, self.api_key)
        self.assertEqual(self.service.base_url, "https://web-api.tp.entsoe.eu/api")
        self.assertEqual(self.service.finland_domain, "10YFI-1--------U")
        self.assertEqual(self.service.vat_rate, 1.255)
    
    def test_factory_function(self):
        """Test the factory function."""
        service = create_electricity_service(self.api_key)
        self.assertIsInstance(service, ElectricityService)
        self.assertEqual(service.api_key, self.api_key)
    
    def test_price_conversion(self):
        """Test price conversion from EUR/MWh to snt/kWh with VAT."""
        # 100 EUR/MWh should be 12.55 snt/kWh with VAT
        result = self.service._convert_price(100.0)
        self.assertAlmostEqual(result, 12.55, places=2)
        
        # 50 EUR/MWh should be 6.275 snt/kWh with VAT
        result = self.service._convert_price(50.0)
        self.assertAlmostEqual(result, 6.275, places=2)
    
    def test_command_parsing_current_hour(self):
        """Test parsing command with no arguments (current hour)."""
        current_time = datetime.now()
        result = self.service.parse_command_args([])
        
        self.assertEqual(result['hour'], current_time.hour)
        self.assertIsNone(result['error'])
        self.assertFalse(result['is_tomorrow'])
        self.assertFalse(result['show_stats'])
    
    def test_command_parsing_specific_hour(self):
        """Test parsing command with specific hour."""
        result = self.service.parse_command_args(['15'])
        
        self.assertEqual(result['hour'], 15)
        self.assertIsNone(result['error'])
        self.assertFalse(result['is_tomorrow'])
        self.assertFalse(result['show_stats'])
    
    def test_command_parsing_tomorrow(self):
        """Test parsing command for tomorrow."""
        result = self.service.parse_command_args(['huomenna'])
        
        current_time = datetime.now()
        expected_date = current_time + timedelta(days=1)
        
        self.assertEqual(result['hour'], current_time.hour)
        self.assertIsNone(result['error'])
        self.assertTrue(result['is_tomorrow'])
        self.assertFalse(result['show_stats'])
        self.assertEqual(result['date'].date(), expected_date.date())
    
    def test_command_parsing_tomorrow_with_hour(self):
        """Test parsing command for tomorrow with specific hour."""
        result = self.service.parse_command_args(['huomenna', '10'])
        
        current_time = datetime.now()
        expected_date = current_time + timedelta(days=1)
        
        self.assertEqual(result['hour'], 10)
        self.assertIsNone(result['error'])
        self.assertTrue(result['is_tomorrow'])
        self.assertFalse(result['show_stats'])
        self.assertEqual(result['date'].date(), expected_date.date())
    
    def test_command_parsing_statistics(self):
        """Test parsing command for statistics."""
        result = self.service.parse_command_args(['tilastot'])
        
        self.assertIsNone(result['error'])
        self.assertFalse(result['is_tomorrow'])
        self.assertTrue(result['show_stats'])
    
    def test_command_parsing_invalid_hour(self):
        """Test parsing command with invalid hour."""
        result = self.service.parse_command_args(['25'])
        
        self.assertIsNotNone(result['error'])
        self.assertIn('Virheellinen tunti', result['error'])
    
    def test_command_parsing_invalid_tomorrow_hour(self):
        """Test parsing command with invalid hour for tomorrow."""
        result = self.service.parse_command_args(['huomenna', '25'])
        
        self.assertIsNotNone(result['error'])
        self.assertIn('Virheellinen tunti', result['error'])
    
    def test_command_parsing_invalid_command(self):
        """Test parsing invalid command."""
        result = self.service.parse_command_args(['invalid'])
        
        self.assertIsNotNone(result['error'])
        self.assertIn('Virheellinen komento', result['error'])
    
    @patch('requests.get')
    def test_fetch_daily_prices_success(self, mock_get):
        """Test successful API response parsing."""
        # Mock successful API response with XML data
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
    <TimeSeries>
        <Period>
            <Point>
                <position>1</position>
                <price.amount>50.0</price.amount>
            </Point>
            <Point>
                <position>2</position>
                <price.amount>45.5</price.amount>
            </Point>
        </Period>
    </TimeSeries>
</Publication_MarketDocument>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = xml_response
        mock_get.return_value = mock_response
        
        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)
        
        self.assertFalse(result['error'])
        self.assertEqual(result['date'], '2023-01-01')
        self.assertEqual(result['prices'][1], 50.0)
        self.assertEqual(result['prices'][2], 45.5)
        self.assertEqual(result['total_hours'], 2)
    
    @patch('requests.get')
    def test_fetch_daily_prices_api_error(self, mock_get):
        """Test API error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)
        
        self.assertTrue(result['error'])
        self.assertEqual(result['status_code'], 401)
        self.assertIn('Invalid ENTSO-E API key', result['message'])
    
    @patch('requests.get')
    def test_fetch_daily_prices_timeout(self, mock_get):
        """Test timeout handling."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()
        
        test_date = datetime(2023, 1, 1)
        result = self.service._fetch_daily_prices(test_date)
        
        self.assertTrue(result['error'])
        self.assertIn('timed out', result['message'])
    
    def test_format_price_message_success(self):
        """Test formatting of successful price data."""
        price_data = {
            'error': False,
            'date': '2023-01-01',
            'hour': 14,
            'today_price': {
                'eur_per_mwh': 50.0,
                'snt_per_kwh_with_vat': 6.275,
                'snt_per_kwh_no_vat': 5.0
            },
            'tomorrow_price': {
                'eur_per_mwh': 45.0,
                'snt_per_kwh_with_vat': 5.6475,
                'snt_per_kwh_no_vat': 4.5
            }
        }
        
        result = self.service.format_price_message(price_data)
        
        self.assertIn('⚡ Tänään 2023-01-01 klo 14: 6.28 snt/kWh', result)
        self.assertIn('⚡ Huomenna 2023-01-02 klo 14: 5.65 snt/kWh', result)
        self.assertIn('ALV 25,5%', result)
    
    def test_format_price_message_error(self):
        """Test formatting of error message."""
        price_data = {
            'error': True,
            'message': 'API error occurred'
        }
        
        result = self.service.format_price_message(price_data)
        
        self.assertIn('⚡ Sähkön hintatietojen haku epäonnistui', result)
        self.assertIn('API error occurred', result)
    
    def test_format_price_message_no_data(self):
        """Test formatting when no price data is available."""
        price_data = {
            'error': False,
            'date': '2023-01-01',
            'hour': 14,
            'today_price': None,
            'tomorrow_price': None
        }
        
        result = self.service.format_price_message(price_data)
        
        self.assertIn('⚡ Sähkön hintatietoja ei saatavilla tunnille 14', result)
        self.assertIn('https://sahko.tk', result)
    
    def test_format_statistics_message(self):
        """Test formatting of statistics message."""
        stats_data = {
            'error': False,
            'date': '2023-01-01',
            'min_price': {
                'hour': 3,
                'eur_per_mwh': 20.0,
                'snt_per_kwh_with_vat': 2.51
            },
            'max_price': {
                'hour': 18,
                'eur_per_mwh': 80.0,
                'snt_per_kwh_with_vat': 10.04
            },
            'avg_price': {
                'eur_per_mwh': 50.0,
                'snt_per_kwh_with_vat': 6.275
            }
        }
        
        result = self.service.format_statistics_message(stats_data)
        
        self.assertIn('📊 Sähkön hintatilastot 2023-01-01', result)
        self.assertIn('Min: 2.51 snt/kWh (klo 03)', result)
        self.assertIn('Max: 10.04 snt/kWh (klo 18)', result)
        self.assertIn('Keskiarvo: 6.28 snt/kWh', result)
    
    @patch.object(ElectricityService, '_fetch_daily_prices')
    def test_get_electricity_price_success(self, mock_fetch):
        """Test getting electricity price successfully."""
        # Mock the daily prices response
        mock_fetch.return_value = {
            'error': False,
            'prices': {
                15: 50.0,  # Hour 14 (0-indexed) maps to position 15 (1-indexed)
                16: 45.0
            }
        }
        
        test_date = datetime(2023, 1, 1, 14, 0)  # 14:00
        result = self.service.get_electricity_price(hour=14, date=test_date)
        
        self.assertFalse(result['error'])
        self.assertEqual(result['hour'], 14)
        self.assertIsNotNone(result['today_price'])
        self.assertEqual(result['today_price']['eur_per_mwh'], 50.0)
        self.assertAlmostEqual(result['today_price']['snt_per_kwh_with_vat'], 6.275, places=2)
    
    def test_get_electricity_price_invalid_hour(self):
        """Test getting electricity price with invalid hour."""
        result = self.service.get_electricity_price(hour=25)
        
        self.assertTrue(result['error'])
        self.assertIn('Invalid hour: 25', result['message'])


if __name__ == '__main__':
    # Run the tests
    unittest.main()

