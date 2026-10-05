"""Pull active Patreon members into the Supporters board list.

Stdlib only. Needs the creator access token from https://www.patreon.com/portal/registration/register-clients
(your client -> "Creator's Access Token") in the PATREON_CREATOR_TOKEN environment variable. Never commit the token.

    python Tools/Community/patreon_sync.py                    # writes Design/Community/supporters.json
    python Tools/Community/patreon_sync.py --out live/supporters.json

Tier mapping: a member's highest entitled tier is matched by title against Design/Community/patreon.json "tiers"
(Seedling=1, Farmhand=2, Golden Needle=3). Unknown tiers count as 1.
Names: Patreon full name, shortened to "First L." for privacy, unless Design/Community/supporter_names.json maps the
Patreon member id (or full name) to a chosen in-world name, or to "" to hide that member.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

API = "https://www.patreon.com/api/oauth2/v2"
ROOT = Path(__file__).resolve().parents[2]


def get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": "FindTheNeedle-SupportersSync/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def short_name(full):
    parts = [p for p in (full or "").split() if p]
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT), help="project root, or the live-site repo (configs at its top level)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cfg_dir = root / "Design/Community" if (root / "Design/Community/patreon.json").exists() else root
    out = Path(args.out) if args.out else cfg_dir / "supporters.json"
    token = os.environ.get("PATREON_CREATOR_TOKEN")
    if not token:
        sys.exit("Set PATREON_CREATOR_TOKEN (creator access token).")

    config = json.loads((cfg_dir / "patreon.json").read_text(encoding="utf-8"))
    tier_ids = {t["name"].lower(): t["id"] for t in config["tiers"]}
    names_file = cfg_dir / "supporter_names.json"
    overrides = json.loads(names_file.read_text(encoding="utf-8")) if names_file.exists() else {}

    campaigns = get(f"{API}/campaigns", token)["data"]
    if not campaigns:
        sys.exit("No campaign on this Patreon account yet.")
    campaign = campaigns[0]["id"]

    query = urllib.parse.urlencode({
        "include": "currently_entitled_tiers",
        "fields[member]": "full_name,patron_status,pledge_relationship_start",
        "fields[tier]": "title,amount_cents",
        "page[count]": "500",
    })
    url = f"{API}/campaigns/{campaign}/members?{query}"
    supporters = []
    while url:
        page = get(url, token)
        tiers = {t["id"]: t["attributes"] for t in page.get("included", []) if t["type"] == "tier"}
        for m in page["data"]:
            a = m["attributes"]
            if a.get("patron_status") != "active_patron":
                continue
            entitled = [tiers[t["id"]] for t in m["relationships"]["currently_entitled_tiers"]["data"] if t["id"] in tiers]
            best = max(entitled, key=lambda t: t.get("amount_cents") or 0, default=None)
            tier = tier_ids.get((best or {}).get("title", "").lower(), 1)
            full = a.get("full_name") or ""
            name = overrides.get(m["id"], overrides.get(full, short_name(full)))
            if not name:
                continue   # hidden at the member's request
            supporters.append({"name": name[:28], "tier": tier, "since": (a.get("pledge_relationship_start") or "")[:10]})
        url = page.get("links", {}).get("next")

    supporters.sort(key=lambda s: (-s["tier"], s["since"] or "9999", s["name"].lower()))
    for s in supporters:
        s.pop("since")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"updated": date.today().isoformat(), "supporters": supporters}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(supporters)} active supporter(s) -> {out}")


if __name__ == "__main__":
    main()
