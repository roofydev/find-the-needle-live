# find-the-needle-live

Public data for the **Find the Needle** VRChat world. The world reads these files with VRChat String Loading
(`*.github.io` is on VRChat's trusted list, so players never see an "untrusted URL" prompt):

- `supporters.json`: names on the lobby Supporters board, refreshed daily from Patreon by GitHub Actions.

GitHub Pages uses the included Actions workflow, which publishes on pushes, daily, and on manual dispatch.
Without a Patreon token it publishes the existing list successfully; automatic member updates start once configured.

Setup (once): Settings → Pages → Source → GitHub Actions. Settings → Secrets → Actions →
`PATREON_CREATOR_TOKEN` = the creator access token from https://www.patreon.com/portal/registration/register-clients.
Optional `supporter_names.json`: `{"<patreon member id or full name>": "In-world name"}` ("" hides someone).
