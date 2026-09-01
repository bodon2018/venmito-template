# Venmito backend

FastAPI + Supabase (Postgres). Ingests the four source formats, conforms them
into one schema, and persists the result with real integrity constraints.

## Layout

```
backend/
  app/
    ingestion/       reading files -- one adapter per format, no cleaning
      detect.py      format + entity detection from content, not filename
      readers.py     JSON / YAML / CSV / XML readers -> plain records
    conform/         matching + conforming -- no database access
      normalize.py   field-level rules (id, name, city, dob)
      people.py      outer-join the two people sources, report conflicts
      identity.py    entity resolution + natural-key lookups
      flags.py       price recomputation, duplicate + risk rules
      pipeline.py    per-entity conform steps
    db/
      session.py     engine, one transaction per upload
      repository.py  all SQL writes (upserts)
    services/
      ingest_service.py   detect -> read -> raw -> conform -> write
    api/routes/      uploads, loads, health
  migrations/
    0001_init.sql    raw / clean / ops schemas
  tests/             22 tests, no database required
```

The split matters: `ingestion` and `conform` never touch the database, which
is why the whole pipeline is testable offline.

## Setup

1. Create a Supabase project.
2. Run `migrations/0001_init.sql` in the Supabase SQL editor.
3. Copy `.env.example` to `.env` and fill in `DATABASE_URL`
   (Project Settings -> Database -> Connection string -> URI, pooled port 6543).

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Interactive docs at http://localhost:8000/docs

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/uploads` | Upload one or more source files (`mode=append\|replace`) |
| GET | `/loads` | Upload history with row counts |
| GET | `/loads/quarantine` | Rows that could not be loaded, with reasons |
| GET | `/loads/notes` | Data-quality notes (e.g. detected outages) |
| GET | `/health` | Liveness + database connectivity |
| GET | `/analysis` | Full report: every section plus headlines |
| GET | `/analysis/headlines` | Plain-language findings for the non-technical view |
| GET | `/analysis/sections` | Section names |
| GET | `/analysis/{name}` | One section, so a panel can refresh alone |

Load the people files first -- the other entities resolve against them. The
endpoint sorts people files ahead of the rest within a single request.

```bash
curl -X POST http://localhost:8000/uploads \
  -F "files=@../data/people.json" -F "files=@../data/people.yml" \
  -F "files=@../data/promotions.csv" -F "files=@../data/transactions.xml" \
  -F "files=@../data/transfers.csv"
```

## Behaviour worth knowing

- **Nothing is deleted.** Defects become flag columns (`needs_review`,
  `is_clean`, `is_duplicate`), so bad rows stay auditable and the transfer
  risk tags remain available as a fraud signal.
- **Upload mode is explicit.** `append` (the default) adds to what is stored;
  `replace` makes the uploaded file the entity's contents, superseding earlier
  loads. Raw history and the audit trail survive a replace either way.
- **Re-uploading identical bytes is a no-op** in append mode, so a double
  click cannot double your data. A `replace` always runs, since it was asked
  for explicitly.
- **Analysis is computed live** from current state -- there is no cache, so a
  fresh `GET /analysis` after an upload always reflects the new data.
- **People are re-merged from `raw` on every people upload**, because merging
  is a whole-population operation -- a new file can change the outcome for ids
  it does not contain.
- **Unresolvable rows go to `ops.quarantine`**, never silently dropped.
- **Policies live in `app/config.py`**, not in code: `PEOPLE_PRECEDENCE`
  decides which file wins a conflict, `DUPLICATE_POLICY` decides how a
  duplicate entity is handled.

## Tests

```bash
python -m pytest tests -q
```

These cover ingestion and conforming end to end against the real files, with
no database connection.
