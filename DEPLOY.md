# Deploying to Vercel

Frontend and API deploy together from this repo. The API runs as a Python
serverless function; the frontend is served as static files.

```
vercel.json        routes /api/* to the function, everything else to frontend/
api/index.py       Vercel entry point -- mounts the backend at /api
api/requirements.txt
```

Local development is unchanged: `uvicorn app.main:app` from `backend/` on port
8000, and any static server for `frontend/`. The frontend picks its API base
automatically — `http://localhost:8000` on localhost, `/api` when deployed.

## Steps

1. **Import the repo** at vercel.com/new. Framework preset **Other**, root
   directory `./` (not `frontend`) — `vercel.json` handles the routing.

2. **Set the environment variable** in Project Settings → Environment Variables:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase pooler URI, password included |

   Use the **transaction pooler** (port 6543). Serverless functions open a
   connection per request, which is exactly what that pooler is for.

3. **Set the production branch.** Vercel defaults to `main`. In
   Project Settings → Git → Production Branch, change it to `venmito-solution`,
   or merge that branch into `main`.

4. **Deploy**, then check `https://<your-app>.vercel.app/api/health`. It should
   return `{"status":"ok","database":"reachable"}`.

## Why the backend needs a different database setup when deployed

Every request runs in a fresh function, so a connection pool would hold
connections that are never reused and would exhaust Supabase's limit.
`api/index.py` sets `VENMITO_SERVERLESS=1`, which makes `db/session.py` use
`NullPool` — one connection per request, closed at the end.

## Known limits of this deployment

- **Cold starts.** The first request after idle takes a few seconds while the
  function boots and connects.
- **Upload size.** Vercel caps a serverless request body at 4.5 MB. The sample
  files are far smaller, but a large production file would need a different
  path (upload to storage, then ingest).
- **30 second timeout.** A people upload re-merges the whole population; that
  runs in about two seconds today but would grow with the data.

For anything beyond a prototype, run the API on a host with a persistent
process (Render, Railway, Fly) and keep only the frontend on Vercel.
