# Venmito

**Herminio Bodon** · bodon2018@gmail.com

A data engineering solution for Venmito: five source files in four formats, conformed
into one Postgres database, with insights derived from it and served through two web
views — one for non-technical staff, one for the technical team.

Live: https://venmito-hb-interview.vercel.app

---

## 1. Diagnostics first

The system was not designed until the data was understood. The `diagnostics/`
notebooks are that work, and every design decision downstream traces back to
something found here.

| Notebook | What it does |
|---|---|
| `data_diagnostics.ipynb` | Reproduces every problem found in the raw files. Each check prints PASS/FAIL, where PASS means the defect was confirmed. Pure standard library — no pandas, no PyYAML — so the parsing is auditable rather than trusted. |
| `data_cleaning.ipynb` | Addresses the six findings. Nothing is deleted; every defect becomes a flag column. |
| `data_analysis.ipynb` | Exploratory analysis and visualisations, plus statistical tests of the patterns found. |

### What the data turned out to be

- **People are split across two files with incompatible schemas.** `people.json`
  and `people.yml` overlap on 228 ids; the union is 1002 people. Neither file is
  the whole population — France and Spain exist **only** in the YAML. Every field
  is encoded differently: `"0001"` vs `1`, `"Jamie Bright"` vs first/last,
  `"Montreal, Canada"` vs a nested object, `05/20/2000` vs `May 20, 2000`.
- **Id 998 means two different people** depending on the file, and one person
  (Fey Kuser) holds two ids with disjoint email and phone. A naive merge silently
  overwrites a real record.
- **Three different join keys.** Transfers join on id, transactions on phone,
  promotions on email *or* phone — 154 of 236 promotion rows are missing one of
  the two.
- **Promotions have duplicate primary keys.** Ids 200–212 each appear twice on
  unrelated rows.
- **Transactions contain arithmetic errors** (a zero price, a negative price) and
  one exact duplicate that double-counts revenue. The XML also nests `<item>`
  inside `<item>`, so a naive XPath double-counts every line.
- **Transfers contain 15 empty rows** clustered on three consecutive month-16ths —
  an ingestion outage, not noise — plus a self-transfer and several outlier
  patterns (a reciprocal round-trip, a same-day fan-out).

### The principle that came out of it

**Nothing is deleted.** Every defect becomes a flag column, so bad rows stay
auditable and the transfer patterns remain available as a fraud signal. The
analysis layer excludes them by query, not by removal.

A second finding worth stating: after excluding the planted entity, **no promotion
effect survives significance testing**, and a cross-validated classifier scores
AUC 0.56 against a 0.50 baseline. The analysis reports what the data supports and
says plainly where it does not.

---

## 2. Approach

Four stages, each isolated so it can be tested on its own.

```
ingestion  ->  conforming  ->  persistence  ->  analysis
```

- **`backend/app/ingestion/`** — one reader per format. Format and entity are
  detected from file *content*, not the filename, because a filename cannot be
  trusted on an upload endpoint. Nothing is cleaned here; a negative price is read
  faithfully and dealt with later, where the decision is visible.
- **`backend/app/conform/`** — normalisation, entity resolution, and the flag
  rules. No database access at all, which is what makes the whole pipeline
  testable offline against the real files.
- **`backend/app/db/`** — all SQL writes, in one place. Every write is an upsert on
  a natural key, so re-uploading corrects rows instead of duplicating them.
- **`backend/app/analysis/`** — read-only aggregation. Runs in Postgres rather than
  in Python, since the data is already there.

### Design decisions

**Three schemas.** `raw` holds files exactly as uploaded, `clean` holds the
conformed data, `ops` holds load history, quarantine and data-quality notes. A
policy change can be replayed from `raw` without the original file.

**Entity resolution is explicit and configurable.** `PEOPLE_PRECEDENCE` decides
which file wins a conflict; `DUPLICATE_POLICY` decides how a duplicate identity is
handled. Both live in config, not in code, because they are business decisions that
will change. Conflicts are *reported* before they are resolved — the id-998
collision would otherwise vanish silently.

**Constraints in the DDL.** `UNIQUE` on email and phone, foreign keys on every
person reference, `CHECK (quantity > 0)`. The duplicate identity would now be
rejected at insert time rather than discovered six analysis steps later.

**Retired natural keys are kept.** When two ids collapse into one entity, the
losing id's email and phone become aliases pointing at the survivor, so historical
files still resolve.

**Upload mode is explicit.** `append` (default) adds to what is stored; `replace`
makes the file the entity's contents. Defaulting to append means a re-upload can
never silently destroy data, and identical bytes are a no-op.

**Both views read the same numbers**, so they cannot disagree. The non-technical
headlines are generated from the computed values, not written by hand.

---

## 3. Technologies

| Layer | Choice | Why |
|---|---|---|
| Database | Supabase (Postgres) | The data is relational, and integrity is exactly what the id-998 collision violated |
| API | FastAPI + SQLAlchemy Core | Typed request handling; raw SQL where the work belongs in the database |
| Validation | Pydantic / pydantic-settings | Schema at the boundary, policies in config |
| Frontend | Plain JavaScript, ES modules | No build step. The design has no class system and no framework idioms, so a framework would add weight without paying for it |
| Charts | None — inline SVG | Datasets are 5–28 points. `charts.js` computes polyline coordinates and bar widths directly; a chart library would bring its own opinions about axes and colour |
| Notebooks | Standard library, then pandas | Diagnostics use no dependencies so the parsing can be audited; cleaning and analysis use pandas, matplotlib, scipy, statsmodels |
| Hosting | Vercel | Frontend and API deploy together from one repo |

---

## 4. Running it

### Prerequisites

Python 3.11+, and a Supabase project (or any Postgres).

### Database

Run the migrations in order in the Supabase SQL editor:

```
backend/migrations/0001_init.sql
backend/migrations/0002_load_modes.sql
```

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

Put your connection string in `.env` — Supabase → Project Settings → Database →
Connection string → URI. Remove the `[ ]` around the password; they are placeholder
markers, not part of the value.

```bash
uvicorn app.main:app --reload --port 8000
```

Check it: http://localhost:8000/health → `{"status":"ok","database":"reachable"}`

### Frontend

Any static server, in a second terminal:

```bash
cd frontend
python3 -m http.server 5173
```

Open http://localhost:5173. The frontend targets `localhost:8000` automatically
when served from localhost.

### Load the data

Through the UI (Upload button in either view), or:

```bash
curl -X POST http://localhost:8000/uploads \
  -F "files=@data/people.json" -F "files=@data/people.yml" \
  -F "files=@data/promotions.csv" -F "files=@data/transactions.xml" \
  -F "files=@data/transfers.csv"
```

People files load first automatically — the other entities resolve against them.

Expected: 1002 people (1001 distinct entities), 236 promotions, 189 transactions
(4 orphans, 1 duplicate), 614 transfers (15 null, 81 flagged).

### Tests

```bash
cd backend && python -m pytest tests -q
```

36 tests. Ingestion and conforming run against the real files with no database;
the analysis tests skip cleanly if `DATABASE_URL` is unset.

### Notebooks

```bash
pip install pandas matplotlib scipy statsmodels
jupyter notebook diagnostics/
```

`data_diagnostics.ipynb` needs nothing beyond the standard library. Run
`data_cleaning.ipynb` before `data_analysis.ipynb` — the latter reads its output.

---

## 5. Consuming the data

Two web views, plus the API directly.

**Non-technical view** — findings in plain language, rewritten after every upload;
client demographics; best sellers and store performance; campaign response rates
with sample sizes attached; a ranked call-back list; transfer activity and a
cross-sell audience. Upload files and every figure recalculates.

**Technical view** — flagged records by category (framed as retained, not broken),
load history, the quarantine queue with original payloads, and a console for
sending requests to any endpoint.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/uploads` | Upload files; `mode=append\|replace` |
| GET | `/analysis` | Full report plus headlines |
| GET | `/analysis/{section}` | One section, so a panel can refresh alone |
| GET | `/analysis/sections` | Section names |
| GET | `/loads` | Upload history |
| GET | `/loads/quarantine` | Rejected rows with reasons |
| GET | `/loads/notes` | Data-quality notes, e.g. detected outages |
| GET | `/health` | Liveness and database connectivity |

Interactive docs at `/docs`.

---

## 6. Deployment

Frontend and API deploy together from this repo. The API runs as a Python
serverless function; the frontend is served as static files.

```
vercel.json          routes /api/* to the function, everything else to frontend/
api/index.py         Vercel entry point — mounts the backend at /api
api/requirements.txt
```

1. **Import the repo** at vercel.com/new. Framework preset **Other**, root
   directory `./` — not `frontend`. `vercel.json` handles routing.
2. **Set `DATABASE_URL`** in Project Settings → Environment Variables, using the
   Supabase **transaction pooler** (port 6543). Serverless opens a connection per
   request, which is what that pooler is for.
3. **Set the production branch** in Settings → Environments → Production → Branch
   Tracking. Vercel defaults to `main`; this work lives on `venmito-solution`. The
   branch must have been deployed at least once before the field will accept it.
4. **Verify** `https://<your-app>.vercel.app/api/health` before the main page — it
   isolates the API from the static routing.

Local development is unchanged. The frontend picks its API base automatically:
`localhost:8000` on localhost, same-origin `/api` when deployed.

### Why the database is configured differently when deployed

Each request runs in a fresh function, so a connection pool would hold connections
that are never reused and would exhaust Supabase's limit. `api/index.py` sets
`VENMITO_SERVERLESS=1`, which switches the engine to `NullPool` — one connection
per request, closed at the end.

### Limits of this deployment

- **Cold starts** — the first request after idle takes a few seconds.
- **4.5 MB upload cap** on serverless request bodies. The sample files are far
  smaller; a large production file would need a different path.
- **30 second timeout** — a people upload re-merges the whole population, which
  takes about two seconds today but grows with the data.

For anything beyond a prototype, run the API on a host with a persistent process
(Render, Railway, Fly) and keep only the frontend on Vercel.

---

## 7. Layout

```
diagnostics/     the notebooks — understanding the data before building
data/            the five source files, unmodified
backend/
  app/
    ingestion/   reading files; one adapter per format
    conform/     normalising, entity resolution, flag rules — no database
    db/          engine and all SQL writes
    analysis/    read-only aggregation and the report
    api/routes/  uploads, loads, analysis, health
  migrations/    schema, in order
  tests/         36 tests
frontend/        plain JS; both views
api/             Vercel entry point
```

## 8. Known limits

- Flagged rows are categorised but nothing retries automatically; re-upload a
  corrected file to resolve them.
- `person_identifiers` enforces one person per phone. True for this data; a shared
  household number would be rejected.
- The frontend targets laptop widths (1024–1920px). It is not designed for tablet
  or phone.
- No authentication — the tool is internal, and the security boundary is the
  connection string.
