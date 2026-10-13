# DLV Automation website

Repository for managing, updating and publishing the DLV Automation website.

## Production file

- `index.html` — current website
- Design baseline: DLV Automation v6
- Future edits should update the existing site rather than replace the design from scratch.

## Publishing

GitHub `main` is the source of truth. Timeweb will securely pull public website updates via HTTPS using [scripts/timeweb_sync_from_github.sh](scripts/timeweb_sync_from_github.sh) and scheduled Timeweb Cron (after the trial period). Timeweb FTPS was unreliable and is disabled for automatic pushes. DNS remains on the existing live site until Timeweb is verified. See [TIMEWEB_DEPLOY_SETUP.md](TIMEWEB_DEPLOY_SETUP.md).
