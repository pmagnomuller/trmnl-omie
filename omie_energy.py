#!/usr/bin/env python3
"""OMIE Iberian day-ahead prices (15-minute periods) + TRMNL webhook export."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IBERIAN_TZ = ZoneInfo("Europe/Lisbon")
AREA_LABELS = {"PT": "Portugal", "ES": "Spain"}
AREA_PRICE_INDEX = {"PT": 0, "ES": 1}  # after year,month,day,period
VALID_AREAS = frozenset(AREA_LABELS)
PERIOD_MINUTES = 15
PERIODS_PER_HOUR = 60 // PERIOD_MINUTES
MARGINALPDBC_URL = (
    "https://www.omie.es/en/file-download"
    "?parents=marginalpdbc&filename=marginalpdbc_{ymd}.1"
)
USER_AGENT = "omie-energy/2.0 (+https://github.com/pmagnomuller)"


def load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip())


def load_home_config(config_dirname: str) -> dict:
    cfg_path = Path.home() / ".config" / config_dirname / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {cfg_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object JSON in {cfg_path}.")
    return data


def config_get_str(cfg: dict, *keys: str) -> str | None:
    for k in keys:
        v = cfg.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip()
        else:
            v = str(v).strip()
        if v:
            return v
    return None


def env_nonempty(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def resolve_area(config: dict) -> str:
    area = env_nonempty("OMIE_AREA") or config_get_str(config, "area", "OMIE_AREA") or "PT"
    area = area.upper()
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT (Portugal) or ES (Spain).")
    return area


def resolve_trmnl_uuid(config: dict) -> str | None:
    return env_nonempty("TRMNL_PLUGIN_UUID") or config_get_str(
        config, "trmnl_plugin_uuid", "TRMNL_PLUGIN_UUID"
    )


def parse_dt(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IBERIAN_TZ)
    return dt


def period_start(market_day: date, period: int) -> datetime:
    """Period 1 = 00:00–00:15 Iberian local time on market_day."""
    base = datetime(market_day.year, market_day.month, market_day.day, tzinfo=IBERIAN_TZ)
    return base + timedelta(minutes=(period - 1) * PERIOD_MINUTES)


def download_text(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            content_type = (resp.headers.get("Content-Type") or "").lower()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"OMIE download failed ({exc.code}): {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OMIE download error: {exc}") from exc

    text = raw.decode("utf-8", errors="replace")
    if "text/html" in content_type or text.lstrip().lower().startswith("<!doctype"):
        return None
    if not text.lstrip().upper().startswith("MARGINALPDBC"):
        return None
    return text


def fetch_day_file(day: date) -> str | None:
    url = MARGINALPDBC_URL.format(ymd=day.strftime("%Y%m%d"))
    return download_text(url)


def parse_marginalpdbc(text: str, area: str) -> list[dict]:
    price_col = 4 + AREA_PRICE_INDEX[area]  # 4=PT, 5=ES
    points: list[dict] = []
    reader = csv.reader(io.StringIO(text), delimiter=";")
    for row in reader:
        if not row:
            continue
        first = row[0].strip()
        if first.upper().startswith("MARGINALPDBC") or first == "*":
            continue
        if len(row) < 6:
            continue
        try:
            year = int(row[0])
            month = int(row[1])
            day = int(row[2])
            period = int(row[3])
            price_mwh = float(row[price_col].replace(",", "."))
        except (ValueError, IndexError):
            continue
        market_day = date(year, month, day)
        starts = period_start(market_day, period)
        ends = starts + timedelta(minutes=PERIOD_MINUTES)
        points.append(
            {
                "startsAt": starts.isoformat(),
                "endsAt": ends.isoformat(),
                "market_date": str(market_day),
                "period": period,
                "area": area,
                "price_eur_mwh": price_mwh,
                "price_eur_kwh": price_mwh / 1000.0,
            }
        )
    points.sort(key=lambda p: p["startsAt"])
    return points


def fetch_area_prices(area: str, start: date, end: date) -> list[dict]:
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT or ES.")
    if end < start:
        raise RuntimeError("--end must be on or after --start.")

    points: list[dict] = []
    day = start
    while day <= end:
        text = fetch_day_file(day)
        if text:
            points.extend(parse_marginalpdbc(text, area))
        day += timedelta(days=1)
    return points


def day_file_available(day: date) -> bool:
    return fetch_day_file(day) is not None


def default_fetch_window() -> tuple[date, date]:
    today = datetime.now(IBERIAN_TZ).date()
    return today - timedelta(days=1), today + timedelta(days=2)


def hours_to_quarters(hours: float) -> int:
    return max(1, int(math.ceil(hours * PERIODS_PER_HOUR)))


def best_window(points, window_start, window_end, duration_quarters: int):
    scoped = []
    for p in points:
        ts = parse_dt(p["startsAt"])
        if window_start and ts < window_start:
            continue
        if window_end and ts >= window_end:
            continue
        scoped.append({"ts": ts, **p})
    if len(scoped) < duration_quarters:
        raise RuntimeError("Not enough 15-minute points in selected window.")

    step = PERIOD_MINUTES * 60
    best = None
    for i in range(0, len(scoped) - duration_quarters + 1):
        chunk = scoped[i : i + duration_quarters]
        contiguous = True
        for j in range(1, len(chunk)):
            if int((chunk[j]["ts"] - chunk[j - 1]["ts"]).total_seconds()) != step:
                contiguous = False
                break
        if not contiguous:
            continue
        total = sum(x["price_eur_kwh"] for x in chunk)
        if best is None or total < best["total"]:
            best = {"total": total, "chunk": chunk}
    if best is None:
        raise RuntimeError("No contiguous price window found.")
    return best


def current_point(points: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(IBERIAN_TZ)
    current_candidates = [
        p
        for p in points
        if parse_dt(p["startsAt"]) <= now < parse_dt(p["endsAt"])
    ]
    if current_candidates:
        return current_candidates[0]
    past = [p for p in points if parse_dt(p["startsAt"]) <= now]
    if not past:
        raise RuntimeError("No current/near-current price available.")
    return past[-1]


def upcoming_points(points: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(IBERIAN_TZ)
    return [p for p in points if parse_dt(p["endsAt"]) > now]


def command_prices(args, default_area: str):
    area = (args.area or default_area).upper()
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT or ES.")

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    if start is None or end is None:
        ds, de = default_fetch_window()
        start = start or ds
        end = end or de

    points = fetch_area_prices(area, start, end)
    now = datetime.now(IBERIAN_TZ)
    future = upcoming_points(points, now)
    limit = hours_to_quarters(args.hours)
    limited = future[:limit]

    print(f"Area: {area} ({AREA_LABELS[area]})")
    print(f"Source: OMIE day-ahead marginal prices 15-min ({start} to {end})")
    print(f"Upcoming prices (next {args.hours}h = {len(limited)} periods):")
    for p in limited:
        print(
            f"- {p['startsAt']}  "
            f"{p['price_eur_mwh']:.2f} EUR/MWh  "
            f"({p['price_eur_kwh']:.4f} EUR/kWh)"
        )


def command_optimize(args, default_area: str):
    area = (args.area or default_area).upper()
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT or ES.")

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    if start is None or end is None:
        ds, de = default_fetch_window()
        start = start or ds
        end = end or de

    points = fetch_area_prices(area, start, end)

    if args.duration_hours:
        duration_hours = float(args.duration_hours)
        duration_quarters = hours_to_quarters(duration_hours)
    else:
        if not args.kwh or not args.power_kw:
            raise RuntimeError("Provide either --duration-hours or both --kwh and --power-kw.")
        duration_hours = args.kwh / args.power_kw
        duration_quarters = hours_to_quarters(duration_hours)

    ws = parse_dt(args.window_start) if args.window_start else datetime.now(IBERIAN_TZ)
    we = parse_dt(args.window_end) if args.window_end else None
    best = best_window(points, ws, we, duration_quarters)
    chunk = best["chunk"]
    avg_kwh = best["total"] / len(chunk)
    avg_mwh = avg_kwh * 1000.0
    est_cost = (args.kwh * avg_kwh) if args.kwh else None
    end_at = parse_dt(chunk[-1]["endsAt"]).isoformat()

    print(f"Area: {area} ({AREA_LABELS[area]})")
    print(f"Optimal {duration_hours:g}h window ({duration_quarters} x 15-min):")
    print(f"- Start: {chunk[0]['startsAt']}")
    print(f"- End:   {end_at}")
    print(f"- Avg price: {avg_mwh:.2f} EUR/MWh ({avg_kwh:.4f} EUR/kWh)")
    if est_cost is not None:
        print(f"- Estimated energy cost ({args.kwh} kWh): {est_cost:.2f} EUR")
    print("Window details:")
    for p in chunk:
        print(
            f"  * {p['startsAt']} -> "
            f"{p['price_eur_mwh']:.2f} EUR/MWh ({p['price_eur_kwh']:.4f} EUR/kWh)"
        )


def command_compare(args):
    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    if start is None or end is None:
        ds, de = default_fetch_window()
        start = start or ds
        end = end or de

    pt_points = fetch_area_prices("PT", start, end)
    es_points = fetch_area_prices("ES", start, end)
    now = datetime.now(IBERIAN_TZ)

    pt_by_ts = {p["startsAt"]: p for p in upcoming_points(pt_points, now)}
    es_by_ts = {p["startsAt"]: p for p in upcoming_points(es_points, now)}
    limit = hours_to_quarters(args.hours)
    shared_ts = sorted(set(pt_by_ts) & set(es_by_ts))[:limit]

    print(
        f"Portugal vs Spain — next {args.hours}h "
        f"({len(shared_ts)} shared 15-min periods, {start} to {end})"
    )
    print(f"{'Period start':<26} {'PT EUR/MWh':>12} {'ES EUR/MWh':>12} {'Diff':>10}")
    for ts in shared_ts:
        pt = pt_by_ts[ts]["price_eur_mwh"]
        es = es_by_ts[ts]["price_eur_mwh"]
        diff = pt - es
        print(f"{ts:<26} {pt:>12.2f} {es:>12.2f} {diff:>+10.2f}")


def run_cmd(label: str, cmd: str, execute: bool):
    print(f"{label}: {cmd}")
    if execute:
        subprocess.run(cmd, shell=True, check=True)


def command_control(args, default_area: str):
    area = (args.area or default_area).upper()
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT or ES.")

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    if start is None or end is None:
        ds, de = default_fetch_window()
        start = start or ds
        end = end or de

    points = fetch_area_prices(area, start, end)
    current = current_point(points)

    price_kwh = float(current["price_eur_kwh"])
    price_mwh = float(current["price_eur_mwh"])
    print(f"Area: {area} ({AREA_LABELS[area]})")
    print(
        f"Current price: {price_mwh:.2f} EUR/MWh ({price_kwh:.4f} EUR/kWh) "
        f"at {current['startsAt']}"
    )
    execute = args.execute
    if not execute:
        print("Mode: dry-run (add --execute to run commands).")
    action_taken = False
    if args.price_below is not None and price_kwh <= args.price_below:
        if args.on_command:
            run_cmd("Price is below threshold -> ON command", args.on_command, execute)
            action_taken = True
    if args.price_above is not None and price_kwh >= args.price_above:
        if args.off_command:
            run_cmd("Price is above threshold -> OFF command", args.off_command, execute)
            action_taken = True
    if not action_taken:
        print("No threshold condition matched; no command executed.")


def fmt_eur_kwh(value: float) -> str:
    return f"{value:.4f}"


def fmt_clock(iso_ts: str) -> str:
    return parse_dt(iso_ts).strftime("%H:%M")


def build_trmnl_payload(
    area: str,
    points: list[dict],
    *,
    cheap_hours: float = 1.0,
    upcoming_count: int = 32,
) -> dict:
    now = datetime.now(IBERIAN_TZ)
    today = now.date()
    current = current_point(points, now)
    upcoming = upcoming_points(points, now)

    today_points = [p for p in points if p["market_date"] == str(today)]
    if not today_points:
        today_points = [current]

    prices = [p["price_eur_kwh"] for p in today_points]
    today_stats = {
        "min": round(min(prices), 4),
        "max": round(max(prices), 4),
        "avg": round(sum(prices) / len(prices), 4),
    }

    duration_quarters = hours_to_quarters(cheap_hours)
    try:
        best = best_window(upcoming, None, None, duration_quarters)
        chunk = best["chunk"]
        avg_kwh = best["total"] / len(chunk)
        cheapest_next = {
            "starts_at": chunk[0]["startsAt"],
            "ends_at": chunk[-1]["endsAt"],
            "label": f"{fmt_clock(chunk[0]['startsAt'])}–{fmt_clock(chunk[-1]['endsAt'])}",
            "avg_eur_kwh": round(avg_kwh, 4),
            "avg_cents_kwh": int(round(avg_kwh * 100)),
            "quarters": len(chunk),
        }
    except RuntimeError:
        cheapest_next = None

    slice_upcoming = upcoming[:upcoming_count]
    labels = [fmt_clock(p["startsAt"]) for p in slice_upcoming]
    cents = [int(round(p["price_eur_kwh"] * 100)) for p in slice_upcoming]
    max_c = max(cents) if cents else 1
    min_c = min(cents) if cents else 0
    span = max(max_c - min_c, 1)
    # 0–10 bar heights for e-ink sparkline
    bars = [int(round(10 * (c - min_c) / span)) for c in cents]

    tomorrow = today + timedelta(days=1)
    payload = {
        "area": area,
        "area_label": AREA_LABELS[area],
        "updated_at": now.isoformat(timespec="seconds"),
        "updated_label": now.strftime("%H:%M"),
        "current": {
            "price_eur_kwh": round(current["price_eur_kwh"], 4),
            "price_eur_mwh": round(current["price_eur_mwh"], 2),
            "price_cents_kwh": int(round(current["price_eur_kwh"] * 100)),
            "price_label": fmt_eur_kwh(current["price_eur_kwh"]),
            "starts_at": current["startsAt"],
            "ends_at": current["endsAt"],
            "slot_label": f"{fmt_clock(current['startsAt'])}–{fmt_clock(current['endsAt'])}",
        },
        "today": today_stats,
        "today_min_label": fmt_eur_kwh(today_stats["min"]),
        "today_max_label": fmt_eur_kwh(today_stats["max"]),
        "today_avg_label": fmt_eur_kwh(today_stats["avg"]),
        "cheapest_next": cheapest_next,
        "upcoming": {
            "t": labels,
            "p": cents,
            "bars": bars,
            "count": len(labels),
        },
        "tomorrow_ready": day_file_available(tomorrow),
    }
    return payload


def push_trmnl(uuid: str, merge_variables: dict) -> None:
    url = f"https://trmnl.com/api/custom_plugins/{uuid}"
    body = json.dumps({"merge_variables": merge_variables}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"TRMNL webhook failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"TRMNL webhook error: {exc}") from exc
    print(f"Pushed to TRMNL ({status}): {resp_body[:200]}")


def command_trmnl(args, default_area: str, config: dict):
    area = (args.area or default_area).upper()
    if area not in VALID_AREAS:
        raise RuntimeError(f"Invalid area '{area}'. Use PT or ES.")

    start = date.fromisoformat(args.start) if args.start else None
    end = date.fromisoformat(args.end) if args.end else None
    if start is None or end is None:
        ds, de = default_fetch_window()
        start = start or ds
        end = end or de

    points = fetch_area_prices(area, start, end)
    if not points:
        raise RuntimeError(f"No OMIE prices found for {area} between {start} and {end}.")

    payload = build_trmnl_payload(
        area,
        points,
        cheap_hours=args.cheap_hours,
        upcoming_count=args.upcoming,
    )
    encoded = json.dumps(payload, separators=(",", ":"))
    size = len(encoded.encode("utf-8"))
    if args.push and size > 2000:
        # Shrink upcoming arrays until under soft 2KB webhook guidance
        for n in (24, 16, 12, 8):
            payload = build_trmnl_payload(
                area, points, cheap_hours=args.cheap_hours, upcoming_count=n
            )
            encoded = json.dumps(payload, separators=(",", ":"))
            size = len(encoded.encode("utf-8"))
            if size <= 2000:
                break

    if args.max_age_min and args.max_age_min > 0:
        slot_end = parse_dt(payload["current"]["ends_at"])
        age_min = (datetime.now(IBERIAN_TZ) - slot_end).total_seconds() / 60.0
        if age_min > args.max_age_min:
            raise RuntimeError(
                f"Stale data: active slot ended {age_min:.0f} min ago "
                f"(limit {args.max_age_min:.0f} min). Refusing to publish."
            )

    # Push first: a rejected or failed webhook should not leave a fresh file
    # behind for a payload that was never delivered.
    if args.push:
        uuid = resolve_trmnl_uuid(config)
        if not uuid:
            raise RuntimeError(
                "TRMNL_PLUGIN_UUID not set (env or ~/.config/omie-energy/config.json)."
            )
        push_trmnl(uuid, payload)
        print(f"Payload size: {size} bytes")
    elif not args.out:
        print(json.dumps(payload, indent=2))
    if not args.push:
        print(f"# payload size: {size} bytes", file=sys.stderr)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(
            {"merge_variables": payload} if args.envelope else payload,
            separators=(",", ":"),
        ) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            dir=out_path.parent, prefix=out_path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(body)
            os.replace(tmp_name, out_path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        print(f"Wrote {out_path} ({len(body.encode('utf-8'))} bytes)")


def build_parser():
    p = argparse.ArgumentParser(
        description="OMIE Iberian market helper for Portugal/Spain 15-min day-ahead prices."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("prices", help="Show upcoming 15-min day-ahead prices.")
    s1.add_argument("--area", type=str.upper, choices=sorted(VALID_AREAS), help="PT or ES (default: OMIE_AREA or PT).")
    s1.add_argument("--hours", type=float, default=24, help="Wall-clock hours of upcoming periods.")
    s1.add_argument("--start", help="Fetch window start YYYY-MM-DD.")
    s1.add_argument("--end", help="Fetch window end YYYY-MM-DD.")

    s2 = sub.add_parser("optimize", help="Find cheapest contiguous time window.")
    s2.add_argument("--area", type=str.upper, choices=sorted(VALID_AREAS), help="PT or ES (default: OMIE_AREA or PT).")
    s2.add_argument("--duration-hours", type=float)
    s2.add_argument("--kwh", type=float)
    s2.add_argument("--power-kw", type=float)
    s2.add_argument("--window-start")
    s2.add_argument("--window-end")
    s2.add_argument("--start", help="Fetch window start YYYY-MM-DD.")
    s2.add_argument("--end", help="Fetch window end YYYY-MM-DD.")

    s3 = sub.add_parser("compare", help="Compare Portugal vs Spain prices period by period.")
    s3.add_argument("--hours", type=float, default=24)
    s3.add_argument("--start", help="Fetch window start YYYY-MM-DD.")
    s3.add_argument("--end", help="Fetch window end YYYY-MM-DD.")

    s4 = sub.add_parser("control", help="Trigger commands from current price thresholds.")
    s4.add_argument("--area", type=str.upper, choices=sorted(VALID_AREAS), help="PT or ES (default: OMIE_AREA or PT).")
    s4.add_argument("--price-below", type=float, help="Threshold in EUR/kWh.")
    s4.add_argument("--price-above", type=float, help="Threshold in EUR/kWh.")
    s4.add_argument("--on-command")
    s4.add_argument("--off-command")
    s4.add_argument("--execute", action="store_true")
    s4.add_argument("--start", help="Fetch window start YYYY-MM-DD.")
    s4.add_argument("--end", help="Fetch window end YYYY-MM-DD.")

    s5 = sub.add_parser("trmnl", help="Build compact JSON for a TRMNL Private Plugin webhook.")
    s5.add_argument("--area", type=str.upper, choices=sorted(VALID_AREAS), help="PT or ES (default: OMIE_AREA or PT).")
    s5.add_argument("--push", action="store_true", help="POST merge_variables to TRMNL webhook.")
    s5.add_argument(
        "--cheap-hours",
        type=float,
        default=1.0,
        help="Length of cheapest upcoming window (hours, default 1).",
    )
    s5.add_argument(
        "--upcoming",
        type=int,
        default=32,
        help="Number of upcoming 15-min slots in sparkline arrays.",
    )
    s5.add_argument(
        "--out",
        metavar="PATH",
        help="Write the payload JSON to PATH (atomic). Local dumps only; "
        "combine with --push if you also want a webhook update.",
    )
    s5.add_argument(
        "--max-age-min",
        type=float,
        default=0.0,
        metavar="MINUTES",
        help="Exit 1 if the active 15-min slot ended more than MINUTES ago "
        "(0 disables). Useful in CI before --push.",
    )
    s5.add_argument(
        "--envelope",
        action="store_true",
        help="With --out, wrap the payload as {\"merge_variables\": {...}} "
        "(the webhook body shape) instead of the bare object.",
    )
    s5.add_argument("--start", help="Fetch window start YYYY-MM-DD.")
    s5.add_argument("--end", help="Fetch window end YYYY-MM-DD.")

    return p


def main():
    load_local_env_file()
    parser = build_parser()
    args = parser.parse_args()
    config = load_home_config("omie-energy")
    default_area = resolve_area(config)

    if args.cmd == "prices":
        command_prices(args, default_area)
    elif args.cmd == "optimize":
        command_optimize(args, default_area)
    elif args.cmd == "compare":
        command_compare(args)
    elif args.cmd == "control":
        command_control(args, default_area)
    elif args.cmd == "trmnl":
        command_trmnl(args, default_area, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
