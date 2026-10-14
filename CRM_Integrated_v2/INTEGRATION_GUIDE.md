# TECHPANDA CRM — Integrated v2 (WhatsApp + Facebook + Call Sync)

Your CRM now contains everything in one project:

| Feature | Where in the CRM | Lead source |
|---|---|---|
| WhatsApp inbox + no-code automations (your latest Whatsapp Chat project) | Sidebar → **WhatsApp Chats**, **WhatsApp Automations** | **WhatsApp** |
| Facebook Lead Ads (your fb_leads app) | Sidebar → **Facebook Leads** | **Facebook** |
| Call recordings from telecaller phones (CRM Call Sync app v1.2) | Lead page + sidebar → **Call Recordings** | — |
| Google Ads number calls + missed-call callbacks | Sidebar → **Missed Calls**, Follow-ups | **Google Call** |

**Google Drive recordings are removed** (Drive folder connect / sync / dashboard). Recordings come only from the
Call Sync app. Old Drive recordings already saved stay playable on the lead page.

```
CRM_Integrated_v2/
├── CRM/                   your CRM with everything integrated (no .env, database, venv or secrets inside)
├── CRMCallSync/           Android Studio project, app v1.2
├── CHANGES.diff           every line changed in your original CRM files
└── INTEGRATION_GUIDE.md   this file
```

---

## 1. Install

1. **Back up** your MySQL database and your `media/` folder.
2. Copy everything inside `CRM_Integrated_v2\CRM\` over your CRM folder (allow replace):
   ```powershell
   robocopy "C:\path\to\CRM_Integrated_v2\CRM" "C:\path\to\your\CRM" /E
   ```
3. **Delete the files that were removed** (robocopy only adds and replaces, it never deletes).
   The old `channels` folder is now `lead_channels`: if it stays, Python picks the wrong `channels` and the
   server won't start. Your channel data in the database is not touched.
   ```powershell
   cd "C:\path\to\your\CRM"
   Remove-Item -Recurse -Force channels
   Remove-Item -Recurse -Force templates\drive
   Remove-Item drive\tests.py, drive\tests_google_drive_complete.py, drive\tests_telecaller_audio_archive.py
   ```
4. Add the new settings to your `.env` (see `.env.example`):
   `WHATSAPP_*`, `FB_*`, and optionally `WHATSAPP_DEFAULT_BRANCH`, `FB_DEFAULT_BRANCH`.
   Copy the WhatsApp values from your old `Whatsapp Chat\.env`.
5. Install and migrate:
   ```powershell
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt        # adds channels, daphne, pillow, djangorestframework
   python manage.py migrate
   python manage.py runserver 8000
   ```
   The start-up line now says `Starting ASGI/Daphne ... development server` — that's correct
   (it serves the WhatsApp live inbox too).

## 2. Bring over your existing WhatsApp data (flows, numbers, chats)

In the **old Whatsapp Chat project** folder:
```powershell
.\venv\Scripts\Activate.ps1
python manage.py dumpdata chat --indent 2 -o whatsapp_data.json
```
Copy `whatsapp_data.json` and the old `media\` folder contents (brochures, avatars, WhatsApp media) into the
CRM folder, then in the **CRM**:
```powershell
python manage.py loaddata whatsapp_data.json
python manage.py sync_whatsapp_leads       # creates CRM leads (source WhatsApp) for the existing chats
```
Then open Django admin → **Chat → Business accounts** → each WhatsApp number → set **Crm branch**
(the branch whose telecallers get that number's new leads).

## 3. Bring over existing Facebook leads (optional)

If the old fb_leads app was in another project: there run `python manage.py dumpdata fb_leads -o fb_data.json`,
then in the CRM:
```powershell
python manage.py loaddata fb_data.json
python manage.py sync_fb_leads --crm-only   # adds them to the CRM as Facebook leads
```
Or just press **Sync from Facebook** on the Facebook Leads page: it pulls every lead from every form on the Page.

## 4. Point Meta to the CRM

Use your public https address (ngrok or `https://crm.techpanda.academy`).

| Meta product | Callback URL | Verify token |
|---|---|---|
| WhatsApp (developers.facebook.com → WhatsApp → Configuration) | `https://YOUR-ADDRESS/webhook/whatsapp/` (unchanged path) | `WHATSAPP_VERIFY_TOKEN` |
| Facebook Page → leadgen (Webhooks → Page) | `https://YOUR-ADDRESS/facebook-leads/webhook/` (the old `/api/webhooks/meta/leads/` also works) | `FB_VERIFY_TOKEN` |

Facebook webhook posts are only accepted with Facebook's signature (`FB_APP_SECRET`). The full Facebook
token / Leads Access setup is unchanged from your fb_leads guide (System User token with `leads_retrieval`,
`pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `pages_manage_ads`, `ads_read`).

---

## How leads are created (rules)

**One lead per phone number** across WhatsApp, Facebook, Google calls, Google Sheets and manual entry
(phone or alternate phone, last 10 digits, any format).

| | New number | Number already a lead |
|---|---|---|
| WhatsApp message | New lead: source **WhatsApp**, channel WhatsApp, status New, name from the WhatsApp profile | Same lead. Source, status, telecaller, branch unchanged. "Started a WhatsApp chat" added to the timeline when a new chat starts |
| Facebook lead | New lead: source **Facebook**, channel Facebook, name / email / course from the form; all answers, form, ad and campaign in the timeline | Same lead: blanks filled (email, course), timeline line added, nothing overwritten |

**Branch → telecaller.** New leads are assigned with your **Lead Setup** branch percentages (same engine as
Google Sheet leads). If there is no branch or the branch's percentages don't add up to 100%, the lead is
**Pending Assignment** (Retry from the Leads page as usual). The branch comes from:

- **WhatsApp:** the WhatsApp number's **Crm branch** → else `WHATSAPP_DEFAULT_BRANCH` → else the branch the student
  types / picks in the flow (variable `branch`, `branch_name`, `location`, `selected_branch` or `preferred_branch`).
- **Facebook:** a form question containing "branch" → a "location" / "city" answer matching a branch →
  a branch name inside the form name (e.g. "Velachery - Data Science") → `FB_DEFAULT_BRANCH`.

**WhatsApp flow answers → lead.** Variables `name` / `full_name` / `student_name` → lead name;
`email` → email; `course` / `course_name` / `selected_course` → Product (course) if the name matches;
branch variables → branch (then auto-assigned). Every answer is written once to the lead's timeline.

**New CRM steps in the flow builder** (palette → **CRM**):
- 🏷️ **Lead Status** — sets any CRM status (Interested, Follow-up, Visit Scheduled …) with status history;
  optional "follow up after N hours" creates a Follow-up for the lead's telecaller.
- 🎧 **Assign Telecaller** — *Branch telecaller* (Lead Setup percentages) or *a specific telecaller*;
  optional "only if the lead has no telecaller yet".
Nothing is sent to the student by these steps; the simulator shows them as an orange "CRM:" line.
If a CRM step fails the bot carries on (logged as `CRM_STEP_FAILED` in the automation log).

## Who sees what

| | Admin | Sales Head | Branch Head | Counselor | Telecaller |
|---|---|---|---|---|---|
| WhatsApp Chats | all chats | chats of leads in their branches | chats of their branch's leads | their / branch leads | chats of their own leads |
| WhatsApp Automations + numbers | ✅ | ✅ | — | — | — |
| Facebook Leads page + Sync | ✅ | ✅ | — | — | — |
| Call Recordings | all | their branches | their branch | their leads | their own |

Telecallers can only message numbers that are their leads. The lead page has **Open WhatsApp chat**, shows the
Facebook form, ad, campaign and all answers, Google Ads calls, and call recordings.

## Call Sync app (unchanged from v1.2)

Build `CRMCallSync` in Android Studio → install on telecaller phones → log in with the CRM URL and the
telecaller's CRM username / password. Details: Missed Calls page, Call Recordings page, lead page cards.

## Production notes

- **One server process** is fine as is. With several worker processes, install `channels-redis` and switch
  `CHANNEL_LAYERS` to Redis (commented example in `config/settings.py`), otherwise live inbox updates only reach
  users on the same process.
- Run with an ASGI server (`daphne config.asgi:application`, or `runserver` for testing). Plain WSGI
  (gunicorn/mod_wsgi) works for everything except live inbox updates (refresh the page instead).
- Keep `private_media/` (call recordings) and `media/` in backups; never expose `private_media/` as a web folder.
- Times are shown in UTC (the CRM's `TIME_ZONE = 'UTC'`), as before.

## Not changed

- The **Configuration → Meta** screen in the CRM was a simulation ("Sync now" only updated a time); it is left as it
  was. The real Facebook connection is the **Facebook Leads** page + `.env` settings above.
- The 34 tests that already failed in your original CRM (Google Sheets tests that need internet, some
  configuration-page tests) still fail the same way; nothing new fails.
