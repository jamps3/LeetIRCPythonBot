#!/usr/bin/env python3
"""
Scheduled Message Service for LeetIRCPythonBot

This service handles the scheduling and execution of messages at specific times
with microsecond precision.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional


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
        Backward-compatible wrapper: accepts microseconds, schedules using nanoseconds.
        """
        # Convert microseconds to nanoseconds
        us = max(0, min(999_999, int(target_microsecond)))
        ns = us * 1_000
        return self.schedule_message_ns(
            irc_client,
            channel,
            message,
            target_hour,
            target_minute,
            target_second,
            ns,
            message_id,
        )

    def schedule_message_ns(
        self,
        irc_client,
        channel: str,
        message: str,
        target_hour: int,
        target_minute: int,
        target_second: int,
        target_nanosecond: int = 0,
        message_id: Optional[str] = None,
    ) -> str:
        """
        Schedule a message using nanosecond-resolution targeting (no datetime).
        """
        # Clamp inputs
        hour = max(0, min(23, int(target_hour)))
        minute = max(0, min(59, int(target_minute)))
        second = max(0, min(59, int(target_second)))
        nano = max(0, min(999_999_999, int(target_nanosecond)))

        # Generate message ID if not provided
        if not message_id:
            message_id = f"scheduled_{int(time.time())}_{len(self.scheduled_messages)}"

        # Compute next occurrence (local time)
        now_ns = time.time_ns()
        now_s = now_ns // 1_000_000_000
        lt = time.localtime(now_s)
        sod_now = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
        sod_target = hour * 3600 + minute * 60 + second
        midnight_today_s = now_s - sod_now
        target_epoch_ns = (midnight_today_s + sod_target) * 1_000_000_000 + nano
        if target_epoch_ns <= now_ns:
            target_epoch_ns += 24 * 3600 * 1_000_000_000

        delay_ns = target_epoch_ns - now_ns
        delay_s = delay_ns / 1_000_000_000.0
        target_display = f"{hour:02d}:{minute:02d}:{second:02d}.{nano:09d}"

        self.logger.info(
            f"Scheduling message '{message}' to {channel} at {target_display} (in {delay_s:.9f} seconds)"
        )

        # Store info
        self.scheduled_messages[message_id] = {
            "irc_client": irc_client,
            "channel": channel,
            "message": message,
            "target_epoch_ns": target_epoch_ns,
            "target_display": target_display,
            "scheduled_at_ns": now_ns,
            "delay_ns": delay_ns,
            "cancelled": False,
        }

        # Start waiter thread (hybrid sleep + spin)
        waiter = threading.Thread(
            target=self._wait_and_send, args=(message_id,), daemon=True
        )
        waiter.start()
        self.thread_pool[message_id] = waiter
        return message_id

    def _send_scheduled_message(self, message_id: str):
        """Send a scheduled message and clean up."""
        if message_id not in self.scheduled_messages:
            self.logger.warning(f"Scheduled message {message_id} not found")
            return

        msg_info = self.scheduled_messages.get(message_id, {})
        if msg_info.get("cancelled"):
            # Already cancelled, clean up
            self.scheduled_messages.pop(message_id, None)
            self.thread_pool.pop(message_id, None)
            self.logger.info(f"Cancelled scheduled message {message_id} was skipped")
            return

        try:
            # Send the message
            irc_client = msg_info.get("irc_client")
            channel = msg_info.get("channel")
            message = msg_info.get("message")

            if hasattr(irc_client, "send_message") and callable(
                getattr(irc_client, "send_message")
            ):
                irc_client.send_message(channel, message)
            elif hasattr(irc_client, "send_raw") and callable(
                getattr(irc_client, "send_raw")
            ):
                irc_client.send_raw(f"PRIVMSG {channel} :{message}")
            else:
                self.logger.error(
                    "IRC client does not support send_message or send_raw; cannot send scheduled message"
                )

            actual_ns = time.time_ns()
            expected_ns = msg_info.get("target_epoch_ns", actual_ns)
            diff_s = abs(actual_ns - expected_ns) / 1_000_000_000.0

            # Format for log
            act_s = actual_ns // 1_000_000_000
            act_rem = actual_ns % 1_000_000_000
            lt = time.localtime(act_s)
            actual_display = (
                f"{lt.tm_hour:02d}:{lt.tm_min:02d}:{lt.tm_sec:02d}.{act_rem:09d}"
            )
            expected_display = msg_info.get("target_display", f"{expected_ns}")

            self.logger.info(
                f"Sent scheduled message '{message}' to {channel} at {actual_display} (expected: {expected_display}, diff: {diff_s:.9f}s)"
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
            # Mark cancelled so the waiter exits without sending
            if message_id in self.scheduled_messages:
                self.scheduled_messages[message_id]["cancelled"] = True
            # Threads can't be forcefully killed; best effort cleanup
            thread = self.thread_pool.pop(message_id, None)
            self.scheduled_messages.pop(message_id, None)
            self.logger.info(f"Cancelled scheduled message {message_id}")
            return True
        return False

    def list_scheduled_messages(self) -> Dict[str, dict]:
        """Get list of currently scheduled messages."""
        result = {}
        for msg_id, msg_info in self.scheduled_messages.items():
            sched_ns = msg_info.get("scheduled_at_ns", time.time_ns())
            sched_s = sched_ns // 1_000_000_000
            sched_rem = sched_ns % 1_000_000_000
            lt = time.localtime(sched_s)
            scheduled_display = (
                f"{lt.tm_hour:02d}:{lt.tm_min:02d}:{lt.tm_sec:02d}.{sched_rem:09d}"
            )

            result[msg_id] = {
                "channel": msg_info.get("channel"),
                "message": msg_info.get("message"),
                "target_time": msg_info.get("target_display"),
                "scheduled_at": scheduled_display,
                "delay": msg_info.get("delay_ns", 0) / 1_000_000_000.0,
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

    def _wait_and_send(self, message_id: str):
        """Hybrid sleep + spin wait until target time (nanosecond precision)."""
        info = self.scheduled_messages.get(message_id)
        if not info:
            return
        target_ns = info.get("target_epoch_ns")
        if not isinstance(target_ns, int):
            self._send_scheduled_message(message_id)
            return

        while True:
            if info.get("cancelled"):
                # Clean up and exit
                self.scheduled_messages.pop(message_id, None)
                self.thread_pool.pop(message_id, None)
                self.logger.info(
                    f"Cancelled scheduled message {message_id} before send"
                )
                return
            now_ns = time.time_ns()
            remaining = target_ns - now_ns
            if remaining <= 0:
                break
            if remaining > 5_000_000:  # > 5 ms
                # Sleep leaving 2 ms margin
                sleep_ns = remaining - 2_000_000
                time.sleep(max(0.0, sleep_ns / 1_000_000_000.0))
            else:
                # Fine spin using perf_counter_ns
                start = time.perf_counter_ns()
                end = start + remaining
                while time.perf_counter_ns() < end:
                    if info.get("cancelled"):
                        self.scheduled_messages.pop(message_id, None)
                        self.thread_pool.pop(message_id, None)
                        self.logger.info(
                            f"Cancelled scheduled message {message_id} during spin"
                        )
                        return
                break
        self._send_scheduled_message(message_id)


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
    Convenience wrapper: microseconds input; schedules using nanoseconds.
    """
    # Convert microseconds to nanoseconds
    us = max(0, min(999_999, int(microsecond)))
    ns = us * 1_000
    return send_scheduled_message_ns(
        irc_client, channel, message, hour, minute, second, ns
    )


def send_scheduled_message_ns(
    irc_client,
    channel: str,
    message: str,
    hour: int,
    minute: int,
    second: int,
    nanosecond: int = 0,
) -> str:
    """
    Convenience function to schedule a message with nanosecond resolution.
    """
    service = get_scheduled_message_service()
    return service.schedule_message_ns(
        irc_client, channel, message, hour, minute, second, nanosecond
    )
