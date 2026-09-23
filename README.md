# trmnl-omie

OMIE Iberian day-ahead electricity prices (Portugal / Spain, 15-minute periods) on a [TRMNL](https://trmnl.com) e-ink display.

A GitHub Actions cron fetches OMIE public price files every 15 minutes and pushes a compact payload to a TRMNL Private Plugin webhook. Liquid markup for full, half-vertical and quadrant layouts is included.

The same script also works as a standalone CLI / agent skill: upcoming prices, cheapest charging window, PT vs ES comparison, and price-threshold control. No API keys, stdlib-only Python.

## What the display shows

- Current 15-min slot price (EUR/kWh) and slot label, e.g. `13:00–13:15`
- Today's min / max / avg day-ahead price
- Next cheapest 1h block
- Sparkline of upcoming periods (cents/kWh, 0–10 bar heights)
- Whether tomorrow's prices are published yet (`tomorrow_ready`)

## Setup

1. TRMNL → **Plugins → Private Plugin**, strategy **Webhook**, save, copy the UUID from `https://trmnl.com/api/custom_plugins/<UUID>`.
2. Paste markup from [`trmnl/markup/`](trmnl/markup/) (`full.liquid`, `half_vertical.liquid`, `quadrant.liquid`).
3. Add repo secret `TRMNL_PLUGIN_UUID`. The workflow [`.github/workflows/trmnl-omie.yml`](.github/workflows/trmnl-omie.yml) runs every 15 minutes (and on manual dispatch) and pushes PT prices.
4. Add the plugin to your device playlist (15–30 min refresh is enough).

Full walkthrough and payload field reference: [`trmnl/SETUP.md`](trmnl/SETUP.md).

## Local use

```bash
# dry-run: print the TRMNL payload
bash run.sh trmnl --area PT

# push once
export TRMNL_PLUGIN_UUID="your-uuid"
bash run.sh trmnl --area PT --push

# other commands
bash run.sh prices --area PT --hours 8
bash run.sh prices --area ES --hours 36
bash run.sh compare --hours 24
bash run.sh optimize --area PT --duration-hours 2
bash run.sh optimize --area PT --kwh 28 --power-kw 11
bash run.sh control --area PT --price-below 0.10 --on-command "echo on" --off-command "echo off"
```

Default area / UUID can live in `.env` (copy `.env.example`) or `~/.config/omie-energy/config.json` (copy `config.json.example`). Precedence: env vars → config file → `PT`.

## Price units

- OMIE publishes **EUR/MWh**; the CLI also shows **EUR/kWh** (`÷ 1000`).
- `optimize` / `control` thresholds are in **EUR/kWh**.
- Timestamps are `Europe/Lisbon`. DST days may carry extra periods.

## Safety

- `.env` is git-ignored. Only `TRMNL_PLUGIN_UUID` is a secret; OMIE data is public.
- `control` is dry-run by default; add `--execute` only after verifying thresholds.
- `--on-command` / `--off-command` run as shell commands — trusted input only.

## Files

- `omie_energy.py` — OMIE fetch, optimize/compare/control, TRMNL payload + webhook push
- `run.sh` — launcher that loads `.env` and runs the script
- `trmnl/SETUP.md`, `trmnl/markup/*.liquid` — Private Plugin setup and layouts
- `.github/workflows/trmnl-omie.yml` — 15-min cron push
- `SKILL.md` — agent-skill metadata (OpenClaw / ClawHub)
- `.env.example`, `config.json.example`, `requirements.txt`

## Related

- [omie-energy](https://github.com/pmagnomuller/omie-energy) — original hourly skill
- [ostrom-energy](https://github.com/pmagnomuller/ostrom-energy), [tibber-energy](https://github.com/pmagnomuller/tibber-energy)
- Writeup: [OpenClaw on My Homelab](https://pedro-muller.com/homelab/openclaw-on-my-homelab/)
