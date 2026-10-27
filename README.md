# DLV Automation website

Repository for managing, updating and publishing the DLV Automation website.

## Production file

- `index.html` — current website
- Design baseline: DLV Automation v6
- Future edits should update the existing site rather than replace the design from scratch.

## Publishing

GitHub `main` is the source of truth; the production domain is hosted at [dlvautomation.ru](https://dlvautomation.ru/). Timeweb pulls the public static site from GitHub via HTTPS/Cron using [this synchronization script](scripts/timeweb_sync_from_github.sh). Monitor the deployed revision separately from the GitHub CI result. Do not publish internal scripts or credentials.

## Free engineering resources

- [4–20 mA / 0–10 V PLC signal scaling calculator and I/O check points](https://dlvautomation.ru/blog/4-20ma-plk-kalkulyator/) — engineering value, raw counts, reverse conversion and five-point CSV checklist.
- [Modbus register and offset calculator](https://dlvautomation.ru/blog/modbus-registry-kalkulyator/) — practical RTU/TCP examples.
- [FAT, I/O and SAT commissioning checklist](https://dlvautomation.ru/blog/fat-io-testy-pnr-asu-tp/) — verification sequence and acceptance criteria.

These resources are reference aids, not substitutes for OEM module manuals or safety procedures.
