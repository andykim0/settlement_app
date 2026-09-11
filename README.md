# settlement_app — settlement manager for delivery-rider branches

A desktop tool for the daily settlement cycle of Korean food-delivery branches (Baemin, Coupang Eats). Today it automates the painful front half — logging in to each platform through its OTP gate and pulling the day's Excel reports, with live run monitoring. The back half — per-rider settlement with tax and insurance deductions, and persistence to PostgreSQL — is specified (schema, use cases, DTOs) but not implemented yet.

**Stack:** Python 3.11 · PySide6 · Playwright · pytest — PostgreSQL 16 / psycopg 3 for the planned persistence layer (Docker stack included; no consumer in the app yet)

> Status, honestly: scraping, Excel download, and the run registry / Monitoring page are real. `RunSettlementUseCase` raises `NotImplementedError`, `infrastructure/repositories/` is empty, and nothing calls the database pool yet. [`WIRING.md`](WIRING.md) lists every widget as live / partial / stub. Built as a focused sprint and imported in one commit; `WIRING.md` and `REVIEW.md` are the record of what was decided when.

---

## Why it exists

Each branch manages dozens of riders across two platforms. Every day someone has to:

1. Log in to the Baemin and Coupang Eats branch portals — both require a one-time code (SMS or e-mail) on every login.
2. Download the day's delivery / settlement Excel reports.
3. Compute each rider's pay: platform fees, withholding tax, insurance, installments, deferrals.
4. Send the statements out and keep an audit trail.

There is no official API for any of this. The tool drives the portals with a real browser and relays the OTP codes automatically. Turning the spreadsheets into per-rider statements is the next milestone.

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
- **Workers** run scrapers off the UI thread on `QThreadPool`. `RunRegistry` (`application/services/run_registry.py`) is the piece with the most engineering in it: a thread-safe run state machine that emits Qt signals (`run_added`, `run_status_changed`, `run_log_appended`, `run_progress_updated`) so the Monitoring page updates live without polling. It is also the best-tested module in the repo (`tests/unit/test_run_registry.py`).
- **Use cases** are the only entry points the UI calls; services and repositories sit behind them, so a scraper or database can be swapped without touching a page.

## Data model

PostgreSQL 16, two databases on one cluster (mirroring the target Aurora layout), 13 tables — schema in [`infrastructure/db/sql/`](infrastructure/db/sql/).

| Database | Tables |
|---|---|
| `delivery_shared` | accounts + refresh tokens, branches, delivery platforms + branch platform accounts, common / individual charges, installment plans, payment deferrals, equipment + photos |
| `delivery_rider` | riders, branch–rider affiliations |

Conventions that matter:

- **Money is `numeric(14,2)` in SQL and `Decimal` in Python. Never `float`.**
- **Credential columns are specified as AES-256-GCM** — `(ciphertext bytea, iv bytea)` pairs with a fresh 12-byte IV per encryption and an `encryption_key_alias` that resolves to a key in the environment / KMS, never in the database. This is a schema contract today; the Python encrypt / decrypt path is not written yet (the SQL comments were written against a Java `Cipher` API, so the client side needs its own implementation).
- **Soft delete everywhere** — `deleted_at timestamptz`; reads filter `WHERE deleted_at IS NULL`.
- **Cross-database references are logical**, not foreign keys — `delivery_rider` and `delivery_shared` may be split across services later, so integrity between them is enforced in code on purpose.
- Coupang's portal and IMAP passwords come from the OS keyring; the Baemin password is still read from a plain environment variable (`baemin_scraper.py`) — the next thing to close.

## Design decisions

| Decision | Why |
|---|---|
| Desktop app, not a web service | One operator per branch, sensitive rider PII, and portal sessions that behave better from a real local browser. |
| Playwright over reverse-engineered HTTP | No official APIs; the portals change often and gate every login behind OTP. Driving the real UI plus OTP relays is more robust than replaying requests. |
| Layered architecture for a "small" tool | The scrapers are the most fragile part of the system. Isolating them behind a `ScraperProtocol` means a portal change is a one-module fix. |
| `Decimal` + `numeric(14,2)` | Settlement is money that gets paid out. Rounding drift is not acceptable. |
| AES-GCM (specified) with per-row IV and external key alias | Portal passwords have to be stored to automate login; an AEAD cipher plus an external key alias means the key can rotate without rewriting rows. |
| Two databases on one cluster, no cross-database FKs | Mirrors the target Aurora layout so the local Docker stack and production share one schema, and leaves room to split the rider database into its own service. |

## Run it

```bash
docker compose up -d                  # PostgreSQL 16 + Adminer (localhost:8080)
pip install -e ".[dev,db]"
playwright install chromium
settlement-app                        # launches the PySide6 UI
pytest                                # 20 unit tests (run registry state machine, settings resolution)
```

Portal accounts and the OTP relay are configured through `infrastructure/settings/app_settings.py` (environment variables + keyring). The Docker stack uses a local-only `dev` password fallback for `localhost`; any other host requires the password environment variable.

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
