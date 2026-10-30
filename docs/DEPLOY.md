# Deploying the CaterKing dev site (Render + Supabase)

The site runs on **Render** (from `render.yaml`) with **Supabase** for the database, the owner login and dish images. These steps are for the owner: they involve accounts and secrets, so only you can do them. Secrets go only into the Supabase and Render dashboards, never into chat or git.

## 1. Supabase project (free)
1. Go to https://supabase.com, sign in and click **New project**.
   - Name: `caterking-dev`
   - Region: **Central EU (Frankfurt)**, the closest to Israel
   - Database password: generate one and keep it in your password manager.
2. Under **Project Settings → Data API** (or **API**), note the **Project URL** and the **anon** and **service_role** keys.
3. Click **Connect** at the top of the project and choose **Session pooler**. Copy that connection string.
   - Render needs the pooler: Supabase's direct host is IPv6-only.
   - Change the start from `postgresql://` to `postgresql+psycopg://` and put your database password in place of `[YOUR-PASSWORD]`. The result looks like:
     `postgresql+psycopg://postgres.<ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`
4. In **Storage**, create a bucket named `dish-images` and set it to **Public**.
5. **Create your owner login.**
   1. Go to **Authentication → Users → Add user** and enter your email and a password.
   2. Make that user an admin. Open the **SQL editor** and run this with your email:
      ```sql
      update auth.users
      set raw_app_meta_data = raw_app_meta_data || '{"role": "admin"}'
      where email = 'you@example.com';
      ```

## 2. Render web service (free)
1. Go to https://dashboard.render.com and choose **New → Blueprint**.
2. Pick the repo `issajber30-arch/ai-catering-platform`. Render finds `render.yaml` and proposes the service `caterking-dev`.
3. Render asks for the secret values. Paste them in:
   - `DATABASE_URL`: the session-pooler string from step 1.3
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`: from step 1.2
   - `ANTHROPIC_API_KEY`: a **new** key from https://console.anthropic.com. Set a monthly spend limit there too.
4. Click **Apply**. The first build takes a few minutes.
   - In the logs, look for `applied 20261029000001_catalog.sql` and the other migrations, then `Uvicorn running`.
5. Open `https://caterking-dev.onrender.com/health` (or the URL Render shows, if that name was taken). It should answer `{"status":"ok","env":"development"}`.

The service deploys from the **`dev`** branch, so merged PRs go live automatically. On the free plan the site sleeps after about 15 minutes idle, and the first visit then takes about a minute.

## 3. Check it
- Customer site: `/customer/`
- Owner dashboard: `/admin/`. Log in with the user from step 1.5.
- Regression check from your Mac: `scripts/smoke_api.sh https://caterking-dev.onrender.com`. Its order checks need one per-tray dish and one pickup slot. Claude can seed matching demo data once the site is up, or adapt the IDs.

Once the site is up, add your menu, the kitchen address in the admin Settings tab, and serving rules. They're needed for real quotes.

## Production (later)
Production gets a second Render service from `main` and a separate Supabase project. Set it up only when you're ready, and only after the dev site has been checked end to end.
