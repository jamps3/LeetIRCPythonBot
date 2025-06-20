#!/usr/bin/env python3
"""
Scheduled Message Service for LeetIRC Bot

This service handles the scheduling and execution of messages at specific times
with microsecond precision.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
import logging


class ScheduledMessageService:
    """Service for scheduling messages to be sent at specific times."""

    def __init__(self):
        self.scheduled_messages: Dict[str, dict] = {}
        self.thread_pool = {}
        self.logger = logging.getLogger(__name__)

    def schedule_message(
        self,
        irc_client,
        channel: str,
        message: str,
        target_hour: int,
        target_minute: int,
        target_second: int,
        target_microsecond: int = 0,
        message_id: Optional[str] = None,
    ) -> str:
        """
        Schedule a message to be sent at a specific time.

        Args:
            irc_client: IRC client to send messages through
            channel: Target channel
            message: Message to send
            target_hour: Hour (0-23)
            target_minute: Minute (0-59)
            target_second: Second (0-59)
            target_microsecond: Microsecond (0-999999)
            message_id: Optional ID for the scheduled message

        Returns:
            str: Message ID for tracking/cancellation
        """
        # Generate message ID if not provided
        if not message_id:
            message_id = f"scheduled_{int(time.time())}_{len(self.scheduled_messages)}"

        # Calculate target time
        now = datetime.now()
        target_time = now.replace(
            hour=target_hour,
            minute=target_minute,
            second=target_second,
            microsecond=target_microsecond,
        )

        # If target time is in the past, schedule for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)

        # Calculate delay in seconds
        delay = (target_time - now).total_seconds()

        self.logger.info(
            f"Scheduling message '{message}' to {channel} at {target_time} "
            f"(in {delay:.6f} seconds)"
        )

        # Store scheduled message info
        self.scheduled_messages[message_id] = {
            "irc_client": irc_client,
            "channel": channel,
            "message": message,
            "target_time": target_time,
            "delay": delay,
            "scheduled_at": now,
        }

        # Create and start timer thread
        timer_thread = threading.Timer(
            delay, self._send_scheduled_message, args=[message_id]
        )
        timer_thread.daemon = True
        timer_thread.start()

        self.thread_pool[message_id] = timer_thread

        return message_id

    def _send_scheduled_message(self, message_id: str):
        """Send a scheduled message and clean up."""
        if message_id not in self.scheduled_messages:
            self.logger.warning(f"Scheduled message {message_id} not found")
            return

        msg_info = self.scheduled_messages[message_id]

        try:
            # Send the message
            irc_client = msg_info["irc_client"]
            channel = msg_info["channel"]
            message = msg_info["message"]

            if hasattr(irc_client, "send_message"):
                irc_client.send_message(channel, message)
            else:
                # Legacy socket interface
                irc_client.sendall(f"PRIVMSG {channel} :{message}\r\n".encode("utf-8"))

            actual_time = datetime.now()
            expected_time = msg_info["target_time"]
            time_diff = abs((actual_time - expected_time).total_seconds())

            self.logger.info(
                f"Sent scheduled message '{message}' to {channel} at {actual_time} "
                f"(expected: {expected_time}, diff: {time_diff:.6f}s)"
            )

        except Exception as e:
            self.logger.error(f"Error sending scheduled message {message_id}: {e}")

        finally:
            # Clean up
            self.scheduled_messages.pop(message_id, None)
            self.thread_pool.pop(message_id, None)

    def cancel_message(self, message_id: str) -> bool:
        """
        Cancel a scheduled message.

        Args:
            message_id: ID of the message to cancel

        Returns:
            bool: True if cancelled, False if not found
        """
        if message_id in self.thread_pool:
            timer = self.thread_pool[message_id]
            timer.cancel()

            # Clean up
            self.scheduled_messages.pop(message_id, None)
            self.thread_pool.pop(message_id, None)

            self.logger.info(f"Cancelled scheduled message {message_id}")
            return True

        return False

    def list_scheduled_messages(self) -> Dict[str, dict]:
        """Get list of currently scheduled messages."""
        result = {}
        for msg_id, msg_info in self.scheduled_messages.items():
            result[msg_id] = {
                "channel": msg_info["channel"],
                "message": msg_info["message"],
                "target_time": msg_info["target_time"].isoformat(),
                "scheduled_at": msg_info["scheduled_at"].isoformat(),
                "delay": msg_info["delay"],
            }
        return result

    def cleanup_expired(self):
        """Clean up expired scheduled messages."""
        now = datetime.now()
        expired_ids = []

        for msg_id, msg_info in self.scheduled_messages.items():
            if msg_info["target_time"] < now:
                expired_ids.append(msg_id)

        for msg_id in expired_ids:
            self.cancel_message(msg_id)

        if expired_ids:
            self.logger.info(
                f"Cleaned up {len(expired_ids)} expired scheduled messages"
            )


# Global service instance
_scheduled_message_service = None


def get_scheduled_message_service() -> ScheduledMessageService:
    """Get the global scheduled message service instance."""
    global _scheduled_message_service
    if _scheduled_message_service is None:
        _scheduled_message_service = ScheduledMessageService()
    return _scheduled_message_service


def send_scheduled_message(
    irc_client,
    channel: str,
    message: str,
    hour: int,
    minute: int,
    second: int,
    microsecond: int = 0,
) -> str:
    """
    Convenience function to schedule a message.

    Args:
        irc_client: IRC client to send messages through
        channel: Target channel
        message: Message to send
        hour: Hour (0-23)
        minute: Minute (0-59)
        second: Second (0-59)
        microsecond: Microsecond (0-999999)

    Returns:
        str: Message ID for tracking/cancellation
    """
    service = get_scheduled_message_service()
    return service.schedule_message(
        irc_client, channel, message, hour, minute, second, microsecond
    )
