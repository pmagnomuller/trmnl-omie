---
name: trmnl-omie
description: "Use when the user asks about Iberian OMIE day-ahead electricity prices for Portugal or Spain (15-minute periods), the cheapest time to run an appliance or charge an EV, PT vs ES price comparison, TRMNL e-ink price displays, or triggering smart-home actions from price thresholds. No API credentials required. Not for Ostrom, Tibber, or other retail providers."
homepage: https://www.omie.es
---

# OMIE Energy (Portugal / Spain)

## When to use

Use when the user asks about:
- Current or upcoming electricity spot prices in Portugal or Spain
- Iberian OMIE day-ahead marginal prices (**15-minute** periods)
- Cheapest time to run a load (dishwasher, laundry, EV charging)
- Portugal vs Spain price comparison
- Pushing prices to a **TRMNL** e-ink Private Plugin
- Device actions based on price thresholds

## Setup

No third-party Python packages are required (stdlib only).

Optional default area (`PT` or `ES`) and TRMNL UUID:

```bash
cp .env.example .env
```

Alternatively, for shareable/persistent configuration, create:
`~/.config/omie-energy/config.json`

```bash
cp config.json.example ~/.config/omie-energy/config.json
```

Configuration precedence:
1) environment variables (`OMIE_*`, `TRMNL_PLUGIN_UUID`)
2) `~/.config/omie-energy/config.json`
3) default area `PT`

## Run

Use the wrapper from the skill directory:

```bash
bash run.sh prices
```

## Commands

### 1) Fetch current and upcoming 15-min day-ahead prices

Portugal (default):

```bash
bash run.sh prices --hours 36
```

Spain:

```bash
bash run.sh prices --area ES --hours 36
```

`--hours` is wall-clock hours (each hour = 4 periods of 15 minutes).

Custom date window:

```bash
bash run.sh prices --area PT --start 2026-06-01 --end 2026-06-07 --hours 48
```

### 2) Find optimal time for appliance or EV charging

Duration is converted to contiguous 15-minute quarters. With no `--window-start`, search starts from **now**.

```bash
bash run.sh optimize \
  --area PT \
  --kwh 28 \
  --power-kw 11 \
  --window-start "2026-06-20T18:00:00+01:00" \
  --window-end "2026-06-21T08:00:00+01:00"
```

For fixed duration:

```bash
bash run.sh optimize --area PT --duration-hours 2
```

### 3) Compare Portugal vs Spain prices

```bash
bash run.sh compare --hours 24
```

### 4) Control smart-home devices by price threshold

Thresholds use **EUR/kWh** (divide OMIE EUR/MWh by 1000).

Dry-run:

```bash
bash run.sh control \
  --area PT \
  --price-below 0.10 \
  --on-command "ha service call switch.turn_on --entity_id switch.ev_charger" \
  --off-command "ha service call switch.turn_off --entity_id switch.ev_charger"
```

Execute commands:

```bash
bash run.sh control \
  --area PT \
  --price-above 0.20 \
  --on-command "ha service call switch.turn_on --entity_id switch.boiler" \
  --off-command "ha service call switch.turn_off --entity_id switch.boiler" \
  --execute
```

### 5) TRMNL e-ink export / push

Dry-run (print compact JSON):

```bash
bash run.sh trmnl --area PT
```

Push to webhook:

```bash
export TRMNL_PLUGIN_UUID="your-plugin-uuid"
bash run.sh trmnl --area PT --push
```

Full setup (markup + GitHub Actions): see [`trmnl/SETUP.md`](trmnl/SETUP.md).

## Notes

- Data source: OMIE public `marginalpdbc_YYYYMMDD.1` files (96 × 15-minute periods).
- Prices are day-ahead **marginal** market prices in **EUR/MWh**; the CLI also shows **EUR/kWh**.
- Timestamps use Iberian local time (`Europe/Lisbon`).
- OMIE can expose extra periods on daylight-saving transition days.
- Tomorrow's prices are typically published in the afternoon; `tomorrow_ready` in the TRMNL payload reflects that.
- `optimize` and `control` use EUR/kWh internally for threshold compatibility with other energy skills.
- Start with dry-run control mode and verify commands before `--execute`.

## Safety

- No secrets required for OMIE; keep `.env` local if you store `TRMNL_PLUGIN_UUID`.
- Keep `--execute` off until threshold logic is verified in dry-run.
- Treat `--on-command` and `--off-command` as trusted input only (they run as shell commands).

## Publisher Checklist (ClawHub)

- Include: `SKILL.md`, `run.sh`, `omie_energy.py`, `requirements.txt`, `.env.example`, `config.json.example`, `trmnl/`
- Exclude: `.env`, `__pycache__/`, local logs, temporary files
- Validate from a clean shell:
  - `bash run.sh prices --area PT --hours 2`
  - `bash run.sh prices --area ES --hours 2`
  - `bash run.sh compare --hours 1`
  - `bash run.sh optimize --area PT --duration-hours 1`
  - `bash run.sh control --area PT --price-below 0.10 --on-command "echo on" --off-command "echo off"`
  - `bash run.sh trmnl --area PT`
