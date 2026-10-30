# ADR 0005: Host on Render + Supabase (supersedes the Railway parts of 0001 and 0004)

Date: 2026-10-30 · Status: Accepted

## Context
The spec named Railway, but no Railway project was ever connected. The owner connected Render to GitHub and asked for the better, more efficient option.

## Decision
- Web app on **Render**, one Docker service per environment, defined in `render.yaml` (dev from `dev` first; production from `main` later, with explicit approval).
- **Supabase** keeps Postgres, Auth (owner login) and Storage (dish images), as in ADR 0004. Render Postgres is not used: the app needs Supabase for Auth and Storage anyway, and Render's free Postgres expires after 30 days.
- Migrations run on container start via `python -m app.migrate` (free plan has no pre-deploy hook).

## Consequences
+ One web service plus one Supabase project per environment; deploys on push.
− Free plan sleeps when idle (about a minute to wake); upgrade before real customers.
− `DATABASE_URL` must use Supabase's session pooler (IPv4).
