#!/usr/bin/env python3
"""
Fetch minor league hitting and pitching stats from the public MLB Stats API
and write JSON files (minor_league_hitters.json, minor_league_pitchers.json)
for Bluebonnet Baseball to load.

Levels fetched (sport IDs):
  11 = Triple-A
  12 = Double-A
  13 = High-A
  14 = Single-A

Each output row contains:
  name, mlbamId, level (e.g. "AAA"), team (abbrev), org (parent MLB team abbrev),
  age, pos, games (G), and the per-stat fields.

The MLB Stats API is free, no auth, no rate-limit issues at this volume.
Run periodically (e.g. nightly via cron) to refresh data.

Usage:
  python3 fetch_minor_league_stats.py [--season 2026] [--out-dir ./public]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

API_BASE = "https://statsapi.mlb.com/api/v1"

# sport_id → level label used in the JSON output
LEVELS = {
    11: "AAA",
    12: "AA",
    13: "A+",
    14: "A",
}

# MLB Stats API pagination: 'limit' max appears to be 1000 per request
PAGE_SIZE = 1000

# Polite delay between API calls (seconds) to avoid hammering the API
REQUEST_DELAY = 0.4

session = requests.Session()
session.headers.update({
    "User-Agent": "BluebonnetBaseball/1.0 (+contact via app)",
    "Accept": "application/json",
})


def get(path: str, params: dict) -> dict:
    """GET with backoff on transient failures."""
    url = f"{API_BASE}/{path.lstrip('/')}"
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [warn] {url} attempt {attempt + 1} failed: {e}. retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after 3 attempts")


def build_team_org_map(season: int) -> dict:
    """
    Return a dict mapping minor league team ID (int) →
    {"team_abbrev": str, "team_name": str, "parent_org": str (MLB abbrev), "parent_id": int}
    """
    print("Fetching team list for org affiliation map...")
    data = get("teams", {
        "sportIds": ",".join(str(s) for s in LEVELS.keys()),
        "season": season,
    })
    teams = data.get("teams", [])
    out = {}
    for t in teams:
        tid = t.get("id")
        if not tid:
            continue
        parent = t.get("parentOrgName") or ""
        # parentOrgName is the full name; we need the abbrev. Look it up from
        # the parent_id by querying the MLB sport (sportId=1).
        # Easier path: parentOrgId, then resolve to abbrev with a second pass.
        out[tid] = {
            "team_abbrev": t.get("abbreviation") or "",
            "team_name": t.get("name") or "",
            "parent_org_name": parent,
            "parent_org_id": t.get("parentOrgId") or 0,
        }
    # Resolve parent org IDs → abbrev via the MLB team list
    mlb_data = get("teams", {"sportIds": "1", "season": season})
    parent_abbrev = {t["id"]: t.get("abbreviation", "") for t in mlb_data.get("teams", [])}
    for tid, info in out.items():
        pid = info["parent_org_id"]
        info["parent_org"] = parent_abbrev.get(pid, "")
    print(f"  loaded {len(out)} minor league teams")
    return out


def fetch_player_stats(season: int, group: str, sport_id: int) -> list:
    """
    Fetch all player season stats for a given sport (level) and stat group.
    Returns list of raw API rows.
    """
    rows = []
    offset = 0
    while True:
        data = get("stats", {
            "stats": "season",
            "group": group,         # "hitting" or "pitching"
            "sportIds": sport_id,
            "season": season,
            "limit": PAGE_SIZE,
            "offset": offset,
            "playerPool": "All",
        })
        splits = []
        for grp in data.get("stats", []):
            splits.extend(grp.get("splits", []))
        if not splits:
            break
        rows.extend(splits)
        if len(splits) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(REQUEST_DELAY)
    return rows


def calc_age(birthdate: str, season: int) -> int | None:
    """Player age as of July 1 of the season (mid-season approximation)."""
    if not birthdate:
        return None
    try:
        bd = datetime.strptime(birthdate, "%Y-%m-%d")
        ref = datetime(season, 7, 1)
        return ref.year - bd.year - ((ref.month, ref.day) < (bd.month, bd.day))
    except (ValueError, TypeError):
        return None


def transform_hitting(rows: list, team_map: dict, season: int) -> list:
    """Map raw API rows → flat hitting records."""
    out = []
    for r in rows:
        player = r.get("player") or {}
        team = r.get("team") or {}
        stat = r.get("stat") or {}
        tid = team.get("id")
        team_info = team_map.get(tid, {})
        sport = r.get("sport") or {}
        sport_id = sport.get("id") or 0
        out.append({
            "name": player.get("fullName") or "",
            "mlbamId": player.get("id") or 0,
            "age": calc_age(player.get("birthDate"), season),
            "pos": (player.get("primaryPosition") or {}).get("abbreviation") or "",
            "team": team_info.get("team_abbrev") or team.get("abbreviation") or "",
            "team_name": team.get("name") or "",
            "org": team_info.get("parent_org") or "",
            "level": LEVELS.get(sport_id, ""),
            "G":   stat.get("gamesPlayed") or 0,
            "AB":  stat.get("atBats") or 0,
            "R":   stat.get("runs") or 0,
            "H":   stat.get("hits") or 0,
            "2B":  stat.get("doubles") or 0,
            "3B":  stat.get("triples") or 0,
            "HR":  stat.get("homeRuns") or 0,
            "RBI": stat.get("rbi") or 0,
            "BB":  stat.get("baseOnBalls") or 0,
            "SO":  stat.get("strikeOuts") or 0,
            "SB":  stat.get("stolenBases") or 0,
            "CS":  stat.get("caughtStealing") or 0,
            "AVG": _f(stat.get("avg")),
            "OBP": _f(stat.get("obp")),
            "SLG": _f(stat.get("slg")),
            "OPS": _f(stat.get("ops")),
        })
    return out


def transform_pitching(rows: list, team_map: dict, season: int) -> list:
    """Map raw API rows → flat pitching records."""
    out = []
    for r in rows:
        player = r.get("player") or {}
        team = r.get("team") or {}
        stat = r.get("stat") or {}
        tid = team.get("id")
        team_info = team_map.get(tid, {})
        sport = r.get("sport") or {}
        sport_id = sport.get("id") or 0
        # API returns IP as e.g. "76.2" (66 outs); convert to float innings.
        ip_raw = stat.get("inningsPitched")
        ip = _ip_to_float(ip_raw)
        out.append({
            "name": player.get("fullName") or "",
            "mlbamId": player.get("id") or 0,
            "age": calc_age(player.get("birthDate"), season),
            "pos": (player.get("primaryPosition") or {}).get("abbreviation") or "P",
            "team": team_info.get("team_abbrev") or team.get("abbreviation") or "",
            "team_name": team.get("name") or "",
            "org": team_info.get("parent_org") or "",
            "level": LEVELS.get(sport_id, ""),
            "G":     stat.get("gamesPlayed") or 0,
            "GS":    stat.get("gamesStarted") or 0,
            "IP":    ip,
            "W":     stat.get("wins") or 0,
            "L":     stat.get("losses") or 0,
            "SV":    stat.get("saves") or 0,
            "HLD":   stat.get("holds") or 0,
            "SVH3":  (stat.get("saves") or 0) + (stat.get("holds") or 0),  # bb saves-or-holds
            "K":     stat.get("strikeOuts") or 0,
            "BB":    stat.get("baseOnBalls") or 0,
            "H":     stat.get("hits") or 0,
            "ER":    stat.get("earnedRuns") or 0,
            "ERA":   _f(stat.get("era")),
            "WHIP":  _f(stat.get("whip")),
            "K9":    _f(stat.get("strikeoutsPer9Inn")),
            "BB9":   _f(stat.get("walksPer9Inn")),
        })
    return out


def _f(v):
    """Coerce a numeric/string stat to float, returning None if unparseable."""
    if v is None or v == "" or v == "-.--":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ip_to_float(v):
    """MLB's IP format: '76.2' means 76 + 2/3 innings (i.e. 2 outs)."""
    if v is None:
        return 0.0
    try:
        s = str(v)
        if "." in s:
            whole, frac = s.split(".")
            return int(whole) + int(frac) / 3.0
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=datetime.now().year,
                        help="MLB season year (default: current year)")
    parser.add_argument("--out-dir", type=Path, default=Path("."),
                        help="Directory to write JSON output (default: cwd)")
    args = parser.parse_args()

    season = args.season
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching MiLB stats for season {season}")
    print(f"Levels: {', '.join(LEVELS.values())}")
    print(f"Output directory: {out_dir.resolve()}")
    print()

    team_map = build_team_org_map(season)

    all_hitters = []
    all_pitchers = []

    for sport_id, level_label in LEVELS.items():
        print(f"\n[{level_label}] fetching hitting...")
        rows = fetch_player_stats(season, "hitting", sport_id)
        hitters = transform_hitting(rows, team_map, season)
        print(f"  {len(hitters)} hitter rows")
        all_hitters.extend(hitters)

        print(f"[{level_label}] fetching pitching...")
        rows = fetch_player_stats(season, "pitching", sport_id)
        pitchers = transform_pitching(rows, team_map, season)
        print(f"  {len(pitchers)} pitcher rows")
        all_pitchers.extend(pitchers)

        time.sleep(REQUEST_DELAY)

    # Sort by name within level/org so the JSON diffs are stable.
    all_hitters.sort(key=lambda p: (p.get("level", ""), p.get("org", ""), p.get("name", "")))
    all_pitchers.sort(key=lambda p: (p.get("level", ""), p.get("org", ""), p.get("name", "")))

    h_path = out_dir / "minor_league_hitters.json"
    p_path = out_dir / "minor_league_pitchers.json"
    with h_path.open("w", encoding="utf-8") as f:
        json.dump(all_hitters, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    with p_path.open("w", encoding="utf-8") as f:
        json.dump(all_pitchers, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"\nWrote {len(all_hitters)} hitters → {h_path}")
    print(f"Wrote {len(all_pitchers)} pitchers → {p_path}")
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
