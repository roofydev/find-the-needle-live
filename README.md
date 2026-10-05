# find-the-needle-live

Public data for the **Find the Needle** VRChat world, read with VRChat String Loading (`*.github.io` is trusted):

- `supporters.json`: the lobby Supporters board. **Opt-in aliases and tier numbers only.**

## Privacy (GH #104)

The sync never requests patron names or emails from Patreon. A patron appears only after they ask to be listed and
choose an alias; that choice lives in the **`SUPPORTER_ALIASES` Actions secret**, never in this public repo:

```json
{"version": 1, "members": {"<patreon member id>": {"alias": "Shown Name", "consent": true}}}
```

- `consent` must be exactly `true`; anything else, a missing entry, or an alias that cleans to nothing leaves the
  member out (fail closed). Aliases are stripped of `<>{}\`, control and invisible characters and cut to 28 chars.
- A malformed secret stops the sync with exit code 2 and leaves `supporters.json` unchanged.
- Former, declined and free members are never listed. A paid tier whose title isn't in `patreon.json` counts as 1.
- Logs print counts only. Member ids, names, emails and pledge amounts never reach the output or the commit.
- To remove someone: delete their entry (or set `"consent": false`) and run the workflow.
- Patreon member ids: Patreon creator page → Audience → a member's page URL, or the API `/campaigns/{id}/members`.

## Secrets

- `PATREON_CREATOR_TOKEN`: creator access token (https://www.patreon.com/portal/registration/register-clients).
- `SUPPORTER_ALIASES`: the alias map above (may be empty: nobody is listed).

Privacy tests run before every sync: `python -m unittest discover -s tools/tests`.
