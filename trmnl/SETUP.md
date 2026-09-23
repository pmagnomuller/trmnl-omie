# TRMNL Private Plugin — OMIE Portugal 15-min prices

Push day-ahead OMIE prices for Portugal to your TRMNL e-ink display every 15 minutes.

## One-time setup

### 1. Create a Private Plugin

Pick one of two strategies. **Webhook** (below) is what the bundled workflow
uses. **Polling** ([jump](#polling-strategy-no-secret-no-cron)) installs with no
secret, which is what a published recipe should use.

1. In [TRMNL](https://trmnl.com) go to **Plugins** → **Private Plugin**.
2. Set **Strategy** to **Webhook**.
3. Save the plugin so a **Webhook URL** / UUID appears.
4. Copy the UUID from `https://trmnl.com/api/custom_plugins/<UUID>`.

### 2. Paste markup

Open the Markup editor and paste:

| Size | File |
|------|------|
| Full | [`src/full.liquid`](src/full.liquid) |
| Half vertical | [`src/half_vertical.liquid`](src/half_vertical.liquid) |
| Quadrant | [`src/quadrant.liquid`](src/quadrant.liquid) |

### 3. Configure the skill / CI

Local dry-run (prints JSON, no push):

```bash
bash run.sh trmnl --area PT
```

Push once:

```bash
export TRMNL_PLUGIN_UUID="your-uuid-here"
# or put it in ~/.config/omie-energy/config.json
bash run.sh trmnl --area PT --push
```

For automatic updates, add a GitHub Actions secret on this repo:

- Name: `TRMNL_PLUGIN_UUID`
- Value: the plugin UUID

The workflow [`.github/workflows/trmnl-omie.yml`](../.github/workflows/trmnl-omie.yml) runs every 15 minutes and on manual dispatch.

### 4. Playlist

Add the plugin to your device playlist. Any interval covering one cron cycle works — 15–30 minutes is what this setup uses. Day-ahead prices only change when OMIE publishes, but the “current” slot and cheap window labels change every 15 minutes.

## Polling strategy (no secret, no cron)

Use this when you do not want to store a plugin UUID anywhere, or when someone
else installs the plugin as a recipe.

1. Enable the JSON endpoint once: repo **Settings → Pages → Deploy from a
   branch → `gh-pages` / `(root)`**. The workflow
   [`../.github/workflows/publish-json.yml`](../.github/workflows/publish-json.yml)
   creates that branch on its first run (`workflow_dispatch` works immediately).
2. Find the URL that actually answers before copying it anywhere. The branch
   existing is not proof the file is served, and a `<owner>.github.io` address
   is wrong for any account with a custom domain on its user site (every such
   path 301-redirects to the custom domain):

   ```bash
   curl -sL -o /dev/null -w '%{http_code}\n' "https://<pages-host>/trmnl-omie/prices-pt.json"  # want 200
   curl -sL "https://<pages-host>/trmnl-omie/prices-pt.json" | head -c 200                       # want {"area"
   ```

   Follow redirects (`-L`): without it you read a 301 body and mistake it for an
   empty file. Two files are published, `prices-pt.json` and `prices-es.json`.

3. Plugin settings: **Strategy** = `Polling`, **Polling verb** = `GET`,
   **Polling URL** = the URL above, **Refresh interval** = `15`.
4. No fields, no headers, no OAuth. The JSON body is the payload from
   [Payload fields](#payload-fields) verbatim, and the templates read its
   top-level keys.

   **Check this against TRMNL's polling preview before publishing a recipe.**
   The webhook sends `{"merge_variables": {...}}`; polling serves the bare
   object. Which one TRMNL's polling merge expects is not established by this
   repo, so verify it in the plugin preview. If the preview shows no variables,
   set the repository variable `ENVELOPE=1`
   (`gh variable set ENVELOPE -b 1 -R <you>/trmnl-omie`): the workflow then also
   publishes `prices-pt-envelope.json` / `prices-es-envelope.json`, wrapped as
   `{"merge_variables": {...}}`. Point the polling URL at one of those.

Reference copy of the plugin settings for this strategy:
[`polling/settings.yml.example`](polling/settings.yml.example).

Notes:

- Enabling Pages is the step that fails most often, and it is not always about
  the repository: a free plan refuses Pages on a **private** repository (the API
  answers `422: Your current plan does not support GitHub Pages for this
  repository`), and an account-level **custom domain** rewrites every
  `<owner>.github.io/...` URL. Check the current GitHub plan requirements for
  your account rather than assuming either way.
- Any static host works instead -- Cloudflare Pages, Netlify, an existing
  server. Nothing in the plugin depends on GitHub Pages, only on the URL
  answering with the JSON.
- Pages caches; a push to `gh-pages` can take a couple of minutes to show.
  TRMNL caches too, so a stale slot label for one refresh cycle is normal.
  Setting the repository variable `POLLING_URL` makes the deploy workflow
  verify the served payload and fail loudly if it lags.
- The endpoint is public and unauthenticated by design. It contains prices and
  timestamps only.

## Payload fields

| Field | Meaning |
|-------|---------|
| `current.price_label` | EUR/kWh for the active 15-min slot |
| `current.slot_label` | e.g. `13:00–13:15` |
| `today_min_label` / `today_max_label` / `today_avg_label` | Today’s day-ahead stats |
| `cheapest_next.label` | Next cheapest 1h block (default) |
| `upcoming.t` / `upcoming.p` / `upcoming.bars` | Sparkline labels, cents/kWh, 0–10 bar heights |
| `tomorrow_ready` | `true` once tomorrow’s OMIE file is published |
| `updated_label` | Last push time (Lisbon) |

Wholesale OMIE only — no retail taxes or network fees.

Price data source: [OMIE](https://www.omie.es/en/market-results/daily/daily-market/daily-hourly-price)
(OMI - Polo Espanol, S.A.). Cite OMIE if you republish these values.
