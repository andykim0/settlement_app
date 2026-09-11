# settlement_app — settlement manager for delivery-rider branches

A desktop tool that automates the daily settlement cycle of Korean food-delivery branches (Baemin, Coupang Eats): log in to each platform, pull the day's Excel reports, and settle every rider's pay with tax and insurance deductions — work that branch staff otherwise do by hand in spreadsheets every morning.

**Stack:** Python 3.11 · PySide6 · Playwright · PostgreSQL 16 · psycopg 3 · pytest

> Status: the scraping / download pipeline and run monitoring are wired end to end. Parts of the settlement math and several dashboard bindings are still stubs — see [`WIRING.md`](WIRING.md) for the exact per-widget status. This is a working prototype, not a finished product.

---

## Why it exists

Each branch manages dozens of riders across two platforms. Every day someone has to:

1. Log in to the Baemin and Coupang Eats branch portals — both require a one-time code (SMS or e-mail) on every login.
2. Download the day's delivery / settlement Excel reports.
3. Compute each rider's pay: platform fees, withholding tax, insurance, installments, deferrals.
4. Send the statements out and keep an audit trail.

There is no official API for any of this. The tool drives the portals with a real browser, relays the OTP codes automatically, and turns the spreadsheets into per-rider statements backed by a real database.

## Architecture

Layered, dependency-inward. The UI never touches a scraper or a database directly.

```
┌───────────────────────────────────────────────────────────────────┐
│ presentation/   PySide6 pages (Dashboard, Data Import, Excel      │
│                 Download, Settlement Run, Monitoring, Results,     │
│                 Settings) + dialogs + presenters                   │
└───────────────┬───────────────────────────────────────────────────┘
                │ signals / DTOs
┌───────────────▼───────────────────────────────────────────────────┐
│ application/    use cases (EnqueueDownloadRun, RunSettlement)     │
│                 services (Download, Dashboard, Results, RunRegistry)│
│                 DTOs, RunState, ScraperProtocol                     │
└───────┬─────────────────────────────────────┬─────────────────────┘
        │ ports                               │
┌───────▼──────────────┐            ┌─────────▼─────────────────────┐
│ domain/              │            │ infrastructure/                │
│ Branch, Rider,       │◄───────────│ scrapers/  baemin_*, coupang_* │
│ DownloadJob,         │            │            coupang_imap_otp    │
│ SettlementRun,       │            │            server/sms_otp_waiter│
│ ScraperHost,         │            │ db/        postgres (psycopg)  │
│ exceptions           │            │ settings/  app_settings        │
└──────────────────────┘            └────────────────────────────────┘
                 workers/  ScraperWorker on QThreadPool
                           → RunRegistry emits RunState → UI updates
```

- **Scrapers** (`infrastructure/scrapers/`) use Playwright. Coupang's e-mail OTP is read through IMAP (`coupang_imap_otp.py`); SMS OTPs arrive through a small relay (`server/sms_otp_waiter.py`). Each platform has a `*_core` (login + navigation) and an extractor for its Excel layout.
- **Workers** run scrapers off the UI thread on `QThreadPool`; a `RunRegistry` tracks every run's `RunState` and pushes updates to the pages through Qt signals, so the Monitoring page is live without polling.
- **Use cases** are the only entry points the UI calls; services and repositories sit behind them, so a scraper or database can be swapped without touching a page.

## Data model

PostgreSQL 16, two databases on one cluster (mirroring the target Aurora layout), 13 tables — schema in [`infrastructure/db/sql/`](infrastructure/db/sql/).

| Database | Tables |
|---|---|
| `delivery_shared` | accounts + refresh tokens, branches, delivery platforms + branch platform accounts, common / individual charges, installment plans, payment deferrals, equipment + photos |
| `delivery_rider` | riders, branch–rider affiliations |

Conventions that matter:

- **Money is `numeric(14,2)` in SQL and `Decimal` in Python. Never `float`.**
- **Credentials are encrypted at rest** — `(ciphertext bytea, iv bytea)` column pairs under AES-256-GCM with a fresh 12-byte IV per encryption; the key never lives in the database, only an alias resolved from the environment / KMS.
- **Soft delete everywhere** — `deleted_at timestamptz`; reads filter `WHERE deleted_at IS NULL`.
- **Cross-database references are logical**, not foreign keys; integrity is enforced in code.
- Local secrets (portal logins, IMAP) go through the OS keyring, not config files.

## Design decisions

| Decision | Why |
|---|---|
| Desktop app, not a web service | One operator per branch, sensitive rider PII, and portal sessions that behave better from a real local browser. |
| Playwright over reverse-engineered HTTP | No official APIs; the portals change often and gate every login behind OTP. Driving the real UI plus OTP relays is more robust than replaying requests. |
| Layered architecture for a "small" tool | The scrapers are the most fragile part of the system. Isolating them behind a `ScraperProtocol` means a portal change is a one-module fix. |
| `Decimal` + `numeric(14,2)` | Settlement is money that gets paid out. Rounding drift is not acceptable. |
| AES-GCM with per-row IV and external key alias | Portal passwords must be stored to automate login, so they are encrypted with an AEAD cipher and the key is rotatable without touching rows. |
| Two databases on one cluster | Matches the production Aurora shape so the local Docker stack and production share one schema. |

## Run it

```bash
docker compose up -d                  # PostgreSQL 16 + Adminer (localhost:8080)
pip install -e ".[dev,db]"
playwright install chromium
settlement-app                        # launches the PySide6 UI
pytest                                # unit + integration tests
```

Environment variables for portal accounts and the OTP relay are read by `infrastructure/settings/app_settings.py`; nothing is hard-coded.

## Repository layout

```
src/settlement_app/
  presentation/   pages, dialogs, widgets, theme, presenters
  application/    use_cases, services, dto
  domain/         entities, value_objects, exceptions
  infrastructure/ scrapers, db, settings, filesystem, repositories
  workers/        scraper_worker
infrastructure/db/   init scripts + SQL schemas (docker entrypoint)
tests/               unit/, integration/
WIRING.md            per-widget wiring status (what is live vs. stub)
REVIEW.md            design notes: Docker stack, schema conventions, security
```
