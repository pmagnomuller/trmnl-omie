# TRMNL Private Plugin — OMIE Portugal 15-min prices

Push day-ahead OMIE prices for Portugal to your TRMNL e-ink display every 15 minutes.

**Delivery is webhook-only.** There is no public JSON URL. A GitHub Actions cron POSTs to your Private Plugin UUID.

## One-time setup

### 1. Create a Private Plugin

1. In [TRMNL](https://trmnl.com) go to **Plugins** → **Private Plugin** (needs Developer Edition).
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
