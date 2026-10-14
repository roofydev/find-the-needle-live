# find-the-needle-live

Public data for the **Find the Needle** VRChat world, read with VRChat String Loading (`*.github.io` is trusted):

- `supporters.json`: the lobby Supporters board. **Display names and tier numbers only.**
- `remote-config.json`: event hours (happy hours, the Saturday Farm Hour, event dates). **Times and multipliers only.**

## Automatic credits (GH #104, owner preference 2026-10-05)

Active paid members appear automatically using the profile display name returned by Patreon API v2 (`member.full_name`).
The membership tier and About page explain this before joining and offer a different name or removal by message.
The workflow refreshes hourly (GitHub may delay scheduled runs); the world loads the current feed on instance join.
No world re-upload is needed for membership/name changes.

**`SUPPORTER_ALIASES` is an optional Actions secret** for chosen names and opt-outs, never a public mapping:

```json
{"version": 1, "members": {"<member id>": {"alias": "Chosen Name"}, "<another id>": {"hidden": true}}}
```

- Missing/empty overrides use Patreon display names automatically. Patreon identity masking, null/empty names,
  and `hidden: true` omit a member; names never fall back to email, member id or another account field.
- An explicit chosen alias replaces the Patreon name. Legacy `consent: true` aliases work; `consent: false` hides
  a member. Names lose `<>{}\`, control and invisible characters and are cut to 28 characters.
- A malformed secret stops the sync with exit code 2 and leaves `supporters.json` unchanged.
- Former, declined and free members are never listed. A paid tier whose title isn't in `patreon.json` counts as 1.
- Logs print counts only. The public feed contains display name + tier; member ids, emails and payment details are never published.
- To hide someone: set `"hidden": true` and run the workflow. **Deleting an override restores automatic naming.**
- To change a name: set a chosen `alias` and run the workflow. Patreon profile changes also propagate automatically.
- Patreon member ids: Patreon creator page → Audience → a member's page URL, or the API `/campaigns/{id}/members`.

## Secrets

- `PATREON_CREATOR_TOKEN`: creator access token (https://www.patreon.com/portal/registration/register-clients).
- `SUPPORTER_ALIASES`: optional overrides above (may be empty: automatic naming).

## Event hours (`remote-config.json`)

Owner decision 2026-10-14: event hours can change without a world upload. Worlds uploaded from 5 November 2026 read
this file when an instance starts and every 30 minutes. Edit it on GitHub and commit to `main`; the workflow checks it
and publishes it. New instances use it right away, running ones within 30 minutes.

- `farm_hour`: the free Saturday hour, with or without an event. `enabled: false` switches it off; `first_unix` moves
  its first day; `hours_utc` are the UTC hours the weeks take in turn (0 to 23); `minutes` is its length (0 to 240);
  `cash_mult` (1 to 2) and `token_mult` (1 to 3).
- `happy_hour`: `start_unix`, `end_unix`, `cash_mult`, `token_mult`. It only works while an event runs.
- `events`, by event id (`"1"` = Harvest Moon): `start_unix` and `end_unix` move it; `enabled: false` cancels it;
  `enabled: true` with no `start_unix` runs it now.

Times are Unix seconds in UTC (1794052800 = Saturday 7 November 2026, 12:00 UTC). Empty blocks keep the built-in
schedule, and the world caps every number whatever the file says. Running instances keep what they last read until
they close, so to stop something early set a time that has passed instead of deleting it.

Examples: keep only the evening Farm Hour with `"farm_hour": {"hours_utc": [19]}`; switch it off with
`"farm_hour": {"enabled": false}`.

A mistake (bad JSON, a misspelt name, a number out of range, an end before its start) fails the workflow with the
reason (`tools/check_remote_config.py`), and the last good file stays live. Supporter updates wait until it is fixed.

Tests run before every sync: `python -m unittest discover -s tools/tests` (28 passing).
