# find-the-needle-live

Public data for the **Find the Needle** VRChat world, read with VRChat String Loading (`*.github.io` is trusted):

- `supporters.json`: the lobby Supporters board. **Display names and tier numbers only.**

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

Tests run before every sync: `python -m unittest discover -s tools/tests` (18 passing).
