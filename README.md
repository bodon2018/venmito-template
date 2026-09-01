# Venmito

**Herminio Bodon** · bodon2018@gmail.com

Venmito came to us with a problem of fragmented data spread across five source files in four formats. I analyzed the data, developed a set of recommendations, and implemented a solution that consolidated their fragmented data into a single PostgreSQL database, with insights derived from it and served through two web views, one for non-technical staff and one for the technical team.

Tools used for analysis, design, and implementation: VS Code, Python, Jupyter Notebook, pen and paper for sketching system design, Github, and AI-assisted development and frontend design via Claude Design and Claude AI (Sonnet and Opus -Low Effort).

Recommendations: venmito-template/recommendations/recommendationsVenmito.pdf

Live Solution: https://venmito-hb-interview.vercel.app/

**An access code is required to enter the web app.** The tool holds client
names, emails, phone numbers and dates of birth, so it is not open to the web.
Any one of these codes works, and a code lasts twelve hours per browser:

    WTZQ-HHMM
    FSF8-HCLJ
    EXWX-NP34
    EUEE-66QQ
    9KAF-QGVU
    V6ZA-TMHW
    ZVPT-CHLM
    MAYH-QC3F
    G5XN-C4PS
    HDWX-PLUL

The gate is enforced on the API, not only on the page — opening an endpoint or
a deep link directly returns `401` until a code has been entered. Rotate the
codes by changing `ACCESS_CODES_RAW`; removing a code immediately invalidates
every token issued from it.


---

## 1. Diagnostics (recommendations/diagnostics)

I first reviewed the data files manually, then constructed a Jupyter notebook to confirm the identified problems. The notebooks are in the `recommendations/diagnostics/` folder, and system design decisions are based on the findings from these analyses.


| Notebook | What it does |
|---|---|
| `data_diagnostics.ipynb` | Identifies problems found in the raw files. Each check prints PASS or FAIL, where FAIL means the defect was confirmed. Pure standard library. |
| `data_cleaning.ipynb` | Addresses the six findings. I decided not to delete questionable data but to flag it instead. This decision is based on the assumption that, as a member of the technical team at Venmito, I would want to investigate any anomalies rather than simply delete data that does not conform to the rest. |
| `data_analysis.ipynb` | Here I conducted exploratory analysis and visualizations, plus statistical tests of the patterns found. This is meant to provide Venmito with insights to help them better understand their clientele and transaction trends. |

The results from my analysis are not included in the repository, but you would get the same results by running the notebooks in listed order (diagnostics → cleaning → analysis). The recommendations are summarized in the PDF file `recommendations/recommendationsVenmito.pdf`, which is also included in this repository. Additionally, figures folder contains the visualizations in the PDF as well as other visualizations that are important to the analysis but were not included in the PDF.

### Identified problems in the provided data (recommendations/raw_data)

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


---

## 2. Solution design

I went with a modular design in which each stage is isolated: data is loaded, inconsistencies are resolved, and the data is organized into a unified format. Data is then persisted in a PostgreSQL database and made available for different purposes. As part of the requirements, the system must support non-technical team members; accordingly, a high-level analysis module is provided so the system can analyze data on their behalf and present it in an easy-to-digest UI. Technical team members, by contrast, have direct access to the server and database and can use the data for other services (e.g., training models).

```
ingestion  ->  conforming  ->  persistence  ->  analysis
```

- **`backend/app/ingestion/`** — one reader per format. Format and entity are
  detected from file *content*, not the filename, because a filename cannot be
  trusted on an upload endpoint. Nothing is cleaned here; a negative price is read
  faithfully and dealt with later, where the decision is visible.
- **`backend/app/conform/`** — normalisation, entity resolution, and the flag
  rules. 
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
| Database | Supabase (Postgres) | The data is relational, and integrity is what the id-998 collision violated |
| API | FastAPI + SQLAlchemy Core | Typed request handling; raw SQL where the work belongs in the database |
| Validation | Pydantic / pydantic-settings | Schema at the boundary, policies in config |
| Frontend | Plain JavaScript, ES modules | No build step. The design has no class system and no framework idioms, so a framework would add weight and at it is not needed at this stage |
| Charts | None — inline SVG | Datasets are 5–28 points. `charts.js` computes polyline coordinates and bar widths directly; a chart library would bring its own opinions about axes and colour |
| Notebooks | Standard library, then pandas | Diagnostics use no dependencies so the parsing can be audited; cleaning and analysis use pandas, matplotlib, scipy, statsmodels |
| Hosting | Vercel | Frontend and API deploy together from one repo|

---

## 4. Running it (Mac — see the appendix for Linux)

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
  -F "files=@recommendations/raw_data/people.json" \
  -F "files=@recommendations/raw_data/people.yml" \
  -F "files=@recommendations/raw_data/promotions.csv" \
  -F "files=@recommendations/raw_data/transactions.xml" \
  -F "files=@recommendations/raw_data/transfers.csv"
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
jupyter notebook recommendations/diagnostics/
```

`data_diagnostics.ipynb` needs nothing beyond the standard library. Run
`data_cleaning.ipynb` before `data_analysis.ipynb` — the latter reads its output
from `recommendations/data_clean/`.

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
recommendations/
  raw_data/      the five source files exactly as provided, unmodified
  diagnostics/   the notebooks — understanding the data before building
  data_clean/    conformed CSVs written by data_cleaning.ipynb (git-ignored)
backend/
  app/
    ingestion/   reading files; one adapter per format
    conform/     normalising, entity resolution, flag rules — no database
    db/          engine and all SQL writes
    analysis/    read-only aggregation and the report
    api/routes/  uploads, loads, analysis, health
  migrations/    schema, in order
  tests/         48 tests
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

---

## 9. To fix / implement next

### For technical team members — controlling the database from the web app

The technical view currently reads: it shows flagged records, load history, the
quarantine queue, and can send requests to any endpoint. It does not let anyone
write to or query the database freely, and that is a deliberate omission for now.

**The app has no authentication.** It is served from a public URL, so a SQL
console or a delete button would be available to anyone who found the address.
Shipping such features would be unsafe. Supporting it properly needs,
in order:

1. **An access gate.** A shared code exchanged for a signed token, enforced by
   middleware on every API route — not only on the page, since the endpoints are
   reachable directly. 
2. **A read-only database role.** A separate Postgres role with `SELECT` only on
   `clean` and `ops`, plus a statement timeout and a row cap. Enforcement belongs
   in the database, not in code that scans SQL strings for dangerous keywords —
   that check is trivially bypassed. 
3. **Soft delete rather than hard delete.** Removing questionable records should
   set an `excluded_by_user` flag with who and why, not issue a `DELETE`. The
   analysis layer already filters on flags, so the practical outcome is identical
   — the records leave the figures — while the evidence survives. This also keeps
   the choice consistent with the rest of the system, where nothing is destroyed.


### For non-technical team members — interactive and forward-looking

The current view answers "what happened". Two additions would let it answer
"what if":

1. **Interactive visualizations.** Hover for exact values, filter by country,
   store or date range, and click through from a chart to the underlying rows.
   The charts are already computed from live data, so this is a presentation
   change rather than a pipeline one.
2. **Scenario projection.** Let staff move the inputs and see the outputs move:
   what revenue looks like if promotion acceptance rises a few points, what the
   transfer network looks like if volume shifts, what happens to store figures if
   payment behaviour changes. That turns the tool from a report into something
   the business can plan against.

Nonetheless the current data does not support
prediction. Any projection built today would be arithmetic
on assumptions the user supplies, and should be labelled as such rather than
presented as a forecast. Real forecasting needs more data — and variables the
source files do not contain, such as offer terms, discount depth and contact
history.

---

## 10. Scaling it

The current deployment is sized for a prototype: one Postgres database, an API
running as a serverless function, and files uploaded through a browser. For scaling the solution we would have to address the follwoing:


### Priorities

| Limit | Where it becomes a problem |
|---|---|
| Vercel's 30s function timeout | A people upload re-merges the whole population on every file. Two seconds today; linear in the number of people. |
| 4.5 MB request body | Anything larger than a sample file cannot be uploaded at all. |
| Cold starts | First request after idle takes seconds, and `NullPool` opens a fresh connection every time. |
| Report computed per request | `GET /analysis` runs ~25 aggregate queries on every page load. |
| One database, one role | No isolation between ingestion writes and analyst reads. |

### The fixes, in the order they would be needed

**1. Containerize the API and move it off serverless.** A `Dockerfile` around
the existing FastAPI app, deployed to Cloud Run, ECS or Fly. This removes
the timeout, the body-size cap and the cold starts, and restores a real
connection pool — the serverless `NullPool` branch in `db/session.py` exists
only because of the current host. Nothing in the application code changes.

**2. Make ingestion asynchronous.** Upload goes to object storage (S3 or
Supabase Storage) and returns immediately with a load id; a worker picks the
file up from a queue and runs the same `ingestion` → `conform` → persist
pipeline. The stages are already separated and database-free up to the write,
so this is a change in how they are invoked, not in what they do. The frontend
polls `/loads/{id}` for status. This is what makes multi-gigabyte files
possible.

**3. Merge people incrementally.** Today a people upload rebuilds the entire
population from `raw` because a new file can change the outcome for ids it does
not contain. That is correct but O(all people) per upload. At scale it becomes
a scoped re-merge — only the ids the new file touches, plus any entity whose
natural keys it collides with — with a full rebuild available as a background
job.

**4. Precompute the analysis.** The aggregates are read-only and change only on
ingest, so they belong in materialized views refreshed at the end of a load,
with the API reading the view instead of recomputing. Add a cache keyed on the
latest load id, so repeat page loads are free and an upload invalidates
naturally.

**5. Split the database roles and reads.** A writer role for ingestion, a
read-only role for analysis and any future SQL console, and a read replica once
analyst queries start competing with ingest. 

**6. Operational maturity.** Migrations move from hand-run SQL files to Alembic
so they version and roll back.


### What would not need to change

The four-stage split is the reason most of the above is straightforward.
`ingestion` and `conform` never touch the database, so they run unchanged in a
worker, a batch job or a test. All SQL writes live in one repository module, so
swapping the persistence target does not touch business logic. The entity
resolution policies are configuration, so they can differ per environment
without a code change. The frontend is static files and already CDN-friendly.

---

## Appendix — running on Linux

Same steps as section 4, with three differences. Verified commands are given in
full so this section stands alone.

### 1. A virtual environment is required

Most current distributions (Debian, Ubuntu, Fedora) mark the system Python as
externally managed, so `pip install` outside a virtual environment fails with
`error: externally-managed-environment`.

```bash
sudo apt install python3-venv python3-pip   # Debian/Ubuntu
sudo dnf install python3-pip                # Fedora
```

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Deactivate with `deactivate`. Open a second terminal for the frontend, and
re-activate there if you run backend commands from it.

### 2. Invoke tools through `python3 -m`

`pip install --user` puts executables in `~/.local/bin`, which is not always on
`PATH`. Calling the module avoids the problem entirely:

```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

```bash
python3 -m pytest tests -q
```

```bash
python3 -m http.server 5173      # from frontend/, in a second terminal
```

### 3. Check the Python version

The code needs 3.11 or newer.

```bash
python3 --version
```

If the distribution ships something older, install a newer interpreter
(`sudo apt install python3.11` on Debian/Ubuntu, or use `pyenv`) and create the
virtual environment with it: `python3.11 -m venv .venv`.

### Everything else is identical

```bash
cp .env.example .env        # then edit DATABASE_URL
```

`psycopg2-binary` ships manylinux wheels, so no compiler or `libpq-dev` is
needed. `cp`, `curl` and `python3 -m http.server` behave the same as on macOS,
and nothing in the code is platform-specific.

Load the data and check health exactly as in section 4:

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/uploads \
  -F "files=@recommendations/raw_data/people.json" \
  -F "files=@recommendations/raw_data/people.yml" \
  -F "files=@recommendations/raw_data/promotions.csv" \
  -F "files=@recommendations/raw_data/transactions.xml" \
  -F "files=@recommendations/raw_data/transfers.csv"
```

### Notebooks

```bash
python3 -m pip install pandas matplotlib scipy statsmodels jupyter
python3 -m jupyter notebook recommendations/diagnostics/
```
