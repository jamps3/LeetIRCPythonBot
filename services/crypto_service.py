"""
Cryptocurrency Service Module

Provides cryptocurrency price information using CoinGecko API.
"""

import requests
from typing import Dict, Any, List, Optional
from datetime import datetime


class CryptoService:
    """Service for fetching cryptocurrency information."""

    def __init__(self):
        """Initialize cryptocurrency service."""
        self.base_url = "https://api.coingecko.com/api/v3"

        # Common cryptocurrency mappings
        self.crypto_aliases = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "ada": "cardano",
            "dot": "polkadot",
            "link": "chainlink",
            "xrp": "ripple",
            "ltc": "litecoin",
            "bch": "bitcoin-cash",
            "bnb": "binancecoin",
            "usdt": "tether",
            "usdc": "usd-coin",
            "sol": "solana",
            "avax": "avalanche-2",
            "matic": "matic-network",
            "uni": "uniswap",
            "atom": "cosmos",
            "xlm": "stellar",
            "vet": "vechain",
            "algo": "algorand",
            "xtz": "tezos",
        }

        # Supported currencies
        self.supported_currencies = ["eur", "usd", "btc", "eth"]

    def get_crypto_price(self, coin: str, currency: str = "eur") -> Dict[str, Any]:
        """
        Get cryptocurrency price information.

        Args:
            coin: Cryptocurrency symbol or name (e.g., 'bitcoin', 'btc')
            currency: Target currency (default: 'eur')

        Returns:
            Dictionary containing price information or error details
        """
        try:
            # Normalize inputs
            coin = coin.lower().strip()
            currency = currency.lower().strip()

            # Handle aliases
            if coin in self.crypto_aliases:
                coin_id = self.crypto_aliases[coin]
            else:
                coin_id = coin

            # Validate currency
            if currency not in self.supported_currencies:
                return {
                    "error": True,
                    "message": f"Unsupported currency: {currency}. Supported: {', '.join(self.supported_currencies)}",
                }

            # Fetch price data
            url = f"{self.base_url}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": currency,
                "include_24hr_change": "true",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_last_updated_at": "true",
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return self._parse_price_data(data, coin_id, currency)
            else:
                return {
                    "error": True,
                    "message": f"CoinGecko API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

        except requests.exceptions.Timeout:
            return {
                "error": True,
                "message": "CoinGecko API request timed out",
                "exception": "timeout",
            }
        except requests.exceptions.RequestException as e:
            return {
                "error": True,
                "message": f"CoinGecko API request failed: {str(e)}",
                "exception": str(e),
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Unexpected error: {str(e)}",
                "exception": str(e),
            }

    def _parse_price_data(
        self, data: Dict[str, Any], coin_id: str, currency: str
    ) -> Dict[str, Any]:
        """
        Parse price data from API response.

        Args:
            data: Raw price data from API
            coin_id: Cryptocurrency ID
            currency: Target currency

        Returns:
            Parsed price information
        """
        try:
            if coin_id not in data:
                return {
                    "error": True,
                    "message": f"Cryptocurrency '{coin_id}' not found. Check spelling or try different name.",
                }

            coin_data = data[coin_id]

            # Extract price data
            price = coin_data.get(currency)
            change_24h = coin_data.get(f"{currency}_24h_change")
            market_cap = coin_data.get(f"{currency}_market_cap")
            volume_24h = coin_data.get(f"{currency}_24h_vol")
            last_updated = coin_data.get("last_updated_at")

            if price is None:
                return {
                    "error": True,
                    "message": f"Price data not available for {coin_id} in {currency.upper()}",
                }

            return {
                "error": False,
                "coin_id": coin_id,
                "currency": currency.upper(),
                "price": price,
                "change_24h": change_24h,
                "market_cap": market_cap,
                "volume_24h": volume_24h,
                "last_updated": (
                    datetime.fromtimestamp(last_updated) if last_updated else None
                ),
            }

        except KeyError as e:
            return {
                "error": True,
                "message": f"Missing required field in price data: {e}",
                "exception": str(e),
            }
        except Exception as e:
            return {
                "error": True,
                "message": f"Error parsing price data: {str(e)}",
                "exception": str(e),
            }

    def get_trending_cryptos(self, limit: int = 7) -> Dict[str, Any]:
        """
        Get trending cryptocurrencies.

        Args:
            limit: Number of trending coins to return (default: 7)

        Returns:
            Dictionary containing trending cryptocurrencies or error details
        """
        try:
            url = f"{self.base_url}/search/trending"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                trending_coins = data.get("coins", [])[:limit]

                return {
                    "error": False,
                    "trending": [
                        {
                            "id": coin["item"]["id"],
                            "name": coin["item"]["name"],
                            "symbol": coin["item"]["symbol"],
                            "rank": coin["item"]["market_cap_rank"],
                            "score": coin["item"]["score"],
                        }
                        for coin in trending_coins
                    ],
                }
            else:
                return {
                    "error": True,
                    "message": f"Trending API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error fetching trending cryptos: {str(e)}",
                "exception": str(e),
            }

    def search_crypto(self, query: str) -> Dict[str, Any]:
        """
        Search for cryptocurrencies by name or symbol.

        Args:
            query: Search query

        Returns:
            Dictionary containing search results or error details
        """
        try:
            url = f"{self.base_url}/search"
            params = {"query": query}
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                coins = data.get("coins", [])[:5]  # Limit to top 5 results

                return {
                    "error": False,
                    "results": [
                        {
                            "id": coin["id"],
                            "name": coin["name"],
                            "symbol": coin["symbol"],
                            "rank": coin.get("market_cap_rank"),
                            "thumb": coin.get("thumb"),
                        }
                        for coin in coins
                    ],
                }
            else:
                return {
                    "error": True,
                    "message": f"Search API returned status code {response.status_code}",
                    "status_code": response.status_code,
                }

        except Exception as e:
            return {
                "error": True,
                "message": f"Error searching cryptos: {str(e)}",
                "exception": str(e),
            }

    def format_price_message(self, price_data: Dict[str, Any]) -> str:
        """
        Format price data into a readable message.

        Args:
            price_data: Price data dictionary

        Returns:
            Formatted price message string
        """
        if price_data.get("error"):
            return f"💸 Kryptohaku epäonnistui: {price_data.get('message', 'Tuntematon virhe')}"

        coin_name = price_data["coin_id"].replace("-", " ").title()
        currency_symbol = self._get_currency_symbol(price_data["currency"])
        price = price_data["price"]
        change_24h = price_data.get("change_24h")

        # Format price based on value
        if price >= 1:
            price_str = f"{price:,.2f}"
        elif price >= 0.01:
            price_str = f"{price:.4f}"
        else:
            price_str = f"{price:.8f}"

        message = f"💰 {coin_name}: {currency_symbol}{price_str}"

        # Add 24h change if available
        if change_24h is not None:
            change_emoji = "📈" if change_24h >= 0 else "📉"
            change_str = f"{change_24h:+.2f}%"
            message += f" ({change_emoji} {change_str})"

        # Add market cap if available and significant
        if price_data.get("market_cap") and price_data["market_cap"] > 1000000:
            market_cap = price_data["market_cap"]
            if market_cap >= 1e9:
                cap_str = f"{market_cap/1e9:.1f}B"
            elif market_cap >= 1e6:
                cap_str = f"{market_cap/1e6:.1f}M"
            else:
                cap_str = f"{market_cap/1e3:.1f}K"
            message += f" | 📊 {currency_symbol}{cap_str}"

        return message

    def format_trending_message(self, trending_data: Dict[str, Any]) -> str:
        """
        Format trending data into a readable message.

        Args:
            trending_data: Trending data dictionary

        Returns:
            Formatted trending message string
        """
        if trending_data.get("error"):
            return f"🔥 Trending-haku epäonnistui: {trending_data.get('message', 'Tuntematon virhe')}"

        trending_coins = trending_data.get("trending", [])
        if not trending_coins:
            return "🔥 Ei trending-kryptoja saatavilla tällä hetkellä."

        coin_list = []
        for i, coin in enumerate(trending_coins[:5], 1):
            symbol = coin["symbol"].upper()
            name = coin["name"]
            coin_list.append(f"{i}. {symbol} ({name})")

        return f"🔥 Trending kryptot: {', '.join(coin_list)}"

    def _get_currency_symbol(self, currency: str) -> str:
        """Get currency symbol for display."""
        symbols = {"EUR": "€", "USD": "$", "BTC": "₿", "ETH": "Ξ"}
        return symbols.get(currency.upper(), currency.upper() + " ")

    def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies."""
        return self.supported_currencies.copy()

    def get_crypto_aliases(self) -> Dict[str, str]:
        """Get dictionary of cryptocurrency aliases."""
        return self.crypto_aliases.copy()


def create_crypto_service() -> CryptoService:
    """
    Factory function to create a cryptocurrency service instance.

    Returns:
        CryptoService instance
    """
    return CryptoService()
