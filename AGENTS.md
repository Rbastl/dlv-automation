# DLV Automation website working instructions

This repository is the website and SEO workstream for dlvautomation.ru. Keep sales prospecting, customer correspondence, tender work and commercial CRM changes in their separate workstream.

## Sources and design

- Preserve the approved V6 design, current navigation and responsive layout. Improve the existing site.
- main is the source of truth. Timeweb is the production host; GitHub Pages is only a technical control.
- The current sitemap contains 50 unique URLs. Add a URL only for a demonstrated independent search intent and update the matching checks intentionally.
- Preserve the 21 verified reference projects. Use exact equipment models only when supported by the reference. Do not invent client work, certifications, team capacity, traffic or outcomes.
- Read the current private SEO tracker and its existing 100-step plan before selecting work. Do not create a competing plan or tracker.

## Change workflow

1. Read the relevant source, open PRs, existing issues and latest Actions evidence.
2. Work on a separate branch and open a focused PR. Keep scope small.
3. Require DLV static SEO integrity and DLV V6 complete UX and responsive QA to pass for the PR head before merging. A skipped or missing check is not a pass.
4. After merging site changes, compare the public /dlv-deploy-revision.txt with the current main SHA. Distinguish deployment lag from a failed publish.
5. Record the actual result, evidence URL, date and next step in the existing private SEO tracker. Code merged, production published, indexed and receiving traffic are separate states.

## Existing monitoring

Reuse existing workflows rather than adding overlapping schedules:

- seo-public-monitor.yml: daily production diagnostics; weekly public competitor audit.
- seo-search-analytics.yml: independent Google and Yandex collection into the private tracker.
- google-index-coverage.yml: read-only Google URL inspection.
- yandex-priority-recrawl.yml: manual, explicit re-crawl only.
- deploy-timeweb.yml: legacy FTPS, manual only. Normal publishing uses Timeweb-side HTTPS/Cron.

## Evidence and access

- Compare traffic using non-overlapping seven-day periods and show the dates. Do not sum query rows as total traffic.
- Missing Yandex metrics are unknown, not zero. A successful workflow may still report an unavailable upstream host.
- Do not infer Googlebot or YandexBot blocking from a timeout at one probe. Issue #43 remains the place for production connectivity evidence.
- Inspect actual HTTP redirects, TLS, robots, sitemap and revision independently. Do not change DNS, firewall, hosting or locks speculatively.
- Owner verification, account/legal acceptance and financial commitments require the owner's action.
- Keep credentials, verification codes, customer files, raw search analytics and private access logs out of this public repository and Actions logs.
- Editorial pitches, accepted topics, submitted manuscripts, published links and measured referrals are distinct states. Do not publish or send messages without the applicable authorization.
