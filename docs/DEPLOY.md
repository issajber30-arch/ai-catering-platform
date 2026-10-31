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

## Production
Production is a second Render service, **`caterking`**, defined in `render.yaml`. It deploys from **`main`** on the free plan for now (sleeps when idle; upgrade to Starter, about $7/month, for always-on). It has its **own** Supabase project, `caterking-prod` (`vowkkljvaymxzhkllvxl`, Ireland), so real orders never mix with test data.

1. **Release:** merge a PR from `dev` into `main`. Only merge what you've already checked on the dev site.
2. **Render:** open the Blueprint and click **Sync**. Render proposes the new `caterking` service and asks for its secrets:
   - `DATABASE_URL`: the line in `~/Desktop/caterking-PROD-DATABASE_URL.txt`. Delete that file afterwards.
   - `SUPABASE_URL`: `https://vowkkljvaymxzhkllvxl.supabase.co`
   - `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`: from the `caterking-prod` project, under Project Settings → API.
   - `ANTHROPIC_API_KEY`: a fresh key with a monthly spend limit.
3. **Owner login:** in `caterking-prod`, go to Authentication → Users and add your user. Claude then grants it the admin role.
4. **Menu:** add the real menu, kitchen address, time slots and serving rules in the production admin.
5. **Check:** run `scripts/smoke_api.sh https://<production-url>`, then place one order and cancel it from the admin.
