# DLV Automation website

Repository for managing, updating and publishing the DLV Automation website.

## Production file

- `index.html` — current website
- Design baseline: DLV Automation v6
- Future edits should update the existing site rather than replace the design from scratch.

## Publishing

GitHub is the source of truth. The new paid Timeweb hosting target is configured with an encrypted GitHub Actions FTPS deployment (`.github/workflows/deploy-timeweb.yml`). DNS stays at the old production host until Timeweb is verified. See [TIMEWEB_DEPLOY_SETUP.md](TIMEWEB_DEPLOY_SETUP.md) for the no-downtime switch.
