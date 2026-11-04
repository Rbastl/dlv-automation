# DLV Automation website

Repository for managing, updating and publishing the DLV Automation website.

## Production file

- `index.html` — current website
- Design baseline: DLV Automation v6
- Future edits should update the existing site rather than replace the design from scratch.

## Publishing

GitHub `main` is the source of truth; the production domain is hosted at [dlvautomation.ru](https://dlvautomation.ru/). Timeweb pulls the public static site from GitHub via HTTPS/Cron using [this synchronization script](scripts/timeweb_sync_from_github.sh). Monitor the deployed revision separately from the GitHub CI result. Do not publish internal scripts or credentials.

## IEC 61131-3 code references

- [Vendor-neutral analogue input scaling in Structured Text](examples/iec61131-3-linear-scale/README.md) — raw endpoints, engineering units, quality flags, and eight independent test cases. Educational example, not a certified PLC library.

## Engineering services and reference work

The public examples in this repository are educational. Project engineering and modernization services are described separately on the production website:

- [Modernize existing PLC/SCADA systems](https://dlvautomation.ru/modernizaciya-asu-tp/#modernization-options) — compare targeted PLC changes, an HMI/SCADA upgrade and a controller migration, with commissioning requirements.
- [PLC/SCADA software subcontracting](https://dlvautomation.ru/outsourcing-asu-tp/) — scoped development and acceptance for OEMs and integrators.
- [Published industrial automation projects](https://dlvautomation.ru/projects/) — documented reference tasks and technology stacks.

These links describe the company's project services; the open example below does not certify or promise any plant-specific implementation.

## Free engineering resources

The website publishes a [free RSS 2.0 feed](https://dlvautomation.ru/feed.xml) of its own engineering articles for feed-reader subscriptions and voluntary syndication. The feed contains summaries and canonical article links, not duplicate full-text articles.

- [4–20 mA / 0–10 V PLC signal scaling calculator and I/O check points](https://dlvautomation.ru/blog/4-20ma-plk-kalkulyator/) — engineering value, raw counts, reverse conversion and five-point CSV checklist.
- [Modbus register and offset calculator](https://dlvautomation.ru/blog/modbus-registry-kalkulyator/) — practical RTU/TCP examples.
- [FAT, I/O and SAT commissioning checklist](https://dlvautomation.ru/blog/fat-io-testy-pnr-asu-tp/) — free CSV template, browser-only completeness check (no upload) and engineering acceptance criteria.
- [Offline FAT/I-O CSV completeness review](examples/fat-io-csv-review/README.md) — free Python checker for the browser-generated test protocol: duplicate IDs, missing acceptance evidence, and documented PASS/FAIL status. Documentation only, no PLC communication.
- [CIP SCADA event log CSV template](https://dlvautomation.ru/cip-moyka-otchety-scada/#cip-report-template) — original browser-generated field checklist for cycle ID, phases, measurements, data quality and exceptions; not sanitation validation.
- [Industrial AI 2026: Siemens/NVIDIA, predictive maintenance and readiness checklist](https://dlvautomation.ru/blog/ii-na-proizvodstve-2026/#ai-pilot-checklist) — sourced analysis plus a free, locally generated 12-point CSV to prepare an AI/PLC/SCADA pilot. No customer data upload, no AI integration claims beyond verified PLC/SCADA work.

These resources are reference aids, not substitutes for OEM module manuals or safety procedures.
