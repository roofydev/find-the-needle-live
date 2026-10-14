"""Checks remote-config.json (event hours) before it is published.

The world (EventManager.OnStringLoadSuccess in roofydev/NeedleHaystack) reads three optional blocks and ignores
anything it can't use, so a typo would fail silently in game. This check fails the publish workflow instead, and
the last good file stays live. The limits match the world's own: Unix times 0 to 2100, hours 0 to 23, minutes
0 to 240, Cash x1 to x2, tokens x1 to x3.

    python tools/check_remote_config.py [remote-config.json]
"""

import json
import re
import sys
from pathlib import Path

MAX_UNIX = 4102444800  # 2100-01-01, the world's UnixOk limit
EVENT_ID = re.compile(r"^[1-9][0-9]*$")
BLOCKS = ("events", "happy_hour", "farm_hour")


class ConfigError(ValueError):
    pass


def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ConfigError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def _reject_constant(name):
    raise ConfigError(f"{name} is not valid JSON for the world")


def parse(text):
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except json.JSONDecodeError as e:
        raise ConfigError(f"not valid JSON: {e}") from None


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_whole(v):
    return _is_number(v) and float(v).is_integer()


def _keys(block, where, allowed):
    for key in block:
        if not key.startswith("_") and key not in allowed:
            raise ConfigError(f"{where}: unknown key {key!r} (allowed: {', '.join(allowed)})")


def _unix(block, key, where, positive=False):
    if key not in block:
        return 0
    v = block[key]
    if not _is_number(v) or v < 0 or v >= MAX_UNIX or (positive and v <= 0):
        low = "after 1970" if positive else "0 or more"
        raise ConfigError(f"{where}.{key} must be a Unix time in seconds, {low} and before 2100")
    return v


def _mult(block, key, where, top):
    if key in block and (not _is_number(block[key]) or not 1 <= block[key] <= top):
        raise ConfigError(f"{where}.{key} must be a number from 1 to {top:g}")


def _window(block, where):
    start, end = _unix(block, "start_unix", where), _unix(block, "end_unix", where)
    if start > 0 and end > 0 and end <= start:
        raise ConfigError(f"{where}: end_unix must be after start_unix")
    return start, end


def check(cfg):
    """Raises ConfigError for anything the world would ignore or misread; returns a one-line summary."""
    if not isinstance(cfg, dict):
        raise ConfigError("the file must be one JSON object { ... }")
    _keys(cfg, "remote-config", BLOCKS)
    for name in BLOCKS:
        if name in cfg and not isinstance(cfg[name], dict):
            raise ConfigError(f"{name} must be an object {{ ... }}")
    summary = []

    events = cfg.get("events", {})
    for eid, ev in events.items():
        where = f"events.{eid}"
        if not EVENT_ID.match(eid):
            raise ConfigError(f"events: {eid!r} is not an event id (a whole number, like \"1\")")
        if not isinstance(ev, dict):
            raise ConfigError(f"{where} must be an object {{ ... }}")
        _keys(ev, where, ("enabled", "start_unix", "end_unix"))
        if "enabled" in ev and not isinstance(ev["enabled"], bool):
            raise ConfigError(f"{where}.enabled must be true or false")
        _window(ev, where)
    if events:
        summary.append(f"{len(events)} event override(s)")

    happy = cfg.get("happy_hour", {})
    _keys(happy, "happy_hour", ("start_unix", "end_unix", "cash_mult", "token_mult"))
    start, end = _window(happy, "happy_hour")
    _mult(happy, "cash_mult", "happy_hour", 2)
    _mult(happy, "token_mult", "happy_hour", 3)
    if start > 0 and end > start:
        summary.append(f"happy hour {int(start)} to {int(end)}")

    farm = cfg.get("farm_hour", {})
    _keys(farm, "farm_hour", ("enabled", "first_unix", "hours_utc", "minutes", "cash_mult", "token_mult"))
    if "enabled" in farm and not isinstance(farm["enabled"], bool):
        raise ConfigError("farm_hour.enabled must be true or false")
    _unix(farm, "first_unix", "farm_hour", positive=True)
    if "hours_utc" in farm:
        hours = farm["hours_utc"]
        if not isinstance(hours, list) or not hours or not all(_is_whole(h) and 0 <= h <= 23 for h in hours):
            raise ConfigError("farm_hour.hours_utc must be a list of whole hours from 0 to 23, like [12, 19]")
    if "minutes" in farm and not (_is_whole(farm["minutes"]) and 0 <= farm["minutes"] <= 240):
        raise ConfigError("farm_hour.minutes must be a whole number from 0 to 240")
    _mult(farm, "cash_mult", "farm_hour", 2)
    _mult(farm, "token_mult", "farm_hour", 3)
    if farm.get("enabled") is False:
        summary.append("Farm Hour off")
    elif any(not k.startswith("_") for k in farm):
        summary.append("Farm Hour changed")

    return ", ".join(summary) or "no overrides (the built-in schedule runs)"


def main(argv):
    path = Path(argv[1] if len(argv) > 1 else "remote-config.json")
    try:
        summary = check(parse(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        print(f"{path}: {e}", file=sys.stderr)
        return 2
    print(f"{path}: OK, {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
