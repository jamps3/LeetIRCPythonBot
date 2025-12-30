"""
External Service Commands Module

Contains commands for external services like weather, electricity, crypto,
YouTube, trains, and other APIs extracted from commands.py.
"""

import json
import os
import re
from datetime import datetime

from command_registry import (
    CommandContext,
    CommandResponse,
    CommandScope,
    CommandType,
    command,
)


@command(
    "s",
    aliases=["sää", "weather"],
    description="Get weather information",
    usage="!s [location]",
    examples=["!s", "!s Helsinki", "!s Joensuu"],
)
def weather_command(context: CommandContext, bot_functions):
    """Get weather information for a location."""
    location = context.args_text.strip() if context.args_text else "Joensuu"

    # Call the weather function from bot_functions
    send_weather = bot_functions.get("send_weather")
    if send_weather:
        # For console, we need to handle the response differently
        if context.is_console:
            # Import logging to track console calls
            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Getting weather for {location} from console")

        # Determine IRC/server context if available (for IRC responses)
        irc_ctx = bot_functions.get("irc") if not context.is_console else None
        # Call the weather service - pass the location as the third parameter
        send_weather(irc_ctx, context.target, location)
        return CommandResponse.no_response()  # Weather service handles the output
    else:
        return "Weather service not available"


@command(
    "se",
    aliases=["sääennuste"],
    description="Short forecast (single line)",
    usage="!se [city] [hours]",
    examples=["!se", "!se Joensuu", "!se Joensuu 12"],
)
def short_forecast_command(context: CommandContext, bot_functions):
    """Return a single-line forecast using Meteosource free API."""
    try:
        from services.weather_forecast_service import format_single_line
    except Exception as e:
        return f"Forecast service not available: {e}"

    # Parse args: allow city with spaces and optional trailing integer hours
    text = context.args_text.strip() if context.args_text else ""
    city = None
    hours = None
    if text:
        parts = text.split()
        # If last token is an int, treat as hours
        try:
            cand = int(parts[-1])
            hours = cand if cand > 0 else None
            parts = parts[:-1]
        except Exception:
            pass
        city = " ".join(parts).strip() if parts else None

    try:
        line = format_single_line(city, hours)
    except Exception as e:
        return f"❌ Ennustevirhe: {e}"
    return line


@command(
    "sel",
    aliases=["sääennustelista"],
    description="Short forecast (multiple lines)",
    usage="!sel [city] [hours]",
    examples=["!sel", "!sel Joensuu 12"],
)
def short_forecast_list_command(context: CommandContext, bot_functions):
    """Return a multi-line forecast using Meteosource free API."""
    try:
        from services.weather_forecast_service import format_multi_line
    except Exception as e:
        return f"Forecast service not available: {e}"

    text = context.args_text.strip() if context.args_text else ""
    city = None
    hours = None
    if text:
        parts = text.split()
        try:
            cand = int(parts[-1])
            hours = cand if cand > 0 else None
            parts = parts[:-1]
        except Exception:
            pass
        city = " ".join(parts).strip() if parts else None

    try:
        lines = format_multi_line(city, hours)
    except Exception as e:
        return f"❌ Ennustevirhe: {e}"

    if context.is_console:
        return "\n".join(lines)
    # On IRC, send each line as separate notice if available
    notice = bot_functions.get("notice_message")
    irc = bot_functions.get("irc")
    target = context.target or context.sender
    if notice and irc:
        for ln in lines:
            notice(ln, irc, target)
        return CommandResponse.no_response()
    return "\n".join(lines)


@command(
    "solarwind",
    description="Get solar wind information from NOAA SWPC",
    usage="!solarwind",
    examples=["!solarwind"],
)
def solarwind_command(context: CommandContext, bot_functions):
    """Get current solar wind information."""
    try:
        from services.solarwind_service import get_solar_wind_info

        return get_solar_wind_info()
    except Exception as e:
        return f"❌ Solar wind error: {str(e)}"


@command(
    "otiedote",
    description="Get accident reports (Onnettomuustiedotteet) from local JSON",
    usage="!otiedote [N | #N | seuraava | set <number> | filter #channel <organization> <field> | filter list]",
    examples=[
        "!otiedote",
        "!otiedote 2",
        "!otiedote #2610",
        "!otiedote seuraava",
        "!otiedote filter #joensuu Pohjois-Karjalan pelastuslaitos organization",
        "!otiedote filter list",
        "Fields: id, title, date, location, organization, content, units, url or * for all",
    ],
)
def otiedote_command(context: CommandContext, bot_functions):
    """Handle otiedote commands from local JSON."""
    try:
        from config import get_config
        from services.otiedote_json_service import create_otiedote_service
    except ImportError:
        return "❌ Otiedote service not available"

    config = get_config()
    otiedote_service = create_otiedote_service(
        callback=lambda title, url, description: None,
        state_file=config.state_file,
    )

    # Load otiedote data
    try:
        otiedote_list = otiedote_service.load_otiedote_data()
        if not otiedote_list:
            return "❌ No otiedote data available."
    except Exception as e:
        return f"❌ Error loading otiedote data: {e}"

    # Latest release number (highest ID)
    latest_id = max(item["id"] for item in otiedote_list) if otiedote_list else 0

    # Handle "seuraava" subcommand - manually fetch next release
    if context.args and context.args[0].lower() == "seuraava":
        try:
            # Fetch the next release manually
            release = otiedote_service.fetch_next_release()
            if release:
                # Apply filtering for the current channel
                target = context.target or ""

                # Load state for filters
                state = otiedote_service._load_state()
                filters = state.get("otiedote", {}).get("filters", {})

                # Check if this channel has filters
                channel_filters = filters.get(target, [])
                should_show = True

                if channel_filters:
                    # Check if any filter matches
                    should_show = False
                    for filter_entry in channel_filters:
                        if ":" in filter_entry:
                            organization, field = filter_entry.split(":", 1)
                        else:
                            organization = filter_entry
                            field = "organization"

                        # Check if the field matches the filter
                        if field == "organization":
                            release_org = release.get("organization", "")
                            if organization.lower() in release_org.lower():
                                should_show = True
                                break
                        elif field == "*":
                            release_text = json.dumps(
                                release, ensure_ascii=False
                            ).lower()
                            if organization.lower() in release_text:
                                should_show = True
                                break
                        else:
                            field_value = release.get(field, "")
                            if isinstance(field_value, list):
                                field_value = " ".join(field_value)
                            if organization.lower() in str(field_value).lower():
                                should_show = True
                                break

                if should_show:
                    # Show the release in the current channel
                    header_message = f"📢 {release['title']} | {release['url']}"
                    server = context.server if hasattr(context, "server") else None
                    if server:
                        bot_functions.get(
                            "notice_message", lambda msg, irc, target: None
                        )(header_message, server, target)
                    return f"✅ Manually fetched and showed Otiedote #{release['id']}: {release['title']} (current was #{otiedote_service.latest_release})"
                else:
                    return f"❌ Next release #{release['id']} is filtered out for this channel (organization: {release.get('organization', 'unknown')})"
            else:
                return f"❌ No new releases found after #{otiedote_service.latest_release} (next release may not be published yet)"
        except Exception as e:
            return f"❌ Error fetching next release after #{otiedote_service.latest_release}: {e}"

    # Handle "set" subcommand - manually set current release number
    if context.args and context.args[0].lower() == "set":
        if len(context.args) < 2:
            return "❌ Usage: !otiedote set <number>"

        try:
            new_number = int(context.args[1])
            if new_number < 0:
                return "❌ Release number must be positive"

            # Set the latest release number
            old_number = otiedote_service.latest_release
            otiedote_service.latest_release = new_number
            otiedote_service._save_latest_release(new_number)

            return (
                f"✅ Otiedote latest release set to #{new_number} (was #{old_number})"
            )

        except ValueError:
            return "❌ Invalid number format"
        except Exception as e:
            return f"❌ Error setting release number: {e}"

    # Handle filter subcommand
    if context.args and context.args[0].lower() == "filter":
        # Check for list subcommand
        if len(context.args) >= 2 and context.args[1].lower() == "list":
            # List all filters
            state = otiedote_service._load_state()
            filters = state.get("otiedote", {}).get("filters", {})

            if not filters:
                return "📋 No otiedote filters configured."

            lines = ["📋 Current otiedote filters:"]
            for channel, channel_filters in filters.items():
                lines.append(f"  {channel}:")
                if channel_filters:
                    for filter_entry in channel_filters:
                        if ":" in filter_entry:
                            org, field = filter_entry.split(":", 1)
                            lines.append(f"    - {org} (field: {field})")
                        else:
                            lines.append(f"    - {filter_entry}")
                else:
                    lines.append("    (no filters)")

            return "\n".join(lines)

        # Add filter
        if len(context.args) < 4:
            return "❌ Usage: !otiedote filter #channel <organization> <field>\n   Or: !otiedote filter list"

        channel = context.args[1]
        if not channel.startswith("#"):
            return "❌ Channel must start with #"

        # Parse organization name (everything between channel and last word)
        field = context.args[-1]  # Last argument is the field
        organization_parts = context.args[2:-1]  # Everything between channel and field
        organization = " ".join(organization_parts)

        if not organization.strip():
            return "❌ Organization name cannot be empty"

        # Load state
        state = otiedote_service._load_state()
        if "otiedote" not in state:
            state["otiedote"] = {"latest_release": 0}

        if "filters" not in state["otiedote"]:
            state["otiedote"]["filters"] = {}

        # Add filter for channel
        if channel not in state["otiedote"]["filters"]:
            state["otiedote"]["filters"][channel] = []

        filter_entry = f"{organization}:{field}"
        if filter_entry not in state["otiedote"]["filters"][channel]:
            state["otiedote"]["filters"][channel].append(filter_entry)

        # Save state
        try:
            otiedote_service._save_state(state)
            return f"✅ Added filter for {channel}: {organization} (field: {field})"
        except Exception as e:
            return f"❌ Failed to save filter: {e}"

    # Current number (#) simply returns latest ID
    if context.args_text and context.args_text.strip() == "#":
        return f"Current otiedote release number: #{latest_id}"

    args_text = context.args_text.strip() if context.args_text else ""

    # !otiedote → show latest full description
    if not args_text:
        try:
            latest = max(otiedote_list, key=lambda x: x["id"])
            if latest["content"]:
                return (
                    f"📄 {latest['title']} | {latest['content']} URL: {latest['url']}"
                )
            else:
                return f"📄 {latest['title']} URL: {latest['url']}"
        except (ValueError, KeyError):
            return "❌ No valid otiedote data available"

    # !otiedote #<number> → show short description for specific release number
    if args_text.startswith("#"):
        try:
            number = int(args_text[1:])
            item = next((x for x in otiedote_list if x["id"] == number), None)
            if not item:
                return f"❌ Otiedote #{number} not found in local JSON."
            trimmed_content = bot_functions.get(
                "trim_with_dots",
                lambda text, limit=400: text[:400] + "..." if len(text) > 400 else text,
            )(item["content"])
            return f"📄 {item['title']} {trimmed_content} {item.get('location', '')} {item.get('date', '')} URL: {item['url']}"
        except ValueError:
            return "❌ Invalid number format. Usage: !otiedote #<number>"

    # !otiedote <N> → show Nth latest (1=latest)
    try:
        offset = int(args_text)
        if offset < 1 or offset > len(otiedote_list):
            return f"❌ Invalid number. Must be between 1 and {len(otiedote_list)}."
        sorted_list = sorted(otiedote_list, key=lambda x: x["id"], reverse=True)
        item = sorted_list[offset - 1]
        trimmed_content = bot_functions.get(
            "trim_with_dots",
            lambda text, limit=400: text[:400] + "..." if len(text) > 400 else text,
        )(item["content"])
        return f"📄 {item['title']} {trimmed_content} {item.get('location', '')} {item.get('date', '')} URL: {item['url']}"
    except ValueError:
        return "❌ Invalid argument. Usage: !otiedote [N | # | #N | filter #channel *filter* organization]"


@command(
    "sahko",
    aliases=["sähkö"],
    description="Get electricity price information",
    usage="!sahko [tänään|huomenna|longbar|tilastot|stats] [tunti]",
    examples=[
        "!sahko",
        "!sahko huomenna",
        "!sahko tänään 15",
        "!sahko longbar",
        "!sahko tilastot",
        "!sahko stats",
    ],
)
def electricity_command(context: CommandContext, bot_functions):
    """Get electricity price information."""
    # Get electricity service directly for better control in TUI mode
    send_electricity_price = bot_functions.get("send_electricity_price")
    if not send_electricity_price:
        return "Electricity price service not available. Please configure ELECTRICITY_API_KEY."

    try:
        # Parse arguments using the service
        # For now, pass the raw args and let the handler deal with it
        send_electricity_price(None, context.target, context.args)
        return CommandResponse.no_response()  # Service handles the output

    except Exception as e:
        return f"⚡ Error getting electricity price: {str(e)}"


@command(
    "euribor",
    description="Get current 12-month Euribor rate",
    usage="!euribor",
    examples=["!euribor"],
)
def euribor_command(context: CommandContext, bot_functions):
    """Get current 12-month Euribor rate from Suomen Pankki."""
    import platform
    import xml.etree.ElementTree as ElementTree
    from datetime import datetime as _dt

    import requests

    try:
        # XML data URL from Suomen Pankki
        url = (
            "https://reports.suomenpankki.fi/WebForms/ReportViewerPage.aspx?report="
            "/tilastot/markkina-_ja_hallinnolliset_korot/euribor_korot_today_xml_en&output=xml"
        )
        response = requests.get(url)
        if response.status_code == 200:
            root = ElementTree.fromstring(response.content)
            ns = {"ns": "euribor_korot_today_xml_en"}
            period = root.find(".//ns:period", namespaces=ns)
            if period is not None:
                date_str = period.attrib.get("value")
                date_obj = _dt.strptime(date_str, "%Y-%m-%d")
                if platform.system() == "Windows":
                    formatted_date = date_obj.strftime("%#d.%#m.%y")
                else:
                    formatted_date = date_obj.strftime("%-d.%-m.%y")
                rates = period.findall(".//ns:rate", namespaces=ns)
                for rate in rates:
                    if rate.attrib.get("name") == "12 month (act/360)":
                        euribor_12m = rate.find("./ns:intr", namespaces=ns)
                        if euribor_12m is not None:
                            return f"{formatted_date} 12kk Euribor: {euribor_12m.attrib['value']}%"
                        else:
                            return "Interest rate value not found."
                else:
                    return "12-month Euribor rate not found."
            else:
                return "No period data found in XML."
        else:
            return (
                f"Failed to retrieve XML data. HTTP Status Code: {response.status_code}"
            )
    except Exception as e:
        return f"Error fetching Euribor rate: {str(e)}"


@command(
    "junat",
    description="Näytä seuraavat junat asemalta (Digitraffic)",
    usage="!junat [asema] | !junat saapuvat [asema]",
    examples=[
        "!junat",
        "!junat Joensuu",
        "!junat JNS",
        "!junat saapuvat",
        "!junat saapuvat HKI",
    ],
)
def trains_command(context: CommandContext, bot_functions):
    """Show upcoming trains for a station using Digitraffic API.

    Defaults to Joensuu (JNS) when no station is given.
    """
    try:
        from services.digitraffic_service import (
            get_arrivals_for_station,
            get_trains_for_station,
        )

        # Parse subcommand 'saapuvat'
        if context.args and context.args[0].lower() == "saapuvat":
            station = (
                " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
            )
            result = get_arrivals_for_station(station)
        else:
            station = context.args_text.strip() if context.args_text else None
            result = get_trains_for_station(station)
        # Let the command framework split by newlines for IRC notices
        return CommandResponse.success_msg(result)
    except Exception as e:
        return f"❌ Digitraffic virhe: {str(e)}"


@command(
    "youtube",
    description="Search YouTube videos or get video info",
    usage="!youtube <search query>",
    examples=["!youtube python tutorial", "!youtube cat videos"],
    requires_args=True,
)
def youtube_command(context: CommandContext, bot_functions):
    """Search YouTube for videos."""
    send_youtube_info = bot_functions.get("send_youtube_info")
    if not send_youtube_info:
        return "YouTube service not available. Please configure YOUTUBE_API_KEY."

    query = context.args_text.strip()
    if not query:
        return "Usage: !youtube <search query>"

    try:
        send_youtube_info(None, context.target, query)
        return CommandResponse.no_response()  # Service handles the output
    except Exception as e:
        return f"❌ YouTube search error: {str(e)}"


@command(
    "crypto",
    description="Get cryptocurrency prices",
    usage="!crypto [coin] [currency]",
    examples=["!crypto", "!crypto btc", "!crypto eth eur"],
)
def crypto_command(context: CommandContext, bot_functions):
    """Get cryptocurrency price information."""
    send_crypto_price = bot_functions.get("send_crypto_price")
    if not send_crypto_price:
        return "Crypto price service not available"

    if len(context.args) >= 1:
        args = [context.args[0]]
        if len(context.args) > 1:
            args.append(context.args[1])
        send_crypto_price(None, context.target, args)
        return CommandResponse.no_response()  # Service handles the output
    else:
        # Show top 3 coins by default
        top_coins = ["bitcoin", "ethereum", "tether"]
        response_parts = []
        for coin in top_coins:
            send_crypto_price(None, context.target, [coin, "eur"])
        return CommandResponse.no_response()  # Service handles the output


@command(
    "url",
    description="Fetch and display title from URL",
    usage="!url <url>",
    examples=["!url https://example.com"],
    requires_args=True,
)
def url_command(context: CommandContext, bot_functions):
    """Fetch title from a URL."""
    fetch_title = bot_functions.get("fetch_title")
    if fetch_title:
        # Extract URL from arguments
        url = context.args_text.strip()
        fetch_title(None, context.target, url)
        return CommandResponse.no_response()  # Service handles the output
    else:
        return "URL title fetching service not available"


@command(
    "leetwinners",
    description="Show top leet winners by category",
    usage="!leetwinners [last]",
    examples=["!leetwinners", "!leetwinners last"],
)
def leetwinners_command(context: CommandContext, bot_functions):
    """Show top-3 leet winners by category (first, last, multileet)."""
    load_leet_winners = bot_functions.get("load_leet_winners")
    if not load_leet_winners:
        return "Leet winners service not available"

    # Check for "last" parameter
    show_today = "last" in (context.args or [])

    # Expected structure: { winner: {category: count, ...}, ... }
    data = load_leet_winners() or {}

    # Extract metadata if present
    metadata = data.get("_metadata", {})
    start_date = metadata.get("statistics_started")

    # Aggregate counts per category -> list of (winner, count)
    per_category = {}
    for winner, categories in data.items():
        # Skip metadata entries
        if winner.startswith("_"):
            continue

        for cat, count in categories.items():
            if cat not in per_category:
                per_category[cat] = []
            per_category[cat].append((winner, count))

    # Sort each category desc by count, then by winner name for stability
    lines = []
    for cat, entries in per_category.items():
        top = sorted(entries, key=lambda x: (-x[1], x[0]))[:5]
        if top:
            formatted = ", ".join(f"{w} [{c}]" for w, c in top)
            lines.append(f"{cat}: {formatted}")

    _cat_map = {"first": "𝓮𝓴𝓪", "last": "𝓿𝓲𝓴𝓪", "multileet": "𝓶𝓾𝓵𝓽𝓲𝓵𝓮𝓮𝓽"}
    transformed = []
    for ln in lines:
        if ":" in ln:
            cat, rest = ln.split(":", 1)
            mapped = _cat_map.get(cat.strip().lower(), cat.strip())
            transformed.append(f"{mapped}: {rest.strip()}")
        else:
            transformed.append(ln)
    winners_text = "; ".join(transformed)

    # Build response with optional start date
    if winners_text:
        if show_today:
            response = f"Last 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
        else:
            response = f"𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼: {winners_text}"
        if start_date:
            response += f" (since {start_date})"
        return response
    else:
        if start_date:
            return f"No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet (tracking since {start_date})."
        else:
            return "No 𝓛𝓮𝓮𝓽𝔀𝓲𝓷𝓷𝓮𝓻𝓼 recorded yet."


@command(
    "eurojackpot",
    command_type=CommandType.PUBLIC,
    description="Get Eurojackpot information",
    usage=(
        "!eurojackpot [next|tulokset|last|date <DD.MM.YY|DD.MM.YYYY|YYYY-MM-DD>|"
        "freq [--extended|--ext] [--limit N]|stats|hot|cold|pairs|trends|streaks|help]"
    ),
    admin_only=False,
)
def command_eurojackpot(context, bot_functions):
    """Get Eurojackpot lottery information."""
    try:
        args = [a.lower() for a in (context.args or [])]

        # Backwards-compatible branches
        if not args:
            from services.eurojackpot_service import get_eurojackpot_numbers

            # Default: next draw info (backwards-compatible)
            return get_eurojackpot_numbers()

        if args[0] in ["tulokset", "results", "viimeisin", "last"]:
            from services.eurojackpot_service import get_eurojackpot_results

            return get_eurojackpot_results()

        # Explicit next
        if args[0] in ["next", "seuraava"]:
            from services.eurojackpot_service import get_eurojackpot_numbers

            return get_eurojackpot_numbers()

        # Draw by date
        if args[0] in ["date", "päivä", "pvm"]:
            if len(context.args) < 2:
                return "Usage: !eurojackpot date <DD.MM.YY|DD.MM.YYYY|YYYY-MM-DD>"
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.get_draw_by_date(context.args[1])
            return res.get("message", "Eurojackpot: Virhe haussa")

        # Frequent numbers with flags
        if args[0] in ["freq", "frequency", "yleisimmat", "yleisimmät"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            extended = any(a in ["--extended", "--ext"] for a in args[1:])
            # parse --limit N
            limit = None
            if "--limit" in args:
                try:
                    li = args.index("--limit")
                    limit = (
                        int(context.args[li + 1])
                        if li + 1 < len(context.args)
                        else None
                    )
                except Exception:
                    limit = None
            res = service.get_frequent_numbers(limit=limit or 10, extended=extended)
            return res.get("message", "📊 Virhe yleisimpien numeroiden haussa")

        # Database stats
        if args[0] in ["stats", "tietokanta"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.get_database_stats()
            return res.get("message", "📊 Virhe tietokannan tilastoissa")

        # Analytics: hot/cold/pairs/trends/streaks
        if args[0] in ["hot", "cold", "pairs", "trends", "streaks", "analytics"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            sub = args[0]
            # If 'analytics' used, expect a subtype
            if sub == "analytics":
                if len(args) < 2:
                    return (
                        "Usage: !eurojackpot analytics <hot|cold|pairs|trends|streaks>"
                    )
                sub = args[1]

            if sub == "hot":
                res = service.get_hot_cold_numbers(mode="hot")
                return res.get("message", "📊 Virhe hot-numeroissa")
            if sub == "cold":
                res = service.get_hot_cold_numbers(mode="cold")
                return res.get("message", "📊 Virhe cold-numeroissa")
            if sub == "pairs":
                res = service.get_common_pairs()
                return res.get("message", "📊 Virhe paritilastoissa")
            if sub == "trends":
                res = service.get_trends()
                return res.get("message", "📊 Virhe trendeissä")
            if sub == "streaks":
                res = service.get_streaks()
                return res.get("message", "📊 Virhe putkitilastoissa")

        if args[0] in ["scrape"]:
            from services.eurojackpot_service import get_eurojackpot_service

            service = get_eurojackpot_service()
            res = service.scrape_all_draws()
            return res.get("message", "Eurojackpot: Virhe haussa")

        if args[0] == "help":
            return (
                "Usage: !eurojackpot [next|tulokset|last|date <date>|freq [--extended] [--limit N]|"
                "stats|hot|cold|pairs|trends|streaks|help]"
            )

        # Fallback: treat as date
        from services.eurojackpot_service import get_eurojackpot_service

        service = get_eurojackpot_service()
        res = service.get_draw_by_date(context.args[0])
        return res.get("message", "Eurojackpot: Virhe haussa")

    except Exception as e:
        return f"❌ Eurojackpot error: {str(e)}"


@command(
    "alko",
    description="Search Alko product information",
    usage="!alko <drink name or product number>",
    examples=["!alko karhu", "!alko lapin kulta", "!alko 319027"],
    requires_args=True,
)
def alko_command(context: CommandContext, bot_functions):
    """Search for drink information from Alko product database."""
    if not context.args_text:
        return "Usage: !alko <drink name or product number>"

    query = context.args_text.strip()
    if not query:
        return "Usage: !alko <drink name or product number>"

    # Get the Alko service from bot functions
    get_alko_product = bot_functions.get("get_alko_product")
    if not get_alko_product:
        return "🍺 Alko service not available"

    try:
        # Search for the product
        result = get_alko_product(query)
        return result
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error in alko command: {e}")
        return f"🍺 Error searching for product: {str(e)}"


@command(
    "wrap",
    description="Toggle text wrapping mode in TUI",
    usage="!wrap",
    examples=["!wrap"],
    scope=CommandScope.CONSOLE_ONLY,
)
def wrap_command(context: CommandContext, bot_functions):
    """Toggle text wrapping mode in TUI."""
    # Access the global TUI instance
    from tui import _current_tui

    if _current_tui is None:
        return "TUI not available"

    # Toggle the wrap mode
    _current_tui.toggle_wrap()
    return ""  # Return empty string since toggle_wrap already logs the change
