# Publishing this plugin as a TRMNL recipe

Order matters: **Unlisted first, Public second.** A recipe that is Public can
only be made Unlisted again by emailing the TRMNL team, so the cheap reversible
step goes first and the demo video is recorded while the endpoint is already
live.

## What you get, what it costs

| | |
|---|---|
| Install path | One click from `trmnl.com/recipes`; installers get automatic updates from your master plugin |
| Users need | Nothing: no UUID, no fork, no cron, no secret |
| You need | The `gh-pages` JSON endpoint running, an MIT license (present), OMIE cited in the plugin description (present) |
| Review | Unlisted skips moderation. Public is manually reviewed by TRMNL |
| Reversibility | Public -> Unlisted requires contacting `team@trmnl.com` |

## Precondition: publish the polling plugin, not your own

**Do not publish plugin `485848`.** That is the Webhook plugin your device pulls
from. Recipe installers would receive the webhook strategy and each need their
own cron and secret -- exactly the friction the recipe is supposed to remove.

Create a **second** private plugin:

1. TRMNL -> **Plugins** -> **Private Plugin** -> Add.
2. **Strategy** = `Polling`, **Polling verb** = `GET`, **Polling URL** =
   `https://pmagnomuller.github.io/trmnl-omie/prices.json`,
   **Refresh interval** = `15`. Reference values:
   [`polling/settings.yml.example`](polling/settings.yml.example).
3. Paste the three layouts from [`src/`](src/) into the Markup editor.
4. Name it `OMIE PT`, description as in
   [`src/settings.yml`](src/settings.yml) (it cites OMIE).
5. Copy its plugin ID from the edit-page URL: `trmnl.com/plugins/<ID>/edit`.

Your existing webhook plugin keeps running untouched.

Before submitting, confirm the endpoint answers:

```bash
curl -s https://pmagnomuller.github.io/trmnl-omie/prices.json | head -c 200
```

Empty or 404 -> run the `Publish prices.json for polling` workflow manually once
and enable **Settings -> Pages -> Deploy from a branch -> `gh-pages` / (root)**.

## Step 1 -- publish Unlisted

1. Open the polling plugin -> settings -> the icon beside **"Publish plugin?"**.
2. Submit. Unlisted skips moderation: you get a shareable recipe link
   immediately.
3. Sanity-check by installing it on a second device, or hand the link to one
   person and watch them install it without help.

Unlisted is the right resting place until the demo video exists. Nothing about
the recipe is public, but the flow is real and testable.

## Step 2 -- promote to Public

Email `team@trmnl.com` with subject:

```
Public plugin submission - OMIE PT
```

Body:

```
Plugin name: OMIE PT
Plugin ID: <polling plugin ID>
Owner email: <your TRMNL account email>

What it does:
Iberian day-ahead electricity prices from OMIE (PT/ES) on an e-ink display:
current 15-minute slot, today's min/avg/max, the cheapest upcoming hour, and a
sparkline of the next 8 hours. Refreshes every 15 minutes from a static JSON
endpoint built by a GitHub Actions cron in the linked repo.

Why public rather than private:
It is the only OMIE day-ahead display on the marketplace, and OMIE prices drive
real decisions in Portugal and Spain -- when to run the dishwasher, the washing
machine, or charge an EV. The data is public and free, needs no credentials and
no per-user setup, so it is useful to anyone in Iberia with a TRMNL, not just to
me. Polling means installers hold no secret and nothing breaks when they unplug
it.

Repo (MIT): https://github.com/pmagnomuller/trmnl-omie
Data source: OMIE (omie.es), cited in the plugin description.

Testing:
No login, no credentials, no form fields. Install the recipe and it renders
within one refresh cycle. The exact JSON it polls is public:
https://pmagnomuller.github.io/trmnl-omie/prices.json

Video demonstration: <link>

Promotion plans:
Writeup on pedro-muller.com (homelab/energy series), the sibling OpenClaw skill
(repos omie-energy, ostrom-energy, tibber-energy) and its README, plus the
TRMNL developer Discord #flex channel before submission.
```

Attach a **video demonstrating installation from scratch** (see script below).
The page asks for test credentials; there are none -- say so explicitly.

## Step 3 -- record the demo video

Two minutes, no audio needed, screen capture only. Record the **Unlisted**
install path; the flow is identical once public.

| # | Shot | Must be visible |
|---|---|---|
| 1 | `trmnl.com/recipes` -> your recipe | Recipe name, install button |
| 2 | Click **Install** | Completing without asking for a URL, key or field |
| 3 | Device playlist -> add the plugin | The recipe appears as a normal plugin |
| 4 | Wait one refresh, then the display | Price, slot label, sparkline, "cheapest next" |
| 5 | Optional: the `gh-pages` JSON in a browser | Same numbers, proving the data path |

Trim dead time between 4 and 5. Upload unlisted to YouTube, put the link in the
email.

## After publishing

- **Updates.** Editing the master plugin's markup pushes to every installer.
  Breaking a variable name in `src/*.liquid` breaks every install, so treat
  template keys as a public interface: add, do not rename.
- **The endpoint is load-bearing.** If `publish-json.yml` breaks, every install
  freezes on its last payload. The webhook path is unaffected.
- **Fork.** Forking needs the Developer edition add-on and stops automatic
  updates. MIT covers it.
- **Money.** TRMNL has said it pays developers for marketplace plugins. Confirm
  the current terms with `team@trmnl.com` in the same email rather than
  assuming a payout.
