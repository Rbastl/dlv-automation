# DLV Automation — commercial SEO sprint: HMI/SCADA and Siemens MB_CLIENT

Date: 2026-11-02. Goal: target relevant B2B organic demand for industrial PLC/HMI/SCADA programming without copying rivals, inventing expertise, or expanding low-value URLs. No outreach/CRM/paid advertising.

## Research and segmentation

- Existing **private** Google Search Console records show emerging visibility for Russian HMI/SCADA project-development intent. Specific private query rows and client data are intentionally **not published here**. Source of truth: closed SEO sheet, tab `Google`/`Страницы`.
- Public commercial competitors:
  - https://mic-s.ru/uslugi/razrabotka-programmnogo-obespecheniia-asu-tp2 (PLC/SCADA, WinCC, InTouch and existing-software modernization)
  - https://www.project-p.ru/programmirovanie/ (PLC, SCADA, HMI development)
  - https://step-eng.ru/service/razrabotka-po (PLC, SCADA, HMI software scope and deliverables)
- Manufacturer technical sources for Siemens-specific diagnosis:
  - https://docs.tia.siemens.cloud/r/en-us/v21/modbus-tcp-s7-1200-s7-1500-s7-1200-g2/modbus-tcp-for-the-library-versions-v4.0-and-later-of-the-s7-1200-cpus-and-as-of-v3.x-of-the-s7-1500-cpus-s7-1200-s7-1500-s7-1200-g2/mb_client-communicating-via-profinet-as-a-modbus-tcp-client-s7-1200-s7-1500-s7-1200-g2/description-of-mb_client-s7-1200-s7-1500-s7-1200-g2
  - https://docs.tia.siemens.cloud/r/en-us/v21/modbus-tcp-s7-1200-s7-1500-s7-1200-g2/modbus-tcp-for-the-library-versions-v4.0-and-later-of-the-s7-1200-cpus-and-as-of-v3.x-of-the-s7-1500-cpus-s7-1200-s7-1500-s7-1200-g2/mb_client-communicating-via-profinet-as-a-modbus-tcp-client-s7-1200-s7-1500-s7-1200-g2/connect-parameter-s7-1200-s7-1500-s7-1200-g2?contentId=MVRyT9bIDwT1EqNHfVg~iA

Competitor page structure is **not** proof of competitor traffic, ranking, conversion, or volume. Siemens details vary across CPU firmware and MB_CLIENT library versions. Never republish third-party examples as own projects.

## Unique destination per user intent (avoid cannibalization)

| Buyer/search intent | Existing URL | Added unique value |
| --- | --- | --- |
| Development of an HMI and SCADA project, requirements | `/scada-hmi/` | Exact technical brief covering data source, tag freshness, alarms, operator roles, archive, acceptance; scoped contact link |
| Siemens S7-1200/S7-1500 PLC programming with MB_CLIENT integration | `/siemens-tia-portal/` | Siemens-specific diagnostic checkpoints for CONNECT/REQ/BUSY/DONE/ERROR/STATUS, link to OEM manuals; **no live force/write instructions** |
| WinCC vs InTouch vs FactoryTalk in a legacy installation | `/blog/vybor-scada-wincc-intouch-factorytalk/` | Decision matrix prompts and one contextual link to the SCADA scope, without generic product rankings |

The site stays at **49 sitemap URLs**. `lastmod` updated only for the three materially changed pages. Page templates, canonical URLs, hreflang, global navigation, JS and V6 layout preserved. Two additional competitor **public page URLs** added to `seo/competitors.json` for weekly title/H1 tracking, not traffic measurement.

## Required tests / next actions

1. CI static SEO integrity: 49 unique sitemap URLs, one H1 per page, correct canonical/hreflang, all internal targets, valid HTML/JSON-LD. V6 Playwright across mobile/desktop widths, including `/scada-hmi/#scada-tz-checklist`.
2. Inspect PR change scope before merge; do not merge failed tests.
3. GitHub main and Timeweb are separate: `dlv-deploy-revision.txt` at production must match main before claiming publication. Intermittent external Timeweb timeouts require host access/error log investigation; they do **not** prove Googlebot/YandexBot blocking.
4. Measure after crawler refresh: comparable *nonoverlapping* GSC seven-day intervals, per-URL impressions/clicks/CTR, commercial leads when attribution is available; Yandex separately only after actual data appears.
5. Next content iteration: prioritize already indexed content with buyer intent and non-indexed commercial pages after technical/live checks; do not mass-generate pages or edit the same title daily.

**SEO cannot guarantee traffic numbers, position, index inclusion, leads or immediate recrawl.**
