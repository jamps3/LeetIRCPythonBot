# Implementation Plan: Exactly Timed Messages to IRC Nicks

## Executive Summary

User workflow:

1. Run `!lag <nick>` to measure and store the lag
2. Run `!sexact <nick|#channel> <time> <message>` to schedule a message that arrives at exact time using stored lag

---

## 1. Current State

### 1.1 Lag Measurement

The bot sends `!lag` to the nick. The nick responds with a NOTICE message containing the receive time (e.g., "Kello on 18.48.00,854239979" - Finnish for "The time is"). The bot calculates lag by comparing the send time of the `!lag` command with the receive time reported by the nick.

Lag calculation: `lag = receive_time_from_nick - send_time_of_lag_command`

### 1.2 Scheduled Messages

- `ScheduledMessageService` already has nanosecond precision
- Currently only supports scheduling to channels via admin `!scheduled` command
- Can send to nicks via `PRIVMSG {nick} :{message}` (already works)
- **Issue**: No lag compensation - sends at exact target time

---

## 2. Required Changes

### 2.1 Lag Storage (Phase 1)

**In `src/message_handler.py`:**

- Add `_lag_storage: Dict[(server, nick), lag_ms]` dictionary
- Modify `_check_latency_response()` to store RTT after calculation
- Add methods:
  - `_store_lag(server, nick, rtt_ms)`
  - `_get_lag(server, nick)` → returns stored lag or None
  - `_list_lags()` → returns all stored lags
  - `_clear_lag(server, nick)`

**Persistence:**

- Use existing data_manager pattern to save/load lag storage
- File: `data/lag_storage.json`

### 2.2 !lag Command Enhancement (Phase 2)

**In `src/commands_irc.py`:**

- Keep existing `!lag <nick>` behavior (measure and display)
- Add subcommands:
  - `!lag <nick> show` - show stored lag for that nick
  - `!lag list` - list all stored lag values
  - `!lag clear [nick]` - clear stored lag(s)

### 2.3 !sexact Command (Phase 3)

**New command in `src/commands_irc.py`:**

```
!sexact <nick> <HH:MM:SS> <message>       - Send to nick (uses nick's lag)
!sexact <nick> #channel <HH:MM:SS> <msg>  - Send to channel using nick's lag
```

**Behavior for nick target:**

1. Parse target nick and time
2. Look up stored lag for (server, nick)
3. If no lag stored, return error: "No lag measured for <nick>. Run !lag first."
4. Calculate send time with compensation
5. Send via PRIVMSG to nick

**Behavior for channel target (using nick's lag):**

1. Parse: `!sexact <nick> #channel <HH:MM:SS> <message>`
2. First argument is the nick whose lag to use
3. Second argument is the channel
4. Look up stored lag for (server, nick)
5. If no lag stored, return error
6. Calculate send time with compensation
7. Send via PRIVMSG to channel

**Timing calculation example:**

```
Desired arrival: 12:00:00.000
Measured lag: 100ms
One-way delay: 50ms
Send at: 11:59:59.950
```

### 2.4 ScheduledMessageService Enhancement (Phase 3)

**In `src/services/scheduled_message_service.py`:**

- Add optional `lag_ms` parameter to `schedule_message()`
- If lag provided, compensate:

```python
if lag_ms is not None:
    lag_ns = int(lag_ms * 1_000_000)
    compensated_target_ns = target_epoch_ns - (lag_ns // 2)
```

---

## 3. Files to Modify

| File                                        | Changes                           |
| ------------------------------------------- | --------------------------------- |
| `src/message_handler.py`                    | Add lag storage dict and methods  |
| `src/commands_irc.py`                       | Enhance !lag, add !sexact command |
| `src/services/scheduled_message_service.py` | Add lag compensation parameter    |

---

## 4. Usage Examples

```
# Step 1: Measure lag to a nick
!lag Beiki
# → 📡 Latency to Beiki: 45.23 ms (RTT)

# Step 2a: Send to nick at exact time (uses Beiki's lag)
!sexact Beiki 12:00:00 Hello Beiki!
# → ✅ Message to arrive at 12:00:00.000 (sending at 11:59:59.775, lag: 45ms)

# Step 2b: Send to channel using nick's lag
# Usage: !sexact <nick> #channel <time> <message>
!sexact Beiki #mychannel 14:30:00 Hello everyone!
# → ✅ Message to #mychannel to arrive at 14:30:00 (using Beiki's lag: 45ms)

# View stored lags
!lag list
# → Stored lags: Beiki: 45ms, Alice: 120ms
```

---

## 5. Technical Notes

- Lag storage keyed by (server_name, nick) to support multiple servers
- One-way delay = RTT / 2 (assumes symmetric latency)
- If target is a channel, lag measurement isn't possible (broadcast), so require nick lag or skip compensation
- Consider adding manual lag override for reliability
