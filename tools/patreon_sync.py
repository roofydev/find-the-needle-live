"""Automatically publish active paid supporters' Patreon display names (GH #104).

The tier and About page explain automatic public credits before membership.
- Request only full_name (Patreon profile display name), patron_status and entitled tiers; never emails or payment details.
- Hidden/missing Patreon names are omitted. Protected per-member overrides can change a name or hide it.
- Public JSON holds just {"name": display_name, "tier": 1..3}; logs print counts, never ids or names.

Inputs (environment, never committed):
  PATREON_CREATOR_TOKEN  creator access token (GitHub Actions secret)
  SUPPORTER_ALIASES      optional protected overrides (GitHub Actions secret), JSON:
                         {"version": 1, "members": {"<member id>": {"alias": "Chosen Name"}, "<another id>": {"hidden": true}}}
                         Missing/empty -> use available Patreon names. Malformed -> exit 2, nothing written.
                         Legacy consent:true aliases still work; consent:false means hidden.

    python Tools/Community/patreon_sync.py [--root DIR] [--out FILE]

Tier mapping: a member's highest paid entitled tier is matched by title against patreon.json "tiers"
(Seedling=1, Farmhand=2, Golden Needle=3); another paid tier counts as 1. No paid tier -> not listed.
"""

import argparse
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://www.patreon.com/api/oauth2/v2"
ROOT = Path(__file__).resolve().parents[2]
MAX_ALIAS = 28
MAX_SUPPORTERS = 120


class AliasMapError(ValueError):
    pass


def clean_alias(value):
    """Display-safe alias: no rich-text brackets, control or format characters, trimmed, at most MAX_ALIAS chars."""
    if not isinstance(value, str):
        return ""
    out = []
    for ch in value:
        if ch in "<>{}\\" or unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            continue
        out.append(" " if unicodedata.category(ch) == "Zs" else ch)
    return " ".join("".join(out).split())[:MAX_ALIAS].strip()


def parse_alias_map(raw):
    """Returns {member_id: alias | None}; None hides a member. Malformed overrides stop publication."""
    if raw is None or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AliasMapError(f"alias map is not JSON (line {e.lineno})") from None
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("members"), dict):
        raise AliasMapError('alias map must be {"version": 1, "members": {...}}')
    aliases = {}
    for member_id, entry in data["members"].items():
        if not isinstance(member_id, str) or not member_id or not isinstance(entry, dict):
            raise AliasMapError("override entries must be objects keyed by member id")
        if any(key in entry and not isinstance(entry[key], bool) for key in ("hidden", "consent")):
            raise AliasMapError("hidden and legacy consent must be booleans")
        if entry.get("hidden") is True or entry.get("consent") is False:
            aliases[member_id] = None
            continue
        alias = clean_alias(entry.get("alias"))
        if not alias:
            raise AliasMapError("a visible override needs a nonempty display-safe alias")
        aliases[member_id] = alias
    return aliases


def build_supporters(pages, tier_ids, aliases):
    """Return public names/tiers for active paid members, honoring hidden names and protected overrides."""
    out = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        tiers = {}
        for t in page.get("included") or []:
            if isinstance(t, dict) and t.get("type") == "tier" and isinstance(t.get("attributes"), dict):
                tiers[t.get("id")] = t["attributes"]
        for m in page.get("data") or []:
            if not isinstance(m, dict):
                continue
            member_id = m.get("id")
            if not isinstance(member_id, str) or not member_id:
                continue
            attrs = m.get("attributes") if isinstance(m.get("attributes"), dict) else {}
            if attrs.get("patron_status") != "active_patron":
                continue                                    # former / declined / deleted members
            name = clean_alias(aliases[member_id] if member_id in aliases else attrs.get("full_name"))
            if not name:
                continue                                    # opt-out, identity hidden, or missing name: no fallback
            rel = (((m.get("relationships") or {}).get("currently_entitled_tiers") or {}).get("data")) or []
            paid = []
            for ref in rel if isinstance(rel, list) else []:
                t = tiers.get(ref.get("id")) if isinstance(ref, dict) else None
                cents = t.get("amount_cents") if t else None
                if isinstance(cents, int) and cents > 0:
                    paid.append(t)
            if not paid:
                continue
            best = max(paid, key=lambda t: t["amount_cents"])
            title = best.get("title") if isinstance(best.get("title"), str) else ""
            tier = tier_ids.get(title.strip().lower(), 1)
            if member_id not in out or tier > out[member_id]["tier"]:
                out[member_id] = {"name": name, "tier": tier}
    listed = sorted(out.values(), key=lambda s: (-s["tier"], s["name"].lower()))
    return listed[:MAX_SUPPORTERS]


def fetch_pages(token):
    def get(url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": "FindTheNeedle-SupportersSync/3.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    campaigns = get(f"{API}/campaigns").get("data") or []
    if not campaigns:
        return []
    query = urllib.parse.urlencode({
        "include": "currently_entitled_tiers",
        "fields[member]": "full_name,patron_status",
        "fields[tier]": "title,amount_cents",
        "page[count]": "500",
    })
    url = f"{API}/campaigns/{campaigns[0]['id']}/members?{query}"
    pages = []
    while url and len(pages) < 50:
        page = get(url)
        pages.append(page)
        url = (page.get("links") or {}).get("next")
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT), help="project root, or the live-site repo (configs at its top level)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg_dir = root / "Design/Community" if (root / "Design/Community/patreon.json").exists() else root
    out = Path(args.out) if args.out else cfg_dir / "supporters.json"

    token = os.environ.get("PATREON_CREATOR_TOKEN")
    if not token:
        print("PATREON_CREATOR_TOKEN not set: nothing synced.")
        return 0
    try:
        aliases = parse_alias_map(os.environ.get("SUPPORTER_ALIASES"))
    except AliasMapError as e:
        print(f"SUPPORTER_ALIASES rejected ({e}); supporters.json left unchanged.", file=sys.stderr)
        return 2

    config = json.loads((cfg_dir / "patreon.json").read_text(encoding="utf-8"))
    tier_ids = {t["name"].strip().lower(): int(t["id"]) for t in config["tiers"]}
    supporters = build_supporters(fetch_pages(token), tier_ids, aliases)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"updated": date.today().isoformat(), "supporters": supporters}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(supporters)} active paid supporter(s) published; {len(aliases)} protected override(s) configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
