# Launching GAJ

A step-by-step guide to putting GAJ online at your own domain, with
HTTPS, a real database, real email, and forwarding addresses that work.
Plan about 2 hours. Do the steps in order: each one gives you a value
the next one needs.

## What it costs

| What | Service | Cost |
|---|---|---|
| Domain name | Cloudflare Registrar | about $10–12 a year for a .com (sold at cost) |
| Running the app | Render, $7/month instance | $7 a month (the free instance sleeps after 15 minutes idle and takes about a minute to wake up, which is fine for testing but not for real users) |
| Database | Neon Free | $0 (1 GB storage, no card needed) |
| Sending email (password resets) | Resend Free | $0 (100 emails a day, 3,000 a month) |
| Receiving email (forwarding addresses) | Cloudflare Email Routing | $0 |
| Log-in codes by text (optional) | Twilio Verify | about 6 cents per successful code in the US ($0.05 + about $0.008 per text); free trial to start |

About **$7 a month plus the domain**, plus a few cents per phone log-in
if you turn on text codes.

Keep a private note open while you work. You'll collect a few values,
such as the database address and the email API key. Never put them in
GitHub.

---

## 1. Put the code on `main`

Render deploys the `main` branch. Merge the open pull requests on
GitHub so `main` has everything, including this file.

## 2. Buy a domain (Cloudflare)

1. Create an account at cloudflare.com.
2. Go to **Domain Registration → Register Domains** and search for a
   name. Short names like `getajob.com` are taken; try variations such as
   `gajapp.com` or `getajobapp.com` and pick one that's available.
3. Buy it. The domain then shows in your Cloudflare dashboard, which
   also manages its DNS.

**Write down:** `yourdomain.com`

## 3. Create the database (Neon)

1. Sign up at neon.com (the Free plan needs no card).
2. Create a project named `gaj`, in a **US East** region (close to
   Render's servers, so pages load fast).
3. Click **Connect** and copy the connection string. It looks like
   `postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require`.

**Write down:** `DATABASE_URL` = that string

## 4. Set up sending email (Resend)

1. Sign up at resend.com.
2. Go to **Domains → Add Domain** and enter `yourdomain.com`.
3. Resend shows a few DNS records. Add each one in **Cloudflare →
   yourdomain.com → DNS → Records**, exactly as shown. Then click
   **Verify** in Resend; it can take a few minutes.
4. Go to **API Keys → Create API Key** with permission "Sending access".

**Write down:** `MAIL_PASSWORD` = the API key (it starts with `re_`)

## 5. Start the app (Render)

1. Sign up at render.com with your GitHub account.
2. Go to **New → Blueprint**, pick the `career-project` repository and
   branch `main`. Render reads `render.yaml` and lists one web service,
   **gaj**.
3. Render asks for the values marked `sync: false`. Fill them in:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | from step 3 |
   | `MAIL_PASSWORD` | from step 4 |
   | `MAIL_FROM` | `GAJ <no-reply@yourdomain.com>` |
   | `CONTACT_EMAIL` | `hello@yourdomain.com` (set up in step 7) |
   | `INBOUND_DOMAIN` | `yourdomain.com` |
   | `BETA_INVITE_CODE` | a code for your testers, e.g. `owls-beta`, or empty for open sign-up |
   | `FEEDBACK_URL` | a Google Form link (step 9), or empty for now |

   `SECRET_KEY` and `INBOUND_WEBHOOK_SECRET` are generated for you.
4. Click **Apply**. Render installs packages, runs the database
   migrations, adds the sample jobs, and starts GAJ.
5. Open `https://gaj-xxxx.onrender.com/healthz`. It should show
   `{"status": "ok"}`.

If the deploy fails, open the service's **Logs**. If GAJ refuses
to start, the log names the setting that's wrong.

**Write down:** `INBOUND_WEBHOOK_SECRET`. In Render, open
**gaj → Environment** and click to reveal it.

## 6. Use your domain (Render + Cloudflare)

1. In Render, go to **gaj → Settings → Custom Domains** and add
   `yourdomain.com` and `www.yourdomain.com`.
2. Render shows the DNS records to create. Add them in **Cloudflare →
   DNS → Records**. Set **Proxy status** to **DNS only** (grey cloud)
   so Render can issue the HTTPS certificate.
3. Wait for Render to show both domains as **Verified** with a
   certificate. This usually takes minutes, and can take up to an hour.
4. Open `https://yourdomain.com`. You should see GAJ with the
   padlock.

## 7. Receive email (Cloudflare Email Routing)

This makes the `gaj-...@yourdomain.com` addresses work. It also gives
you `hello@yourdomain.com` delivered to your own Gmail.

1. In **Cloudflare → yourdomain.com → Email → Email Routing**, click
   **Enable**. Let Cloudflare add its MX and TXT records.
2. Under **Destination addresses**, add your Gmail and confirm the email
   Cloudflare sends you.
3. Under **Routing rules**, create a custom address: `hello@yourdomain.com`
   → **Send to an email** → your Gmail.
4. Create the Worker:
   1. Go to **Workers & Pages → Create → Worker**, name it
      `gaj-email`, and deploy the starter.
   2. Click **Edit code**, replace everything with the contents of
      `deploy/cloudflare-email-worker.js`, and click **Deploy**.
   3. Go to **Settings → Variables and Secrets** and add:
      - `JOBTRACK_URL` = `https://yourdomain.com/inbound/email`
      - `INBOUND_SECRET` = the `INBOUND_WEBHOOK_SECRET` from Render
        (choose type **Secret**)
5. Back in **Email Routing → Routing rules**, edit **Catch-all address**:
   set the action to **Send to a Worker**, choose `gaj-email`, and
   enable it.

The specific `hello@` rule wins over the catch-all, so only other
addresses (the `gaj-` ones) go to GAJ.

## 7b. Text-message log-in codes (Twilio, optional)

Skip this step and phone log-in is simply hidden on the live site.
Everything else works without it.

1. Sign up at twilio.com (the free trial needs no card).
2. In the Console, go to **Verify → Services → Create new**, name it
   `GAJ`, tick **SMS**, and create it.
3. Copy three values into Render (**gaj → Environment**):
   - `TWILIO_ACCOUNT_SID` (on the Console home page, starts with `AC`)
   - `TWILIO_AUTH_TOKEN` (on the same page; keep it secret)
   - `TWILIO_VERIFY_SERVICE_SID` (on the Verify service, starts with `VA`)
4. Trial accounts can only text numbers you've verified in Twilio.
   Upgrade the account before inviting testers.

GAJ only texts US and Canadian numbers, and limits how many codes one
number can get. That protects you from bots that rack up texting bills.

## 8. Test everything on the live site

Use a test account first, then your real one.

- [ ] `https://yourdomain.com` loads with the padlock, and `http://` redirects to `https://`
- [ ] Create an account (with the invite code, if you set one), then log in
- [ ] **Forgot password** sends a real email, and its link opens a `https://yourdomain.com/...` page
- [ ] Inbox: add the address in Gmail as a forwarding address. The confirmation code appears in GAJ's Inbox within a minute
- [ ] Add an application for a company, then forward one of that company's emails to your address. The status updates
- [ ] Email `hello@yourdomain.com` from another account. It arrives in your Gmail
- [ ] If you set up Twilio: Account → add your phone, enter the texted code, log out, then log in with **Phone**
- [ ] Account: **Download my data** works
- [ ] Delete the test account
- [ ] The Privacy and Terms pages show your contact email

## 9. Invite beta testers

1. Make a short Google Form: what did you try, what broke, what's
   missing, and would you keep using it? Put its link in `FEEDBACK_URL`
   in Render. Saving the change redeploys the app.
2. Invite 10–20 people who are job hunting right now (classmates,
   friends from work). Send them the link, the invite code, and
   one line on what GAJ does.
3. Read the feedback weekly and fix the most common problem first.

## Every update after launch

Merge a pull request into `main` and Render deploys it. It runs any
new migrations first (`preDeployCommand` in `render.yaml`), and the
site stays up during the switch.

## Good to know

- **Render free instance:** to test for $0, change `plan: starter` to
  `plan: free` in `render.yaml`. The free instance doesn't run
  `preDeployCommand`, so also change `buildCommand` to
  `pip install -r requirements.txt && flask --app app init-db && flask --app app seed`.
  Expect the site to sleep after 15 idle minutes.
- **Backups:** Neon keeps a short history you can restore from (the
  window depends on the plan). For your own copy, download your data
  from Account now and then.
- **Watching the site:** Render checks `/healthz` and restarts the app
  if it stops answering. A free UptimeRobot monitor on the same URL
  can email you when the site goes down.
