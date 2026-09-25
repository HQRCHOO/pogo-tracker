# pogo-tracker

The poller behind the TrackMaster dashboard. It checks Pokémon GO events, raid
bosses, GO Plus+ stock and card-game releases on a schedule, writes one
`dashboard.json` to Google Drive, and sends alerts to Discord and a morning
digest to Slack.

- Edit what it watches in `config/watchlist.yaml`.
- Keys and tokens are GitHub secrets, never files in this repo.
- Setup steps: the Revisions tab on the TrackMaster dashboard, or the build guide.

Run locally without Drive: `LOCAL_DASHBOARD=dashboard.json python -m poller.main --force --dry-run`
