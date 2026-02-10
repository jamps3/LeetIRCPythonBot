"""
Debug script for testing the !kaiku command with !crypto subcommand.

This demonstrates how !kaiku can execute subcommands and send results to a channel.
Example: !kaiku #channel !crypto btc
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from command_registry import CommandContext, CommandResponse
from commands import echo_command
from services.crypto_service import create_crypto_service


class MockServer:
    """Mock server that captures messages sent to channels."""

    def __init__(self):
        self.sent_messages = []

    def send_message(self, target, message):
        """Mock send_message that captures the message."""
        self.sent_messages.append((target, message))
        print(f"[MockServer] Message sent to {target}: {message}")


async def test_kaiku_with_crypto():
    """Test !kaiku #channel !crypto btc command flow."""
    print("=" * 60)
    print("Testing: !kaiku #test !crypto btc")
    print("=" * 60)

    # Create mock server
    mock_server = MockServer()

    # Create actual crypto service
    crypto_service = create_crypto_service()

    # Wrapper function that matches what crypto_command expects
    def get_crypto_price(coin, currency="eur"):
        result = crypto_service.get_crypto_price(coin, currency)
        if result.get("error"):
            raise Exception(result.get("message", "Crypto service error"))
        return result["price"]

    # Create bot_functions with the mock server and crypto service
    bot_functions = {
        "server": mock_server,
        "get_crypto_price": get_crypto_price,
    }

    # Create context for !kaiku #test !crypto btc
    context = CommandContext(
        command="kaiku",
        args=["#test", "!crypto", "btc"],
        raw_message="!kaiku #test !crypto btc",
        sender="test_user",
        target="#debug",
        server_name="test_server",
        is_console=False,
    )

    # Execute the kaiku command
    response = await echo_command(context, bot_functions)

    # Check results
    print("\n" + "-" * 60)
    print("Results:")
    print("-" * 60)

    if mock_server.sent_messages:
        print(
            f"✅ Successfully sent {len(mock_server.sent_messages)} message(s) to channel:"
        )
        for target, msg in mock_server.sent_messages:
            print(f"   -> {target}: {msg}")
    else:
        print("❌ No messages were sent to the channel")

    if response and hasattr(response, "message"):
        print(f"\nCommand response: {response.message}")
    elif response:
        print(f"\nCommand response: {response}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def test_kaiku_with_weather():
    """Test !kaiku #channel !s command flow."""
    print("\n" + "=" * 60)
    print("Testing: !kaiku #test !s")
    print("=" * 60)

    # Create mock server
    mock_server = MockServer()

    # Create bot_functions with just the mock server
    bot_functions = {
        "server": mock_server,
    }

    # Create context for !kaiku #test !s
    context = CommandContext(
        command="kaiku",
        args=["#test", "!s"],
        raw_message="!kaiku #test !s",
        sender="test_user",
        target="#debug",
        server_name="test_server",
        is_console=False,
    )

    # Execute the kaiku command
    response = await echo_command(context, bot_functions)

    # Check results
    print("\n" + "-" * 60)
    print("Results:")
    print("-" * 60)

    if mock_server.sent_messages:
        print(
            f"✅ Successfully sent {len(mock_server.sent_messages)} message(s) to channel:"
        )
        for target, msg in mock_server.sent_messages:
            print(f"   -> {target}: {msg}")
    else:
        print("❌ No messages were sent to the channel")

    if response and hasattr(response, "message"):
        print(f"\nCommand response: {response.message}")
    elif response:
        print(f"\nCommand response: {response}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def test_kaiku_with_np():
    """Test !kaiku #channel !np command flow."""
    print("\n" + "=" * 60)
    print("Testing: !kaiku #test !np")
    print("=" * 60)

    # Create mock server
    mock_server = MockServer()

    # Create bot_functions with just the mock server
    bot_functions = {
        "server": mock_server,
    }

    # Create context for !kaiku #test !np
    context = CommandContext(
        command="kaiku",
        args=["#test", "!np"],
        raw_message="!kaiku #test !np",
        sender="test_user",
        target="#debug",
        server_name="test_server",
        is_console=False,
    )

    # Execute the kaiku command
    response = await echo_command(context, bot_functions)

    # Check results
    print("\n" + "-" * 60)
    print("Results:")
    print("-" * 60)

    if mock_server.sent_messages:
        print(
            f"✅ Successfully sent {len(mock_server.sent_messages)} message(s) to channel:"
        )
        for target, msg in mock_server.sent_messages:
            print(f"   -> {target}: {msg}")
    else:
        print("❌ No messages were sent to the channel")

    if response and hasattr(response, "message"):
        print(f"\nCommand response: {response.message}")
    elif response:
        print(f"\nCommand response: {response}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def test_kaiku_with_muunnos():
    """Test !kaiku #channel !muunnos command flow."""
    print("\n" + "=" * 60)
    print("Testing: !kaiku #test !muunnos")
    print("=" * 60)

    # Create mock server
    mock_server = MockServer()

    # Create bot_functions with just the mock server
    bot_functions = {
        "server": mock_server,
    }

    # Create context for !kaiku #test !muunnos
    context = CommandContext(
        command="kaiku",
        args=["#test", "!muunnos"],
        raw_message="!kaiku #test !muunnos",
        sender="test_user",
        target="#debug",
        server_name="test_server",
        is_console=False,
    )

    # Execute the kaiku command
    response = await echo_command(context, bot_functions)

    # Check results
    print("\n" + "-" * 60)
    print("Results:")
    print("-" * 60)

    if mock_server.sent_messages:
        print(
            f"✅ Successfully sent {len(mock_server.sent_messages)} message(s) to channel:"
        )
        for target, msg in mock_server.sent_messages:
            print(f"   -> {target}: {msg}")
    else:
        print("❌ No messages were sent to the channel")

    if response and hasattr(response, "message"):
        print(f"\nCommand response: {response.message}")
    elif response:
        print(f"\nCommand response: {response}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


async def main():
    """Run all tests."""
    await test_kaiku_with_crypto()
    await test_kaiku_with_weather()
    await test_kaiku_with_np()
    await test_kaiku_with_muunnos()


if __name__ == "__main__":
    asyncio.run(main())
