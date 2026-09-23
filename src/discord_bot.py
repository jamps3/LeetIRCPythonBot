"""Discord transport for LeetIRCPythonBot.

The transport deliberately delegates commands and shared services to the
existing bot rather than maintaining a second feature implementation.
"""

from __future__ import annotations

import asyncio
import os
import re
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Callable

import logger
from command_loader import ensure_commands_loaded
from command_registry import (
    CommandContext,
    get_command_registry,
    process_command_message,
)
from state_utils import update_json_file

CORE_COMMANDS = {
    "help": "help",
    "about": "about",
    "version": "version",
    "weather": "s",
    "forecast": "se",
    "electricity": "sahko",
    "crypto": "crypto",
    "youtube": "youtube",
    "solarwind": "solarwind",
    "trains": "junat",
    "eurojackpot": "eurojackpot",
    "alko": "alko",
    "roll": "noppa",
    "coin": "kolikko",
    "rps": "ksp",
    "feature": "feature",
    "features": "feature",
    "metrics": "metrics",
    "history": "history",
    "subscribe": "tilaa",
}

_NATIVE_DISCORD_COMMANDS = {"ask", "poll", "seen", "status"}
_DISCORD_COMMAND_NAME = re.compile(r"^[a-z0-9_-]{1,32}$")


def get_discord_command_map() -> dict[str, str]:
    """Return every registry command that may be safely exposed on Discord."""
    ensure_commands_loaded()
    registry = get_command_registry()
    commands = {
        name: name
        for name, handler in registry._commands.items()
        if handler.info.supports_discord
        and name not in _NATIVE_DISCORD_COMMANDS
        and _DISCORD_COMMAND_NAME.fullmatch(name)
    }
    for slash_name, registry_name in CORE_COMMANDS.items():
        handler = registry.get_handler(registry_name)
        if (
            handler
            and handler.info.supports_discord
            and slash_name not in _NATIVE_DISCORD_COMMANDS
            and _DISCORD_COMMAND_NAME.fullmatch(slash_name)
        ):
            commands[slash_name] = registry_name
    return dict(sorted(commands.items()))


class DiscordChannelTransport:
    """Per-event facade that satisfies the small IRC server API the handler uses."""

    def __init__(self, bot: "DiscordBot", server_name: str):
        self._bot = bot
        self.platform = "discord"
        self.config = SimpleNamespace(name=server_name, use_notices=False)
        self.bot_name = bot.bot_name

    @property
    def connected(self) -> bool:
        return self._bot.connected

    def send_message(self, target: str, message: str) -> None:
        self._bot.send_message(target, message)

    def send_embed(self, target: str, title: str, description: str) -> None:
        self._bot.send_embed(target, title, description)

    send_notice = send_message


class DiscordBot:
    """Run Discord alongside IRC and adapt Discord events to shared services."""

    def __init__(self, bot_manager, settings: dict[str, Any]):
        self.bot_manager = bot_manager
        self.settings = settings
        self.token = os.getenv("DISCORD_TOKEN", "")
        self.logger = logger.get_logger("Discord")
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.client = None
        self.tree = None
        self._discord = None
        self._notification_times: dict[str, list[datetime]] = {}
        self.config = SimpleNamespace(name="discord", use_notices=False)
        self.bot_name = "DiscordBot"

    def _community(self):
        handler = getattr(self.bot_manager, "message_handler", None)
        getter = getattr(handler, "_get_community_state", None)
        return getter() if callable(getter) else None

    def _record_event(self, event: str, detail: str, level: str = "INFO") -> None:
        community = self._community()
        if community and hasattr(community, "add_discord_event"):
            community.add_discord_event(event, detail, level)

    def get_diagnostics(self) -> dict[str, Any]:
        """Return secret-free startup diagnostics for TUI and /health."""
        allowed = sorted(self._configured_ids("allowed_channels"))
        return {
            "enabled": bool(self.settings.get("enabled", False)),
            "token_configured": bool(self.token),
            "connected": self.connected,
            "message_content_intent": True,
            "allowed_channels": allowed,
            "command_sync": self.settings.get("command_sync", "global"),
        }

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", False) and self.token)

    @property
    def connected(self) -> bool:
        return bool(
            self.client
            and self.loop
            and self.loop.is_running()
            and not self.client.is_closed()
        )

    def start(self) -> bool:
        """Start Discord's asyncio gateway in a dedicated daemon thread."""
        if not self.enabled:
            if self.settings.get("enabled", False):
                self.logger.warning("Discord is enabled but DISCORD_TOKEN is not set")
            return False
        if self.thread and self.thread.is_alive():
            return True
        self.thread = threading.Thread(
            target=self._thread_main, name="discord-gateway", daemon=True
        )
        self.thread.start()
        self._record_event("gateway", "Discord gateway thread started")
        return True

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run())
        except Exception as exc:
            self.logger.error(f"Discord gateway failed during startup: {exc}")
            self._record_event("gateway", str(exc), "ERROR")

    async def _run(self) -> None:
        try:
            import discord
            from discord import app_commands
        except ImportError:
            self.logger.error("discord.py is not installed; run uv sync --dev")
            return

        self.loop = asyncio.get_running_loop()
        self._discord = discord
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self._register_commands(discord, app_commands)

        @self.client.event
        async def on_ready():
            self.bot_name = self.client.user.name if self.client.user else self.bot_name
            if self.settings.get("command_sync", "global") != "disabled":
                try:
                    await self.tree.sync()
                    self.logger.info("Discord slash commands synchronized")
                except Exception as exc:
                    self.logger.error(f"Discord command synchronization failed: {exc}")
                    self._record_event("command_sync", str(exc), "ERROR")
            self.logger.info(f"Discord connected as {self.bot_name}")
            await self._capture_channel_diagnostics()

        @self.client.event
        async def on_message(message):
            await self._on_message(message)

        try:
            await self.client.start(self.token)
        except Exception as exc:
            self.logger.error(f"Discord gateway stopped: {exc}")

    def _register_commands(self, discord, app_commands) -> None:
        registry = get_command_registry()
        for slash_name, registry_name in get_discord_command_map().items():
            handler = registry.get_handler(registry_name)
            description = (
                handler.info.description
                if handler and handler.info.description
                else f"Run LeetIRCBot {registry_name}"
            )
            self.tree.add_command(
                app_commands.Command(
                    name=slash_name,
                    description=description[:100],
                    callback=self._make_command_callback(registry_name),
                )
            )

        @self.tree.command(
            name="poll", description="Create, inspect, or close a Discord poll"
        )
        async def poll(interaction, action: str, data: str = ""):
            await self._poll_command(interaction, action, data, discord)

        async def seen(interaction, member):
            await self._run_command(interaction, "seen", str(member.id))

        # ``discord`` is loaded lazily, so assign the runtime type before
        # discord.py inspects this callback for its slash-command schema.
        seen.__annotations__["member"] = discord.Member
        self.tree.add_command(
            app_commands.Command(
                name="seen",
                description="Show a member's latest activity",
                callback=seen,
            )
        )

        @self.tree.command(name="ask", description="Ask the configured GPT service")
        async def ask(interaction, prompt: str):
            await self._ask_command(interaction, prompt)

        @self.tree.command(name="status", description="Show Discord bot status")
        async def status(interaction):
            if not self._allowed_interaction(interaction):
                await self._respond(
                    interaction, "This bot is not enabled in this channel.", True
                )
                return
            await self._respond(interaction, self._status_message(interaction), True)

        @self.tree.command(name="health", description="Show bot and service health")
        async def health(interaction):
            if not self._allowed_interaction(interaction):
                await self._respond(
                    interaction, "This bot is not enabled in this channel.", True
                )
                return
            await self._respond(interaction, self._health_message(), True)

        @self.tree.command(
            name="settings",
            description="View or update this Discord channel's settings",
        )
        async def settings(interaction, action: str = "show", value: str = ""):
            await self._settings_command(interaction, action, value)

    def _make_command_callback(self, command: str) -> Callable[..., Any]:
        """Create a slash callback without exposing closure state as an option."""

        async def callback(interaction, arguments: str = ""):
            await self._run_command(interaction, command, arguments)

        callback.__name__ = f"discord_{command}"
        return callback

    def _allowed_channel(self, channel_id: int | str | None) -> bool:
        allowed = self._configured_ids("allowed_channels")
        return bool(channel_id is not None and str(channel_id) in allowed)

    def _configured_ids(self, setting: str) -> set[str]:
        """Read IDs defensively while state migrations repair legacy entries."""
        values = self.settings.get(setting, [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return set()
        return {
            item.strip()
            for value in values
            for item in str(value).split(",")
            if item.strip()
        }

    def _scope(self, interaction_or_message) -> tuple[str, str, bool]:
        guild = getattr(interaction_or_message, "guild", None)
        channel = getattr(interaction_or_message, "channel", None)
        channel_id = str(getattr(channel, "id", ""))
        return (
            f"discord:{getattr(guild, 'id', 'dm')}",
            f"#{channel_id}",
            guild is None,
        )

    def _allowed_interaction(self, interaction) -> bool:
        if interaction.guild is None:
            return True
        return self._allowed_channel(getattr(interaction.channel, "id", None))

    def _status_message(self, interaction) -> str:
        """Return Discord-specific status without exposing any configuration secrets."""
        if interaction.guild is None:
            return "Discord status: online. DMs support slash commands only."
        return (
            "Discord status: online. "
            f"Guild {interaction.guild.id}, channel {interaction.channel.id} is enabled."
        )

    def _health_message(self) -> str:
        diagnostics = self.get_diagnostics()
        manager_health = getattr(self.bot_manager, "get_health_status", lambda: {})()
        services = (
            manager_health.get("services", {})
            if isinstance(manager_health, dict)
            else {}
        )
        healthy = sum(bool(value) for value in services.values())
        jobs = (
            manager_health.get("background_jobs", {})
            if isinstance(manager_health, dict)
            else {}
        )
        return (
            f"Discord: {'online' if diagnostics['connected'] else 'offline'} | "
            f"Token: {'configured' if diagnostics['token_configured'] else 'missing'} | "
            f"Services: {healthy}/{len(services)} available | "
            f"Background jobs: {len(jobs)} tracked"
        )

    async def _respond(
        self, interaction, message: str, ephemeral: bool = False
    ) -> None:
        message = message or "Done."
        chunks = [
            message[index : index + 1900] for index in range(0, len(message), 1900)
        ]
        if not interaction.response.is_done():
            await interaction.response.send_message(chunks.pop(0), ephemeral=ephemeral)
        for chunk in chunks:
            await interaction.followup.send(chunk, ephemeral=ephemeral)

    def _context(self, interaction, command: str, arguments: str) -> CommandContext:
        server_name, target, is_private = self._scope(interaction)
        user = interaction.user
        return CommandContext(
            command="",
            args=[],
            raw_message=f"!{command} {arguments}".strip(),
            sender=getattr(user, "display_name", user.name),
            target=target,
            is_private=is_private,
            server_name=server_name,
            server=self,
            platform="discord",
            actor_id=str(user.id),
            channel_id=target.lstrip("#"),
        )

    async def _run_command(self, interaction, command: str, arguments: str) -> None:
        if not self._allowed_interaction(interaction):
            await self._respond(
                interaction, "This bot is not enabled in this channel.", True
            )
            return
        ensure_commands_loaded()
        context = self._context(interaction, command, arguments)
        handler = self.bot_manager.message_handler
        transport = DiscordChannelTransport(self, context.server_name)
        context.server = transport
        bot_functions = handler._create_bot_functions(
            transport,
            {
                "server_name": context.server_name,
                "target": context.target,
                "sender": context.sender,
            },
        )
        bot_functions["discord_admin"] = self.is_admin(interaction)
        response = await process_command_message(
            context.raw_message, context, bot_functions
        )
        community = self._community()
        if community:
            community.record_command("discord", command)
        message = response.message if response and response.should_respond else "Done."
        if (
            command in {"weather", "forecast", "electricity"}
            and response
            and response.should_respond
        ):
            await self._respond_embed(interaction, command.title(), message)
        else:
            await self._respond(interaction, message)

    def is_admin(self, interaction) -> bool:
        user_ids = self._configured_ids("admin_user_ids")
        if str(interaction.user.id) in user_ids:
            return True
        member = getattr(interaction, "user", None)
        role_ids = self._configured_ids("admin_role_ids")
        roles = getattr(member, "roles", [])
        if any(str(getattr(role, "id", "")) in role_ids for role in roles):
            return True
        permissions = getattr(member, "guild_permissions", None)
        return bool(getattr(permissions, "manage_guild", False))

    def _channel_settings(self, channel_id: str) -> dict[str, Any]:
        settings = self.settings.get("channel_settings", {})
        return settings.get(str(channel_id), {}) if isinstance(settings, dict) else {}

    def can_deliver_notification(self, target: str) -> bool:
        """Apply Discord-only quiet hours and hourly notification limits."""
        settings = self._channel_settings(str(target).lstrip("#"))
        quiet_hours = str(settings.get("quiet_hours", ""))
        if quiet_hours:
            try:
                start, end = (
                    datetime.strptime(part, "%H:%M").time()
                    for part in quiet_hours.split("-", 1)
                )
                now = datetime.now().time()
                if (start <= end and start <= now < end) or (
                    start > end and (now >= start or now < end)
                ):
                    return False
            except ValueError:
                self.logger.warning(
                    f"Ignoring invalid Discord quiet hours for {target}: {quiet_hours}"
                )
        try:
            limit = int(settings.get("rate_limit", 0))
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            return True
        now = datetime.now()
        timestamps = [
            stamp
            for stamp in self._notification_times.get(target, [])
            if (now - stamp).total_seconds() < 3600
        ]
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        self._notification_times[target] = timestamps
        return True

    def _save_channel_settings(self, channel_id: str, values: dict[str, Any]) -> bool:
        config = getattr(self.bot_manager, "config", None)
        state_file = getattr(config, "state_file", "data/state.json")

        def updater(data):
            config_data = data.setdefault("config", {})
            discord = config_data.setdefault("discord", {})
            channels = discord.setdefault("channel_settings", {})
            existing = channels.setdefault(str(channel_id), {})
            existing.update(values)
            return data

        saved = update_json_file(state_file, updater, default=dict, strict=True)
        if saved:
            channels = self.settings.setdefault("channel_settings", {})
            channels.setdefault(str(channel_id), {}).update(values)
        return saved

    async def _settings_command(self, interaction, action: str, value: str) -> None:
        if interaction.guild is None or not self._allowed_interaction(interaction):
            await self._respond(
                interaction,
                "Settings are available in enabled Discord channels only.",
                True,
            )
            return
        if not self.is_admin(interaction):
            await self._respond(
                interaction, "Discord administrator permission is required.", True
            )
            return
        channel_id = str(interaction.channel.id)
        action = action.lower().strip()
        community = self._community()
        if action == "show":
            features = (
                community.get_channel_features(*self._scope(interaction)[:2])
                if community
                else {}
            )
            settings = self._channel_settings(channel_id)
            enabled = ", ".join(name for name, active in features.items() if active)
            await self._respond(
                interaction,
                f"Enabled features: {enabled or 'none'} | Quiet hours: {settings.get('quiet_hours', 'off')} | Notification rate: {settings.get('rate_limit', 0)}/hour",
                True,
            )
            return
        if action == "feature":
            parts = value.lower().split()
            server_name, target, _ = self._scope(interaction)
            available_features = (
                community.get_channel_features(server_name, target) if community else {}
            )
            if len(parts) != 2 or parts[0] not in available_features:
                await self._respond(
                    interaction, "Use: /settings feature value:<feature> <on|off>", True
                )
                return
            if parts[1] not in {"on", "off"}:
                await self._respond(interaction, "Use on or off.", True)
                return
            community.set_feature(server_name, target, parts[0], parts[1] == "on")
            await self._respond(interaction, f"{parts[0]} is now {parts[1]}.", True)
            return
        if action == "quiet":
            if value and not re.fullmatch(r"\d{2}:\d{2}-\d{2}:\d{2}", value):
                await self._respond(
                    interaction,
                    "Use HH:MM-HH:MM, or leave value empty to disable.",
                    True,
                )
                return
            self._save_channel_settings(channel_id, {"quiet_hours": value})
            await self._respond(interaction, f"Quiet hours: {value or 'off'}.", True)
            return
        if action == "rate":
            if not value.isdigit():
                await self._respond(
                    interaction, "Use a whole number of notifications per hour.", True
                )
                return
            self._save_channel_settings(channel_id, {"rate_limit": int(value)})
            await self._respond(
                interaction, f"Notification rate limit: {value}/hour.", True
            )
            return
        await self._respond(interaction, "Actions: show, feature, quiet, rate.", True)

    async def _on_message(self, message) -> None:
        if getattr(message.author, "bot", False) or message.guild is None:
            return
        if not self._allowed_channel(getattr(message.channel, "id", None)):
            return
        server_name, target, _ = self._scope(message)
        transport = DiscordChannelTransport(self, server_name)
        await self.bot_manager.message_handler.handle_message(
            transport,
            getattr(message.author, "display_name", message.author.name),
            "",
            target,
            message.content,
            platform="discord",
            actor_id=str(message.author.id),
            channel_id=str(message.channel.id),
        )

    async def _capture_channel_diagnostics(self) -> None:
        """Persist channel names and report missing send/read permissions."""
        community = self._community()
        if not community:
            return
        for channel_id in self._configured_ids("allowed_channels"):
            channel = self.client.get_channel(int(channel_id)) if self.client else None
            if channel is None:
                self._record_event(
                    "diagnostic",
                    f"Allowed channel {channel_id} is not visible",
                    "WARNING",
                )
                continue
            permissions = {}
            guild = getattr(channel, "guild", None)
            me = getattr(guild, "me", None)
            if me and hasattr(channel, "permissions_for"):
                resolved = channel.permissions_for(me)
                permissions = {
                    name: bool(getattr(resolved, name, False))
                    for name in (
                        "view_channel",
                        "send_messages",
                        "read_message_history",
                        "embed_links",
                    )
                }
                missing = [name for name, allowed in permissions.items() if not allowed]
                if missing:
                    self._record_event(
                        "diagnostic",
                        f"#{getattr(channel, 'name', channel_id)} missing: {', '.join(missing)}",
                        "WARNING",
                    )
            community.save_discord_channel(
                str(getattr(guild, "id", "")),
                channel_id,
                getattr(channel, "name", ""),
                permissions,
            )
        self._record_event(
            "gateway", "Discord connected and channel diagnostics completed"
        )

    async def _respond_embed(self, interaction, title: str, description: str) -> None:
        if not self._discord:
            await self._respond(interaction, description)
            return
        embed = self._discord.Embed(title=title, description=description[:4096])
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)

    async def _poll_command(self, interaction, action: str, data: str, discord) -> None:
        if interaction.guild is None or not self._allowed_interaction(interaction):
            await self._respond(
                interaction,
                "Polls are available in enabled Discord channels only.",
                True,
            )
            return
        server_name, target, _ = self._scope(interaction)
        community = self.bot_manager.message_handler._get_community_state()
        action = action.lower()
        if action == "create":
            parts = [part.strip() for part in data.split("|") if part.strip()]
            if len(parts) < 3 or len(parts) > 11:
                await self._respond(
                    interaction,
                    "Use: question | option | option (up to 10 options).",
                    True,
                )
                return
            poll = discord.Poll(question=parts[0], duration=timedelta(hours=24))
            for option in parts[1:]:
                poll.add_answer(text=option)
            await interaction.response.send_message(poll=poll)
            message = await interaction.original_response()
            community.save_discord_poll(
                server_name,
                target,
                str(message.id),
                parts[0],
                parts[1:],
                str(interaction.user.id),
            )
            return
        if not data.isdigit():
            await self._respond(interaction, "Provide the poll message ID.", True)
            return
        stored = community.get_discord_poll(server_name, target, data)
        if not stored:
            await self._respond(
                interaction, "That poll is not tracked in this channel.", True
            )
            return
        message = await interaction.channel.fetch_message(int(data))
        poll = getattr(message, "poll", None)
        answers = list(getattr(poll, "answers", []) or [])
        results = [
            int(getattr(answer, "votes", getattr(answer, "vote_count", 0)))
            for answer in answers
        ]
        closed = action == "close"
        if closed:
            if str(interaction.user.id) != stored["creator_id"] and not self.is_admin(
                interaction
            ):
                await self._respond(
                    interaction,
                    "Only the creator or an admin can close this poll.",
                    True,
                )
                return
            message = await message.end_poll()
            poll = getattr(message, "poll", poll)
            answers = list(getattr(poll, "answers", []) or [])
            results = [
                int(getattr(answer, "votes", getattr(answer, "vote_count", 0)))
                for answer in answers
            ]
        community.save_discord_poll(
            server_name,
            target,
            data,
            stored["question"],
            stored["options"],
            stored["creator_id"],
            results,
            closed,
        )
        listed = " | ".join(
            f"{index + 1}. {option}: {results[index] if index < len(results) else 0}"
            for index, option in enumerate(stored["options"])
        )
        await self._respond(
            interaction, f"Poll {data}{' closed' if closed else ''}: {listed}"
        )

    async def _ask_command(self, interaction, prompt: str) -> None:
        if not self._allowed_interaction(interaction):
            await self._respond(
                interaction, "This bot is not enabled in this channel.", True
            )
            return
        server_name, target, _ = self._scope(interaction)
        community = self.bot_manager.message_handler._get_community_state()
        if interaction.guild and not community.is_enabled(server_name, target, "ai"):
            await self._respond(interaction, "AI is disabled in this channel.", True)
            return
        gpt = self.bot_manager.service_manager.get_service("gpt")
        if not gpt:
            await self._respond(interaction, "GPT service is not available.", True)
            return
        history_channel = target
        if interaction.guild and not community.is_enabled(
            server_name, target, "gpt_history"
        ):
            history_channel = None
        await interaction.response.defer(thinking=True)
        response = await asyncio.to_thread(
            gpt.chat,
            prompt,
            getattr(interaction.user, "display_name", interaction.user.name),
            server_name,
            history_channel,
        )
        if interaction.guild:
            community.record_metric(server_name, target, "commands")
        await self._respond(interaction, response)

    def send_message(self, target: str, message: str) -> None:
        """Synchronous transport adapter used by existing notification code."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._send(target, message), self.loop)

    send_notice = send_message

    async def _send(self, target: str, message: str) -> None:
        if not self.client:
            return
        channel_id = int(str(target).lstrip("#"))
        channel = self.client.get_channel(
            channel_id
        ) or await self.client.fetch_channel(channel_id)
        await channel.send(message[:2000], allowed_mentions=None)

    def send_embed(self, target: str, title: str, description: str) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_embed(target, title, description), self.loop
            )

    async def _send_embed(self, target: str, title: str, description: str) -> None:
        if not self.client:
            return
        channel_id = int(str(target).lstrip("#"))
        channel = self.client.get_channel(
            channel_id
        ) or await self.client.fetch_channel(channel_id)
        if self._discord:
            await channel.send(
                embed=self._discord.Embed(title=title, description=description[:4096]),
                allowed_mentions=None,
            )
        else:
            await channel.send(f"{title}: {description}"[:2000], allowed_mentions=None)

    def stop(self) -> None:
        loop = self.loop
        client = self.client
        close_complete = threading.Event()

        if loop and client and not loop.is_closed() and not client.is_closed():

            def request_close() -> None:
                async def close_client() -> None:
                    try:
                        if not client.is_closed():
                            await client.close()
                    finally:
                        close_complete.set()

                asyncio.create_task(close_client())

            try:
                # Create the coroutine on Discord's loop. Constructing it before
                # scheduling risks an unawaited-coroutine warning during shutdown.
                loop.call_soon_threadsafe(request_close)
                if not close_complete.wait(timeout=10):
                    self.logger.warning("Discord shutdown timed out")
            except RuntimeError:
                # The gateway can finish and close its loop between the checks.
                pass
        if (
            self.thread
            and self.thread.is_alive()
            and threading.current_thread() != self.thread
        ):
            self.thread.join(timeout=10)
