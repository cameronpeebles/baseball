import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

USERNAME = os.environ.get("FANTRAX_USERNAME", "")
PASSWORD = os.environ.get("FANTRAX_PASSWORD", "")
FX_RM = os.environ.get("FANTRAX_FX_RM", "")
CF_CLEARANCE = os.environ.get("FANTRAX_CF_CLEARANCE", "")

TEAM_IDS = [
    "huopotx1miytz3cs",
    "xuv2jl3cmiytz3cs",
    "38pp2hphmiytz3cs",
    "t3dy3k9imiytz3cs",
    "r7wbtddcmiytz3cs",
    "aax8gerpmiytz3cs",
    "e3fi1sgxmiytz3cs",
    "2rfp1oakmiytz3cs",
    "corx71vmmiytz3cs",
    "7owlmroxmiytz3cs"
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})

if FX_RM:
    session.cookies.set("FX_RM", FX_RM, domain=".fantrax.com")
if CF_CLEARANCE:
    session.cookies.set("cf_clearance", CF_CLEARANCE, domain=".fantrax.com")
session.cookies.set("ui", "xvxwu418k69yvpe7", domain=".fantrax.com")

def fetch(msgs, refUrl):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    all_msgs = [{"method": "login", "data": {
        "username": USERNAME,
        "password": PASSWORD,
        "stayLoggedIn": True
    }}] + msgs
    body = {
        "msgs": all_msgs,
        "uiv": 3,
        "refUrl": refUrl,
        "dt": 1,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    result = r.json()
    responses = result.get("responses", [])
    data_responses = responses[1:]
    for resp in data_responses:
        if "WARNING_NOT_LOGGED_IN" in str(resp):
            print("ERROR: Not logged in")
            exit(1)
    return data_responses

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Fetch standings
print("Fetching standings...")
r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings")
save("standings.json", r[0])

# Fetch season stats
print("Fetching season stats...")
r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "SEASON_STATS"}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=SEASON_STATS")
save("standings_season.json", r[0])

# Fetch combined standings
print("Fetching combined standings...")
r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "COMBINED"}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=COMBINED")
save("standings_combined.json", r[0])

# Fetch schedule / by-period standings
print("Fetching schedule (by period) standings...")
r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "SCHEDULE"}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=SCHEDULE")
save("standings_schedule.json", r[0])

# Fetch hitting stats — paginate until we have 1000 players or run out of pages
print("Fetching hitting stats...")

def fetch_players(position_group, max_players=1000):
    all_rows = []
    base_data = None
    page = 1
    while len(all_rows) < max_players:
        print(f"  Page {page} ({len(all_rows)} players so far)...")
        r = fetch([{"method": "getPlayerStats", "data": {
            "statusOrTeamFilter": "ALL",
            "pageNumber": str(page),
            "positionOrGroup": position_group,
            "miscDisplayType": "1"
        }}], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players;statusOrTeamFilter=ALL;pageNumber={page};positionOrGroup={position_group};miscDisplayType=1")

        resp = r[0]
        data = resp.get("data") or {}
        rows = data.get("statsTable") or []

        if not rows:
            print(f"  No rows on page {page}, stopping.")
            break

        if base_data is None:
            base_data = resp

        all_rows.extend(rows)

        # Use Fantrax's own pagination flag to know when to stop
        if not data.get("nextSchedPageAllowed", False):
            print(f"  nextSchedPageAllowed is false — no more pages.")
            break

        page += 1

    print(f"  Total: {len(all_rows)} players fetched.")

    if base_data is None:
        return {}

    result = dict(base_data)
    result["data"] = dict(base_data.get("data") or {})
    result["data"]["statsTable"] = all_rows[:max_players]
    return result

hitting_data = fetch_players("BASEBALL_HITTING", max_players=1000)
save("players_hitting.json", hitting_data)

# Fetch pitching stats
print("Fetching pitching stats...")
pitching_data = fetch_players("BASEBALL_PITCHING", max_players=1000)
save("players_pitching.json", pitching_data)

# Fetch each team's roster individually
print("Fetching rosters...")
all_rosters = {}
for team_id in TEAM_IDS:
    print(f"  Fetching roster for {team_id}...")
    r = fetch([{"method": "getTeamRosterInfo", "data": {
        "leagueId": LEAGUE_ID,
        "teamId": team_id,
        "sortType": "SCORING_CATEGORY",
        "scipId": "10#0010#-1"
    }}], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/team/roster;teamId={team_id}")
    all_rosters[team_id] = r[0]
save("rosters.json", {"data": {"rosters": all_rosters}})

# ---------------------------------------------------------------------------
# Fetch per-week category stats and schedule for the JOE Factor calculator.
#
# Fantrax's COMBINED view only has W/L standings, not category stats.
# The per-week category stats live in the SCORING_PERIOD view — one fetch
# per scoring period. We also derive the schedule (who played whom each week)
# from the W/L totals since that's the most reliable source.
# ---------------------------------------------------------------------------
import re

print("Fetching per-week scoring period stats for JOE Factor...")

# First fetch the main standings to find out how many scoring periods exist
# and to get the team info / team names we need
r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings")
standings_data = r[0]
team_info = (standings_data.get("data") or {}).get("fantasyTeamInfo") or {}

# Fetch each scoring period individually (periods 1–30 is more than enough;
# we stop as soon as a period returns no rows)
joe_stats = []    # one entry per team per week: {team, week, R, HR, ...}
schedule  = []    # one entry per matchup: {week, away, home}

MAX_PERIODS = 20

for period in range(1, MAX_PERIODS + 1):
    r = fetch(
        [{"method": "getStandings", "data": {
            "leagueId": LEAGUE_ID,
            "view": "SCORING_PERIOD",
            "scoringPeriod": period
        }}],
        f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=SCORING_PERIOD;scoringPeriod={period}"
    )
    sp_data = r[0]
    tables = (sp_data.get("data") or {}).get("tableList") or []

    stat_tables = []
    for t in tables:
        if t.get("tableType") == "SECTION_HEADING":
            continue
        if t.get("rows"):
            stat_tables.append(t)

    if not stat_tables:
        print(f"  Period {period}: no data, stopping.")
        break

    var_headers = (stat_tables[0].get("header") or {}).get("cells") or []
    all_rows = []
    for t in stat_tables:
        all_rows.extend(t.get("rows") or [])

    if not all_rows:
        print(f"  Period {period}: empty rows, stopping.")
        break

    # Build key -> column-index map from headers
    idx = {}
    for i, h in enumerate(var_headers):
        if h.get("key"):       idx[h["key"].upper()]       = i
        if h.get("name"):      idx[h["name"].upper()]      = i
        if h.get("shortName"): idx[h["shortName"].upper()] = i

    if period == 1:
        print(f"  DEBUG period 1 idx keys: {sorted(idx.keys())}")

    def get_stat(cells, key, default=0):
        i = idx.get(key.upper())
        if i is None:
            return default
        try:
            v = float((cells[i] or {}).get("content") or default)
            return v
        except (ValueError, TypeError):
            return default

    period_teams = []
    seen_teams = set()  # deduplicate - take first row per team

    for row in all_rows:
        fc    = row.get("fixedCells") or []
        cells = row.get("cells") or []

        team_name = ""
        for fc_cell in fc:
            if fc_cell.get("teamId"):
                ti = team_info.get(fc_cell["teamId"]) or {}
                team_name = ti.get("name") or fc_cell.get("content") or ""
                break
        if not team_name or team_name in seen_teams:
            continue
        seen_teams.add(team_name)

        entry = {
            "team": team_name,
            "week": period,
            "R":    get_stat(cells, "R"),
            "HR":   get_stat(cells, "HR"),
            "RBI":  get_stat(cells, "RBI"),
            "SB":   get_stat(cells, "SB"),
            "AVG":  get_stat(cells, "AVG"),
            "K":    get_stat(cells, "K"),
            "W":    get_stat(cells, "W"),
            "SV":   get_stat(cells, "SV") or get_stat(cells, "SVH3") or get_stat(cells, "SVH"),
            "ERA":  get_stat(cells, "ERA"),
            "WHIP": get_stat(cells, "WHIP"),
        }
        joe_stats.append(entry)

        # Collect W/L/T for schedule derivation
        w = get_stat(cells, "W")
        l = get_stat(cells, "L")
        t = get_stat(cells, "T")
        period_teams.append({"team": team_name, "W": w, "L": l, "T": t})

    print(f"  Period {period}: {len(period_teams)} teams across {len(stat_tables)} table(s), {len(period_teams)//2} matchups")

joe_stats.sort(key=lambda x: (x["week"], x["team"]))
schedule.sort(key=lambda x: (x["week"], x["away"]))

save("joe_stats.json", joe_stats)
save("schedule.json", schedule)

print(f"Saved {len(joe_stats)} team-week stat rows.")
print(f"Saved {len(schedule)} matchups across {len(set(m['week'] for m in schedule))} weeks.")

# ---------------------------------------------------------------------------
# Fetch the full season schedule (all periods, including future ones).
# This is used by Match Predictions so team names are always live from Fantrax
# rather than hardcoded. Saves data/full_schedule.json as a flat list:
#   [{"period": 1, "away": "Team A", "home": "Team B"}, ...]
# ---------------------------------------------------------------------------
print("Fetching full season schedule...")

r = fetch(
    [{"method": "getSchedule", "data": {"leagueId": LEAGUE_ID}}],
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/matchups"
)
raw_schedule = r[0]

# The response contains a list of scoring periods. Each period has matchups
# with teamId references we resolve through team_info.
full_schedule = []

periods_data = (raw_schedule.get("data") or {}).get("matchupList") or \
               (raw_schedule.get("data") or {}).get("schedule") or \
               (raw_schedule.get("data") or {}).get("scheduleList") or []

# Fantrax sometimes nests schedule differently — handle both shapes
if not periods_data:
    # Try alternate key names
    data_block = raw_schedule.get("data") or {}
    for key in data_block:
        val = data_block[key]
        if isinstance(val, list) and len(val) > 0:
            # Check if it looks like a list of periods/matchups
            first = val[0]
            if isinstance(first, dict) and ("matchups" in first or "away" in first or "homeTeamId" in first):
                periods_data = val
                break

for item in periods_data:
    # Shape 1: {scoringPeriod, matchups: [{awayTeamId, homeTeamId}]}
    if "matchups" in item:
        period_num = item.get("scoringPeriod") or item.get("period") or item.get("id") or 0
        for m in item.get("matchups") or []:
            away_id = m.get("awayTeamId") or m.get("away") or ""
            home_id = m.get("homeTeamId") or m.get("home") or ""
            away_name = (team_info.get(away_id) or {}).get("name") or away_id
            home_name = (team_info.get(home_id) or {}).get("name") or home_id
            if away_name and home_name:
                full_schedule.append({
                    "period": int(period_num),
                    "away": away_name,
                    "home": home_name
                })
    # Shape 2: flat matchup row {scoringPeriod, awayTeamId, homeTeamId}
    elif "awayTeamId" in item or "homeTeamId" in item:
        period_num = item.get("scoringPeriod") or item.get("period") or 0
        away_id = item.get("awayTeamId") or ""
        home_id = item.get("homeTeamId") or ""
        away_name = (team_info.get(away_id) or {}).get("name") or away_id
        home_name = (team_info.get(home_id) or {}).get("name") or home_id
        if away_name and home_name:
            full_schedule.append({
                "period": int(period_num),
                "away": away_name,
                "home": home_name
            })

if full_schedule:
    full_schedule.sort(key=lambda x: (x["period"], x["away"]))
    save("full_schedule.json", full_schedule)
    print(f"Saved {len(full_schedule)} matchups across {len(set(m['period'] for m in full_schedule))} periods.")
else:
    # If we couldn't parse the response, save the raw data so we can inspect it
    print("WARNING: Could not parse schedule response — saving raw for inspection.")
    save("full_schedule_raw.json", raw_schedule)
    # Fall back to saving the CSV-derived schedule so the page still works
    csv_schedule = [
      {"period":1,  "away":"REL REL",               "home":"Buffalo Blues"},
      {"period":1,  "away":"Chew-Bock-a",            "home":"Team Fluck"},
      {"period":1,  "away":"PowerCraig5000",         "home":"Coover's Corner"},
      {"period":1,  "away":"William Street Wendy",   "home":"The Ronnie Woo-Woos"},
      {"period":1,  "away":"Not Just a MiLB Team",   "home":"Little Elm Big Bats"},
      {"period":2,  "away":"Little Elm Big Bats",    "home":"PowerCraig5000"},
      {"period":2,  "away":"Coover's Corner",        "home":"Chew-Bock-a"},
      {"period":2,  "away":"Team Fluck",             "home":"Buffalo Blues"},
      {"period":2,  "away":"The Ronnie Woo-Woos",    "home":"REL REL"},
      {"period":2,  "away":"Not Just a MiLB Team",   "home":"William Street Wendy"},
      {"period":3,  "away":"Buffalo Blues",          "home":"Coover's Corner"},
      {"period":3,  "away":"REL REL",                "home":"Not Just a MiLB Team"},
      {"period":3,  "away":"Chew-Bock-a",            "home":"PowerCraig5000"},
      {"period":3,  "away":"Team Fluck",             "home":"The Ronnie Woo-Woos"},
      {"period":3,  "away":"William Street Wendy",   "home":"Little Elm Big Bats"},
      {"period":4,  "away":"Little Elm Big Bats",    "home":"Chew-Bock-a"},
      {"period":4,  "away":"PowerCraig5000",         "home":"Buffalo Blues"},
      {"period":4,  "away":"Coover's Corner",        "home":"The Ronnie Woo-Woos"},
      {"period":4,  "away":"William Street Wendy",   "home":"REL REL"},
      {"period":4,  "away":"Not Just a MiLB Team",   "home":"Team Fluck"},
      {"period":5,  "away":"Buffalo Blues",          "home":"Chew-Bock-a"},
      {"period":5,  "away":"REL REL",                "home":"Little Elm Big Bats"},
      {"period":5,  "away":"Coover's Corner",        "home":"Not Just a MiLB Team"},
      {"period":5,  "away":"Team Fluck",             "home":"William Street Wendy"},
      {"period":5,  "away":"The Ronnie Woo-Woos",    "home":"PowerCraig5000"},
      {"period":6,  "away":"Little Elm Big Bats",    "home":"Buffalo Blues"},
      {"period":6,  "away":"REL REL",                "home":"Team Fluck"},
      {"period":6,  "away":"Chew-Bock-a",            "home":"The Ronnie Woo-Woos"},
      {"period":6,  "away":"PowerCraig5000",         "home":"Not Just a MiLB Team"},
      {"period":6,  "away":"William Street Wendy",   "home":"Coover's Corner"},
      {"period":7,  "away":"PowerCraig5000",         "home":"William Street Wendy"},
      {"period":7,  "away":"Coover's Corner",        "home":"REL REL"},
      {"period":7,  "away":"Team Fluck",             "home":"Little Elm Big Bats"},
      {"period":7,  "away":"The Ronnie Woo-Woos",    "home":"Buffalo Blues"},
      {"period":7,  "away":"Not Just a MiLB Team",   "home":"Chew-Bock-a"},
      {"period":8,  "away":"Buffalo Blues",          "home":"Not Just a MiLB Team"},
      {"period":8,  "away":"Little Elm Big Bats",    "home":"The Ronnie Woo-Woos"},
      {"period":8,  "away":"REL REL",                "home":"PowerCraig5000"},
      {"period":8,  "away":"Chew-Bock-a",            "home":"William Street Wendy"},
      {"period":8,  "away":"Team Fluck",             "home":"Coover's Corner"},
      {"period":9,  "away":"Chew-Bock-a",            "home":"REL REL"},
      {"period":9,  "away":"PowerCraig5000",         "home":"Team Fluck"},
      {"period":9,  "away":"Coover's Corner",        "home":"Little Elm Big Bats"},
      {"period":9,  "away":"William Street Wendy",   "home":"Buffalo Blues"},
      {"period":9,  "away":"Not Just a MiLB Team",   "home":"The Ronnie Woo-Woos"},
      {"period":10, "away":"Buffalo Blues",          "home":"REL REL"},
      {"period":10, "away":"Little Elm Big Bats",    "home":"Not Just a MiLB Team"},
      {"period":10, "away":"Coover's Corner",        "home":"PowerCraig5000"},
      {"period":10, "away":"Team Fluck",             "home":"Chew-Bock-a"},
      {"period":10, "away":"The Ronnie Woo-Woos",    "home":"William Street Wendy"},
      {"period":11, "away":"Buffalo Blues",          "home":"Team Fluck"},
      {"period":11, "away":"REL REL",                "home":"The Ronnie Woo-Woos"},
      {"period":11, "away":"Chew-Bock-a",            "home":"Coover's Corner"},
      {"period":11, "away":"PowerCraig5000",         "home":"Little Elm Big Bats"},
      {"period":11, "away":"William Street Wendy",   "home":"Not Just a MiLB Team"},
      {"period":12, "away":"Little Elm Big Bats",    "home":"William Street Wendy"},
      {"period":12, "away":"PowerCraig5000",         "home":"Chew-Bock-a"},
      {"period":12, "away":"Coover's Corner",        "home":"Buffalo Blues"},
      {"period":12, "away":"The Ronnie Woo-Woos",    "home":"Team Fluck"},
      {"period":12, "away":"Not Just a MiLB Team",   "home":"REL REL"},
      {"period":13, "away":"Buffalo Blues",          "home":"PowerCraig5000"},
      {"period":13, "away":"REL REL",                "home":"William Street Wendy"},
      {"period":13, "away":"Chew-Bock-a",            "home":"Little Elm Big Bats"},
      {"period":13, "away":"Team Fluck",             "home":"Not Just a MiLB Team"},
      {"period":13, "away":"The Ronnie Woo-Woos",    "home":"Coover's Corner"},
      {"period":14, "away":"Little Elm Big Bats",    "home":"REL REL"},
      {"period":14, "away":"Chew-Bock-a",            "home":"Buffalo Blues"},
      {"period":14, "away":"PowerCraig5000",         "home":"The Ronnie Woo-Woos"},
      {"period":14, "away":"William Street Wendy",   "home":"Team Fluck"},
      {"period":14, "away":"Not Just a MiLB Team",   "home":"Coover's Corner"},
      {"period":15, "away":"Buffalo Blues",          "home":"Little Elm Big Bats"},
      {"period":15, "away":"Coover's Corner",        "home":"William Street Wendy"},
      {"period":15, "away":"Team Fluck",             "home":"REL REL"},
      {"period":15, "away":"The Ronnie Woo-Woos",    "home":"Chew-Bock-a"},
      {"period":15, "away":"Not Just a MiLB Team",   "home":"PowerCraig5000"},
      {"period":16, "away":"Buffalo Blues",          "home":"The Ronnie Woo-Woos"},
      {"period":16, "away":"Little Elm Big Bats",    "home":"Team Fluck"},
      {"period":16, "away":"REL REL",                "home":"Coover's Corner"},
      {"period":16, "away":"Chew-Bock-a",            "home":"Not Just a MiLB Team"},
      {"period":16, "away":"William Street Wendy",   "home":"PowerCraig5000"},
      {"period":17, "away":"PowerCraig5000",         "home":"REL REL"},
      {"period":17, "away":"Coover's Corner",        "home":"Team Fluck"},
      {"period":17, "away":"The Ronnie Woo-Woos",    "home":"Little Elm Big Bats"},
      {"period":17, "away":"William Street Wendy",   "home":"Chew-Bock-a"},
      {"period":17, "away":"Not Just a MiLB Team",   "home":"Buffalo Blues"},
      {"period":18, "away":"Buffalo Blues",          "home":"William Street Wendy"},
      {"period":18, "away":"Little Elm Big Bats",    "home":"Coover's Corner"},
      {"period":18, "away":"REL REL",                "home":"Chew-Bock-a"},
      {"period":18, "away":"Team Fluck",             "home":"PowerCraig5000"},
      {"period":18, "away":"The Ronnie Woo-Woos",    "home":"Not Just a MiLB Team"},
      {"period":19, "away":"REL REL",                "home":"Buffalo Blues"},
      {"period":19, "away":"Chew-Bock-a",            "home":"Team Fluck"},
      {"period":19, "away":"PowerCraig5000",         "home":"Coover's Corner"},
      {"period":19, "away":"William Street Wendy",   "home":"The Ronnie Woo-Woos"},
      {"period":19, "away":"Not Just a MiLB Team",   "home":"Little Elm Big Bats"},
      {"period":20, "away":"Little Elm Big Bats",    "home":"PowerCraig5000"},
      {"period":20, "away":"Coover's Corner",        "home":"Chew-Bock-a"},
      {"period":20, "away":"Team Fluck",             "home":"Buffalo Blues"},
      {"period":20, "away":"The Ronnie Woo-Woos",    "home":"REL REL"},
      {"period":20, "away":"Not Just a MiLB Team",   "home":"William Street Wendy"},
    ]
    save("full_schedule.json", csv_schedule)
    print("Saved CSV-derived schedule as fallback.")

print("All done!")

# ---------------------------------------------------------------------------
# Baseball Savant advanced stats via pybaseball
# pip install pybaseball is handled by requirements.txt or inline below
# ---------------------------------------------------------------------------
try:
    import pybaseball
    from pybaseball import statcast_batter_exitvelo_barrels, batting_stats_range
    HAVE_PYBASEBALL = True
    print("pybaseball available")
except ImportError:
    HAVE_PYBASEBALL = False
    print("pybaseball not available, installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "pybaseball", "--quiet"])
    from pybaseball import statcast_batter_exitvelo_barrels
    HAVE_PYBASEBALL = True

import pandas as pd

SAVANT_YEAR = 2026

HIT_FIELD_MAP = {
    "slg_percent":        "SLG",
    "xslg":               "xSLG",
    "barrel_batted_rate": "Barrel%",
    "hard_hit_percent":   "HardHit%",
    "avg_hyper_speed":    "EV50",
    "babip":              "BABIP",
    "est_woba":           "xwOBA",
    "woba":               "wOBA",
}

PIT_FIELD_MAP = {
    "whiff_percent": "Whiff%",
    "k_percent":     "K%",
    "bb_percent":    "BB%",
}

def fetch_statcast_leaders(player_type, field_map, label):
    """Use pybaseball's statcast leaderboard function."""
    print(f"Fetching {label} via pybaseball...")
    try:
        from pybaseball import statcast_batter_exitvelo_barrels as bev
        # pybaseball provides statcast_batter_percentile_rankings and similar
        # Use the custom statcast leaderboard
        from pybaseball import statcast_leaderboards
        df = statcast_leaderboards(
            year=SAVANT_YEAR,
            player_type=player_type,
            min_pa=1
        )
        print(f"  Got {len(df)} rows, columns: {list(df.columns[:15])}")
        return df
    except Exception as e:
        print(f"  statcast_leaderboards failed: {e}")
        return None

def fetch_via_requests_csv(player_type, field_map, label):
    """Direct CSV download from Baseball Savant with proper headers."""
    import requests as _req
    import csv, io, gzip

    selections = ",".join(["player_id","last_name","first_name","pa"] + list(field_map.keys()))
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={SAVANT_YEAR}&type={player_type}&filter=&min=1"
        f"&selections={selections}"
        f"&chart=false&x=pa&y=pa&r=no&chartType=beeswarm"
        f"&sort=pa&sortDir=desc&csv=true"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/csv,text/plain,*/*",
        # No Accept-Encoding — let requests handle decompression automatically
    }
    print(f"  Trying direct CSV: {url[:120]}...")
    r = _req.get(url, headers=headers, timeout=30)
    r.encoding = 'utf-8'
    print(f"  Status: {r.status_code}, length: {len(r.content)}")

    if r.status_code != 200:
        print(f"  Non-200 response, aborting")
        return [], {}

    # Decompress if gzipped
    content = r.content
    if content[:2] == b'\x1f\x8b':
        print("  Response is gzip-compressed, decompressing...")
        content = gzip.decompress(content)

    text = content.decode('utf-8', errors='replace')
    print(f"  Decoded text length: {len(text)}, first 200: {text[:200]}")

    if not text.strip():
        print("  Empty response")
        return [], {}

    # Strip BOM if present
    if text.startswith('\ufeff'):
        text = text[1:]

    # Baseball Savant sometimes combines last_name and first_name into one
    # quoted field "last_name, first_name" — detect and handle both formats
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    print(f"  CSV rows: {len(rows)}, headers: {list(reader.fieldnames or [])[:12]}")

    # Detect combined name field
    fieldnames = reader.fieldnames or []
    combined_name_field = None
    for f in fieldnames:
        clean = f.strip().strip('"').lower()
        if 'last_name' in clean and 'first_name' in clean:
            combined_name_field = f
            break

    players = []
    totals = {d: 0.0 for d in field_map.values()}
    counts = {d: 0   for d in field_map.values()}

    for row in rows:
        if combined_name_field:
            # Format: "Vargas, Ildemaro" → "Ildemaro Vargas"
            combined = (row.get(combined_name_field) or "").strip()
            parts = combined.split(",", 1)
            last  = parts[0].strip()
            first = parts[1].strip() if len(parts) > 1 else ""
        else:
            first = (row.get("first_name") or "").strip()
            last  = (row.get("last_name")  or "").strip()
        name = (first + " " + last).strip()
        if not name: continue
        entry = {"PlayerName": name}
        for field, disp in field_map.items():
            raw = row.get(field)
            raw = raw.strip() if raw is not None else ""
            if raw and raw not in ("null",""):
                try:
                    v = float(raw)
                    entry[disp] = v
                    totals[disp] += v
                    counts[disp] += 1
                except: entry[disp] = None
            else:
                entry[disp] = None
        players.append(entry)

    league_avg = {d: round(totals[d]/counts[d], 3) for d in field_map.values() if counts[d] > 0}
    print(f"  Extracted {len(players)} players, league_avg: {league_avg}")
    return players, league_avg

# Try pybaseball first, fall back to direct CSV
print("\n=== Fetching hitting advanced stats ===")
hit_players, hit_lg = fetch_via_requests_csv("batter", HIT_FIELD_MAP, "hitters")

print("\n=== Fetching pitching advanced stats ===")
pit_players, pit_lg = fetch_via_requests_csv("pitcher", PIT_FIELD_MAP, "pitchers")

# Keep fangraphs files for backward compatibility
save("fangraphs_hitting.json", {
    "players":    hit_players,
    "league_avg": hit_lg,
    "cols":       list(HIT_FIELD_MAP.values())
})

save("fangraphs_pitching.json", {
    "players":    pit_players,
    "league_avg": pit_lg,
    "cols":       list(PIT_FIELD_MAP.values())
})

# Build name-keyed dicts for statcast unified files
import unicodedata as _ud2
def norm_name(n):
    n = n.lower().strip()
    n = ''.join(c for c in _ud2.normalize('NFD', n) if _ud2.category(c) != 'Mn')
    return ' '.join(''.join(c for c in n if c.isalpha() or c == ' ').split())

hit_by_name = {}
for p in hit_players:
    key = norm_name(p.get('PlayerName') or '')
    if key:
        hit_by_name[key] = {k: v for k, v in p.items() if k != 'PlayerName'}

pit_by_name = {}
for p in pit_players:
    key = norm_name(p.get('PlayerName') or '')
    if key:
        pit_by_name[key] = {k: v for k, v in p.items() if k != 'PlayerName'}

save("statcast_hitting.json", {
    "players":    hit_by_name,
    "league_avg": hit_lg,
    "cols":       list(HIT_FIELD_MAP.values())
})

save("statcast_pitching.json", {
    "players":    pit_by_name,
    "league_avg": pit_lg,
    "cols":       list(PIT_FIELD_MAP.values())
})

print("\nAdvanced stats fetch complete!")

# ---------------------------------------------------------------------------
# Waiver Targets — xwOBA vs wOBA, BABIP YoY, Barrel% YoY, HardHit% YoY
# Uses the same fetch_via_requests_csv that already works for fangraphs_hitting.json
# ---------------------------------------------------------------------------
print("\n=== Fetching waiver target data ===")

# 2026 data already fetched above as hit_players — reuse it
# Also fetch 2025 data for year-over-year comparisons
YOY_FIELD_MAP = {
    "barrel_batted_rate": "Barrel%",
    "hard_hit_percent":   "HardHit%",
    "babip":              "BABIP",
}

print("Fetching 2025 hitter Statcast for YoY deltas...")
hit_players_2025, _ = fetch_via_requests_csv("batter", YOY_FIELD_MAP, "hitters 2025")

# Also fetch xwOBA/wOBA for 2026
XWOBA_FIELD_MAP = {
    "est_woba":           "xwOBA",
    "woba":               "wOBA",
    "babip":              "BABIP",
    "barrel_batted_rate": "Barrel%",
    "hard_hit_percent":   "HardHit%",
}

# fetch_via_requests_csv uses SAVANT_YEAR=2026 — we need 2025 too
# Temporarily override year for 2025 fetch
import urllib.parse

def fetch_savant_year(year, field_map, label):
    """Fetch Savant custom leaderboard for a specific year."""
    import requests as _req2
    import csv as _csv2, io as _io2, gzip as _gzip2
    selections = ",".join(["player_id","last_name","first_name","pa"] + list(field_map.keys()))
    url = (
        f"https://baseballsavant.mlb.com/leaderboard/custom"
        f"?year={year}&type=batter&filter=&min=1"
        f"&selections={selections}"
        f"&chart=false&x=pa&y=pa&r=no&chartType=beeswarm"
        f"&sort=pa&sortDir=desc&csv=true"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/csv,text/plain,*/*",
    }
    print(f"  Fetching {label} ({year}): {url[:100]}...")
    try:
        r = _req2.get(url, headers=headers, timeout=30)
        print(f"  Status {r.status_code}, {len(r.content)} bytes")
        if r.status_code != 200:
            return []
        content = r.content
        if content[:2] == b'\x1f\x8b':
            content = _gzip2.decompress(content)
        text = content.decode('utf-8', errors='replace')
        if text.startswith('\ufeff'):
            text = text[1:]
        reader = _csv2.DictReader(_io2.StringIO(text))
        rows = list(reader)
        print(f"  Columns: {list(reader.fieldnames or [])[:12]}")
        if rows:
            print(f"  First row: { {k:v for k,v in list(rows[0].items())[:10]} }")

        # Parse into player list keyed by player_id and name
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        combined = next((f for f in fieldnames if 'last_name' in f.lower() and 'first_name' in f.lower()), None)
        result = []
        for row in rows:
            row = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            pid = row.get('player_id','').strip()
            if combined:
                parts = (row.get(combined) or '').split(',',1)
                name = ((parts[1].strip() if len(parts)>1 else '') + ' ' + parts[0].strip()).strip()
            else:
                first = (row.get('first_name') or '').strip()
                last  = (row.get('last_name')  or '').strip()
                name  = (first + ' ' + last).strip()
            entry = {'player_id': pid, 'name': name, 'pa': row.get('pa','').strip()}
            for field, disp in field_map.items():
                raw = (row.get(field) or '').strip()
                try: entry[disp] = float(raw) if raw and raw != 'null' else None
                except: entry[disp] = None
            result.append(entry)
        print(f"  Parsed {len(result)} players")
        return result
    except Exception as e:
        print(f"  Error: {e}")
        return []

TARGETS_FIELD_MAP = {
    "babip":              "BABIP",
    "barrel_batted_rate": "Barrel%",
    "hard_hit_percent":   "HardHit%",
}

XWOBA_FIELD_MAP = {
    "est_woba_using_speedangle": "xwOBA",
    "woba":                      "wOBA",
}

def fetch_xwoba_2026():
    """Fetch xwOBA from expected_statistics endpoint (known to work)."""
    url = ("https://baseballsavant.mlb.com/leaderboard/expected_statistics"
           "?type=batter&year=2026&position=&team=&filterType=bip&min=q&csv=true")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/csv,text/plain,*/*",
    }
    print(f"  xwOBA 2026: {url[:100]}...")
    try:
        r = requests.get(url, headers=headers, timeout=30)
        print(f"  Status {r.status_code}, {len(r.content)} bytes")
        if r.status_code != 200: return []
        content = r.content
        if content[:2] == b'\x1f\x8b':
            import gzip as _gz; content = _gz.decompress(content)
        text = content.decode('utf-8', errors='replace')
        if text.startswith('\ufeff'): text = text[1:]
        import csv as _c, io as _io
        reader = _c.DictReader(_io.StringIO(text))
        rows = list(reader)
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        print(f"  xwOBA columns: {fieldnames[:15]}, rows: {len(rows)}")
        combined = next((f for f in fieldnames if 'last_name' in f.lower() and 'first_name' in f.lower()), None)
        result = []
        for row in rows:
            row = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            pid = str(row.get('player_id','') or '').strip()
            if combined:
                parts = (row.get(combined) or '').split(',',1)
                name = ((parts[1].strip() if len(parts)>1 else '') + ' ' + parts[0].strip()).strip()
            else:
                name = ((row.get('first_name','') or '') + ' ' + (row.get('last_name','') or '')).strip()
            xwoba = None
            for k in ('est_woba','est_woba_using_speedangle','xwoba','expected_woba'):
                v = row.get(k,'').strip()
                if v and v != 'null':
                    try: xwoba = float(v); break
                    except: pass
            woba = None
            v = row.get('woba','').strip()
            if v and v != 'null':
                try: woba = float(v)
                except: pass
            pa = row.get('pa','').strip() or row.get('ab','').strip()
            result.append({'player_id': pid, 'name': name, 'xwOBA': xwoba, 'wOBA': woba, 'pa': pa})
        print(f"  Parsed {len(result)} xwOBA players")
        return result
    except Exception as e:
        print(f"  xwOBA error: {e}")
        return []

players_2026      = fetch_savant_year(2026, TARGETS_FIELD_MAP, "targets 2026")
players_2025      = fetch_savant_year(2025, TARGETS_FIELD_MAP, "targets 2025")
players_xwoba     = fetch_xwoba_2026()

# Build lookups keyed by player_id (primary) then name (fallback)
import unicodedata as _ud

def norm(n):
    n = n.lower().strip()
    n = ''.join(c for c in _ud.normalize('NFD', n) if _ud.category(c) != 'Mn')
    return ' '.join(''.join(c for c in n if c.isalpha() or c == ' ').split())

def make_lookup(players):
    by_id, by_name = {}, {}
    for p in players:
        pid = (p.get('player_id') or '').strip()
        name = (p.get('name') or '').strip()
        if pid:
            by_id[pid] = p
        if name:
            key = norm(name)
            if key and key not in by_name:
                by_name[key] = p
    return by_id, by_name

lkp26_id,    lkp26_nm    = make_lookup(players_2026)
lkp25_id,    lkp25_nm    = make_lookup(players_2025)
lkpxw_id,    lkpxw_nm    = make_lookup(players_xwoba)
print(f"  2026: {len(lkp26_id)} by id, xwoba: {len(lkpxw_id)} by id, 2025: {len(lkp25_id)} by id")

def find(by_id, by_name, pid, name):
    if pid and pid in by_id: return by_id[pid]
    key = norm(name)
    return by_name.get(key, {})

targets = []
for p26 in players_2026:
    pid  = (p26.get('player_id') or '').strip()
    name = (p26.get('name') or '').strip()
    p25  = find(lkp25_id, lkp25_nm, pid, name)
    pxw  = find(lkpxw_id, lkpxw_nm, pid, name)

    xwoba   = pxw.get('xwOBA')
    woba    = pxw.get('wOBA')
    b26     = p26.get('BABIP')
    bar26   = p26.get('Barrel%')
    hh26    = p26.get('HardHit%')
    b25     = p25.get('BABIP')
    bar25   = p25.get('Barrel%')
    hh25    = p25.get('HardHit%')
    pa_26_v = p26.get('pa') or pxw.get('pa')
    pa_26   = int(float(pa_26_v)) if pa_26_v else None

    delta_xwoba  = round(xwoba - woba, 3) if xwoba is not None and woba is not None else None
    delta_babip  = round(b26   - b25,  3) if b26   is not None and b25  is not None else None
    delta_barrel = round(bar26 - bar25, 1) if bar26 is not None and bar25 is not None else None
    delta_hh     = round(hh26  - hh25,  1) if hh26  is not None and hh25  is not None else None

    if xwoba is None: continue  # skip players with no 2026 data

    is_under = (delta_xwoba  is not None and delta_xwoba  >= 0.010 and
                delta_babip  is not None and delta_babip  <= -0.010 and
                delta_barrel is not None and delta_barrel >= 0.0)
    is_over  = (delta_xwoba  is not None and delta_xwoba  <= -0.010 and
                delta_babip  is not None and delta_babip  >= 0.010 and
                delta_barrel is not None and delta_barrel <= 0.0)

    signal = "Underperforming" if is_under else "Overperforming" if is_over else "Neutral"

    grade = "—"
    if is_under and delta_hh is not None:
        if   delta_hh >= 4.0: grade = "Elite Buy Low"
        elif delta_hh >= 3.0: grade = "Good Buy Low"
        elif delta_hh >= 2.0: grade = "Buy Low"
    elif is_over and delta_hh is not None:
        if   delta_hh <= -4.0: grade = "Elite Sell High"
        elif delta_hh <= -3.0: grade = "Good Sell High"
        elif delta_hh <= -2.0: grade = "Sell High"

    targets.append({
        "name":           name,
        "name_key":       norm(name),
        "mlbam_id":       pid,
        "pa_2026":        pa_26,
        "xwoba":          xwoba,
        "woba":           woba,
        "delta_xwoba":    delta_xwoba,
        "babip_2026":     b26,
        "babip_2025":     b25,
        "delta_babip":    delta_babip,
        "barrel_2026":    bar26,
        "barrel_2025":    bar25,
        "delta_barrel":   delta_barrel,
        "hardhit_2026":   hh26,
        "hardhit_2025":   hh25,
        "delta_hardhit":  delta_hh,
        "signal":         signal,
        "grade":          grade,
    })

n_under = sum(1 for t in targets if t['signal'] == 'Underperforming')
n_over  = sum(1 for t in targets if t['signal'] == 'Overperforming')
n_grade = sum(1 for t in targets if t['grade'] != '—')
print(f"  Merged {len(targets)} players — {n_under} underperforming, {n_over} overperforming, {n_grade} graded")
save("targets_hitting.json", targets)
print("Targets hitting fetch complete!")

# ---------------------------------------------------------------------------
# Pitcher Targets — xERA vs ERA, BABIP YoY, K% YoY, Fastball Velo YoY
# ---------------------------------------------------------------------------
print("\n=== Fetching pitcher target data ===")

import unicodedata as _ud2
def norm_pit(n):
    n = n.lower().strip()
    n = ''.join(c for c in _ud2.normalize('NFD', n) if _ud2.category(c) != 'Mn')
    return ' '.join(''.join(c for c in n if c.isalpha() or c == ' ').split())

def make_pit_lookup(players):
    by_id, by_name = {}, {}
    for p in players:
        pid  = (p.get('player_id') or '').strip()
        name = (p.get('name') or '').strip()
        if pid:  by_id[pid]  = p
        if name:
            key = norm_pit(name)
            if key and key not in by_name: by_name[key] = p
    return by_id, by_name

def find_pit(by_id, by_name, pid, name):
    if pid and pid in by_id: return by_id[pid]
    return by_name.get(norm_pit(name), {})

def safe_f(d, *keys):
    for k in keys:
        v = str(d.get(k, '') or '').strip()
        if v and v not in ('null',''):
            try: return float(v)
            except: pass
    return None

# ERA/xERA — use expected_statistics endpoint for pitchers
def fetch_pitcher_era_stats():
    url = ("https://baseballsavant.mlb.com/leaderboard/expected_statistics"
           "?type=pitcher&year=2026&position=&team=&filterType=bip&min=q&sort=15&sortDir=asc&csv=true")
    print(f"  ERA/xERA 2026: {url[:100]}...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                   "Accept": "text/csv,text/plain,*/*"}
        r = requests.get(url, headers=headers, timeout=30)
        print(f"  Status {r.status_code}, {len(r.content)} bytes")
        if r.status_code != 200: return []
        import gzip as _gz2, csv as _csv3, io as _io3
        content = r.content
        if content[:2] == b'\x1f\x8b': content = _gz2.decompress(content)
        text = content.decode('utf-8', errors='replace')
        if text.startswith('\ufeff'): text = text[1:]
        rows_raw = list(_csv3.DictReader(_io3.StringIO(text)))
        print(f"  ERA cols: {list(rows_raw[0].keys())[:15] if rows_raw else []}")
        fieldnames = list(_csv3.DictReader(_io3.StringIO(text)).fieldnames or [])
        combined = next((f for f in fieldnames if 'last_name' in f.lower() and 'first_name' in f.lower()), None)
        result = []
        for row in rows_raw:
            row = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            pid = str(row.get('player_id','') or '').strip()
            if combined:
                parts = (row.get(combined) or '').split(',',1)
                name = ((parts[1].strip() if len(parts)>1 else '') + ' ' + parts[0].strip()).strip()
            else:
                name = ((row.get('first_name','') or '') + ' ' + (row.get('last_name','') or '')).strip()
            result.append({'player_id': pid, 'name': name, 'row': row})
        print(f"  Parsed {len(result)} ERA rows")
        return result
    except Exception as e:
        print(f"  Error: {e}"); return []

# YoY stats — reuse fetch_savant_year but for pitcher type
PIT_YOY_BABIP  = {"babip": "BABIP"}
PIT_YOY_K      = {"k_percent": "K%"}
PIT_YOY_VELO   = {"fastball_avg_speed": "Velo"}

def fetch_savant_year_pit(year, field_map, label):
    """Same as fetch_savant_year but type=pitcher."""
    import requests as _rp, csv as _cp, io as _ip, gzip as _gp
    selections = ",".join(["player_id","last_name","first_name","pa"] + list(field_map.keys()))
    url = (f"https://baseballsavant.mlb.com/leaderboard/custom"
           f"?year={year}&type=pitcher&filter=&min=1"
           f"&selections={selections}&chart=false&x=pa&y=pa&r=no&chartType=beeswarm"
           f"&sort=pa&sortDir=desc&csv=true")
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
               "Accept": "text/csv,text/plain,*/*"}
    print(f"  {label} ({year}): {url[:100]}...")
    try:
        r = _rp.get(url, headers=headers, timeout=30)
        print(f"  Status {r.status_code}, {len(r.content)} bytes")
        if r.status_code != 200: return []
        content = r.content
        if content[:2] == b'\x1f\x8b': content = _gp.decompress(content)
        text = content.decode('utf-8', errors='replace')
        if text.startswith('\ufeff'): text = text[1:]
        reader = _cp.DictReader(_ip.StringIO(text))
        rows = list(reader)
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        combined = next((f for f in fieldnames if 'last_name' in f.lower() and 'first_name' in f.lower()), None)
        result = []
        for row in rows:
            row = {k.strip(): (v.strip() if isinstance(v,str) else v) for k,v in row.items()}
            pid = row.get('player_id','').strip()
            if combined:
                parts = (row.get(combined) or '').split(',',1)
                name = ((parts[1].strip() if len(parts)>1 else '') + ' ' + parts[0].strip()).strip()
            else:
                name = ((row.get('first_name','') or '') + ' ' + (row.get('last_name','') or '')).strip()
            entry = {'player_id': pid, 'name': name}
            for field, disp in field_map.items():
                raw = (row.get(field) or '').strip()
                try: entry[disp] = float(raw) if raw and raw != 'null' else None
                except: entry[disp] = None
            result.append(entry)
        print(f"  Parsed {len(result)} rows")
        return result
    except Exception as e:
        print(f"  Error: {e}"); return []

era_data     = fetch_pitcher_era_stats()
babip26_pit  = fetch_savant_year_pit(2026, PIT_YOY_BABIP, "Pitcher BABIP 2026")
babip25_pit  = fetch_savant_year_pit(2025, PIT_YOY_BABIP, "Pitcher BABIP 2025")
k26_pit      = fetch_savant_year_pit(2026, PIT_YOY_K,    "Pitcher K% 2026")
k25_pit      = fetch_savant_year_pit(2025, PIT_YOY_K,    "Pitcher K% 2025")
velo26_pit   = fetch_savant_year_pit(2026, PIT_YOY_VELO, "Pitcher Velo 2026")
velo25_pit   = fetch_savant_year_pit(2025, PIT_YOY_VELO, "Pitcher Velo 2025")

era_id, era_nm       = make_pit_lookup(era_data)
b26_id, b26_nm       = make_pit_lookup(babip26_pit)
b25_id, b25_nm       = make_pit_lookup(babip25_pit)
k26_id, k26_nm       = make_pit_lookup(k26_pit)
k25_id, k25_nm       = make_pit_lookup(k25_pit)
v26_id, v26_nm       = make_pit_lookup(velo26_pit)
v25_id, v25_nm       = make_pit_lookup(velo25_pit)
print(f"  era={len(era_id)}, b26={len(b26_id)}, b25={len(b25_id)}, k26={len(k26_id)}, v26={len(v26_id)}")

pit_targets = []
for pd2 in era_data:
    pid  = pd2['player_id']
    name = pd2['name']
    xr   = pd2['row']

    b26  = find_pit(b26_id, b26_nm, pid, name)
    b25  = find_pit(b25_id, b25_nm, pid, name)
    k26  = find_pit(k26_id, k26_nm, pid, name)
    k25  = find_pit(k25_id, k25_nm, pid, name)
    v26  = find_pit(v26_id, v26_nm, pid, name)
    v25  = find_pit(v25_id, v25_nm, pid, name)

    era  = safe_f(xr, 'era')
    xera = safe_f(xr, 'est_era', 'xera', 'expected_era', 'est_era_using_speedangle')
    ip26 = safe_f(xr, 'ip', 'innings_pitched')
    # delta_era = ERA - xERA
    # Positive = ERA worse than xERA = unlucky = Underperforming (Buy Low)
    # Negative = ERA better than xERA = lucky  = Overperforming  (Sell High)
    delta_era = round(era - xera, 2) if xera is not None and era is not None else None

    babip_26 = b26.get('BABIP'); babip_25 = b25.get('BABIP')
    delta_babip = round(babip_26 - babip_25, 3) if babip_26 is not None and babip_25 is not None else None

    k_26 = k26.get('K%'); k_25 = k25.get('K%')
    delta_k = round(k_26 - k_25, 1) if k_26 is not None and k_25 is not None else None

    velo_26 = v26.get('Velo'); velo_25 = v25.get('Velo')
    delta_velo = round(velo_26 - velo_25, 1) if velo_26 is not None and velo_25 is not None else None

    if era is None and xera is None:
        continue

    # Underperforming (Buy Low): ERA much worse than xERA, BABIP up (bad luck), K% holding
    # Overperforming  (Sell High): ERA much better than xERA, BABIP down (good luck), K% declining
    is_under = (delta_era   is not None and delta_era   >= 0.25 and
                delta_babip is not None and delta_babip >= 0.010 and
                delta_k     is not None and delta_k     >= 0.0)
    is_over  = (delta_era   is not None and delta_era   <= -0.25 and
                delta_babip is not None and delta_babip <= -0.010 and
                delta_k     is not None and delta_k     <= 0.0)

    signal = "Underperforming" if is_under else "Overperforming" if is_over else "Neutral"

    grade = "—"
    dv = delta_velo
    if is_under and dv is not None:
        if   dv >= 1.0:  grade = "Elite Buy Low"
        elif dv >= 0.75: grade = "Good Buy Low"
        elif dv >= 0.5:  grade = "Buy Low"
    elif is_over and dv is not None:
        if   dv <= -1.0:  grade = "Elite Sell High"
        elif dv <= -0.75: grade = "Good Sell High"
        elif dv <= -0.5:  grade = "Sell High"

    pit_targets.append({
        "name":         name,
        "name_key":     norm_pit(name),
        "mlbam_id":     pid,
        "ip_2026":      round(ip26, 1) if ip26 is not None else None,
        "era":          era,
        "xera":         xera,
        "delta_era":    delta_era,
        "babip_2026":   babip_26,
        "babip_2025":   babip_25,
        "delta_babip":  delta_babip,
        "k_2026":       k_26,
        "k_2025":       k_25,
        "delta_k":      delta_k,
        "velo_2026":    velo_26,
        "velo_2025":    velo_25,
        "delta_velo":   delta_velo,
        "signal":       signal,
        "grade":        grade,
    })

n_under = sum(1 for t in pit_targets if t['signal'] == 'Underperforming')
n_over  = sum(1 for t in pit_targets if t['signal'] == 'Overperforming')
n_grade = sum(1 for t in pit_targets if t['grade'] != '—')
print(f"  Merged {len(pit_targets)} pitchers — {n_under} underperforming, {n_over} overperforming, {n_grade} graded")
save("targets_pitching.json", pit_targets)
print("Pitcher targets fetch complete!")

# ---------------------------------------------------------------------------
# Optimal fWAR Weights — find positional scarcity weights that best predict
# fantasy point standings using scipy optimization
# ---------------------------------------------------------------------------
print("\n=== Computing optimal fWAR weights ===")

try:
    import numpy as np
    from scipy.optimize import minimize
    from scipy.stats import spearmanr

    # Historic season data hardcoded (same as in index.html HISTORIC_DATA)
    # Each entry: rank, pts, and per-category totals
    # We use pts as the "true" ordering signal
    HISTORIC = {
        2025: [
            dict(rank=1,  pts=81,   r=1159, hr=305, rbi=1059, sb=262, avg=0.261, w=165, k=2555, sv=126,   era=3.51, whip=1.165),
            dict(rank=2,  pts=80,   r=1241, hr=393, rbi=1165, sb=224, avg=0.261, w=144, k=2137, sv=127,   era=3.84, whip=1.226),
            dict(rank=3,  pts=68.5, r=1057, hr=311, rbi=1080, sb=181, avg=0.248, w=112, k=2098, sv=176.5, era=3.47, whip=1.171),
            dict(rank=4,  pts=65,   r=1067, hr=319, rbi=1064, sb=164, avg=0.261, w=38,  k=793,  sv=189,   era=3.38, whip=1.195),
            dict(rank=5,  pts=57.5, r=1102, hr=265, rbi=970,  sb=126, avg=0.254, w=152, k=2062, sv=148,   era=3.47, whip=1.169),
            dict(rank=6,  pts=56,   r=1102, hr=308, rbi=981,  sb=200, avg=0.254, w=108, k=1923, sv=151.5, era=3.74, whip=1.206),
            dict(rank=7,  pts=54,   r=1076, hr=287, rbi=1011, sb=176, avg=0.255, w=149, k=2072, sv=76.5,  era=3.86, whip=1.217),
            dict(rank=8,  pts=48.5, r=1011, hr=311, rbi=1016, sb=211, avg=0.255, w=129, k=1970, sv=67,    era=4.04, whip=1.279),
            dict(rank=9,  pts=28.5, r=1005, hr=299, rbi=981,  sb=148, avg=0.248, w=84,  k=1320, sv=72.5,  era=4.15, whip=1.238),
            dict(rank=10, pts=11,   r=737,  hr=235, rbi=762,  sb=115, avg=0.242, w=41,  k=751,  sv=3,     era=4.5,  whip=1.329),
        ],
        2024: [
            dict(rank=1,  pts=78,   r=1101, hr=338, rbi=1025, sb=254, avg=0.245, w=171, k=2414, sv=109, era=3.63, whip=1.148),
            dict(rank=2,  pts=72,   r=1076, hr=326, rbi=1053, sb=226, avg=0.257, w=125, k=1967, sv=117, era=3.55, whip=1.119),
            dict(rank=3,  pts=69.5, r=1078, hr=282, rbi=1037, sb=197, avg=0.257, w=153, k=2501, sv=121, era=4.02, whip=1.204),
            dict(rank=4,  pts=69,   r=1081, hr=289, rbi=1052, sb=178, avg=0.258, w=152, k=2309, sv=147, era=3.81, whip=1.258),
            dict(rank=5,  pts=59,   r=1188, hr=366, rbi=1115, sb=166, avg=0.255, w=142, k=2227, sv=78,  era=4.02, whip=1.257),
            dict(rank=6,  pts=55,   r=1037, hr=308, rbi=991,  sb=172, avg=0.252, w=144, k=2085, sv=130, era=3.71, whip=1.21),
            dict(rank=7,  pts=50.5, r=1073, hr=271, rbi=985,  sb=211, avg=0.247, w=145, k=2404, sv=46,  era=3.73, whip=1.226),
            dict(rank=8,  pts=49,   r=1047, hr=262, rbi=985,  sb=197, avg=0.254, w=159, k=2195, sv=108, era=3.94, whip=1.235),
            dict(rank=9,  pts=30,   r=1014, hr=273, rbi=1023, sb=148, avg=0.257, w=95,  k=1624, sv=28,  era=4.34, whip=1.299),
            dict(rank=10, pts=18,   r=515,  hr=143, rbi=532,  sb=95,  avg=0.247, w=22,  k=403,  sv=0,   era=3.96, whip=1.236),
        ],
        2023: [
            dict(rank=1,  pts=80,   r=1203, hr=373, rbi=1199, sb=162, avg=0.262, w=179, k=2811, sv=142, era=4.01, whip=1.269),
            dict(rank=2,  pts=76.5, r=1204, hr=353, rbi=1154, sb=189, avg=0.263, w=155, k=2201, sv=86,  era=3.98, whip=1.252),
            dict(rank=3,  pts=71,   r=1231, hr=356, rbi=1167, sb=184, avg=0.264, w=130, k=2090, sv=60,  era=4.2,  whip=1.229),
            dict(rank=4,  pts=71,   r=1084, hr=271, rbi=935,  sb=225, avg=0.259, w=144, k=2218, sv=130, era=3.79, whip=1.191),
            dict(rank=5,  pts=62.5, r=1063, hr=305, rbi=1098, sb=189, avg=0.258, w=128, k=2076, sv=173, era=4.01, whip=1.237),
            dict(rank=6,  pts=45,   r=921,  hr=259, rbi=874,  sb=143, avg=0.246, w=99,  k=1586, sv=122, era=3.95, whip=1.186),
            dict(rank=7,  pts=44,   r=1078, hr=328, rbi=1060, sb=213, avg=0.259, w=97,  k=1585, sv=0,   era=4.28, whip=1.296),
            dict(rank=8,  pts=40,   r=1057, hr=268, rbi=946,  sb=306, avg=0.262, w=89,  k=1543, sv=16,  era=4.12, whip=1.318),
            dict(rank=9,  pts=34,   r=936,  hr=301, rbi=961,  sb=133, avg=0.256, w=88,  k=1504, sv=78,  era=4.03, whip=1.273),
            dict(rank=10, pts=26,   r=947,  hr=192, rbi=780,  sb=67,  avg=0.264, w=65,  k=1202, sv=13,  era=4.05, whip=1.28),
        ],
        2022: [
            dict(rank=1,  pts=80,   r=1099, hr=332, rbi=1124, sb=180, avg=0.264, w=164, k=2115, sv=140, era=3.25, whip=1.1),
            dict(rank=2,  pts=78,   r=1085, hr=318, rbi=1059, sb=178, avg=0.261, w=140, k=2074, sv=120, era=3.28, whip=1.11),
            dict(rank=3,  pts=73,   r=1066, hr=315, rbi=1057, sb=146, avg=0.259, w=138, k=2070, sv=95,  era=3.41, whip=1.14),
            dict(rank=4,  pts=68,   r=1038, hr=302, rbi=1051, sb=137, avg=0.258, w=138, k=2068, sv=93,  era=3.43, whip=1.17),
            dict(rank=5,  pts=65.5, r=1034, hr=286, rbi=1015, sb=121, avg=0.256, w=128, k=2048, sv=91,  era=3.52, whip=1.19),
            dict(rank=6,  pts=58,   r=1027, hr=271, rbi=964,  sb=114, avg=0.253, w=122, k=1791, sv=88,  era=3.62, whip=1.2),
            dict(rank=7,  pts=47.5, r=1012, hr=269, rbi=918,  sb=101, avg=0.252, w=108, k=1654, sv=60,  era=3.77, whip=1.2),
            dict(rank=8,  pts=34,   r=841,  hr=214, rbi=818,  sb=82,  avg=0.251, w=80,  k=1199, sv=54,  era=3.79, whip=1.22),
            dict(rank=9,  pts=32,   r=786,  hr=200, rbi=719,  sb=58,  avg=0.244, w=63,  k=1036, sv=17,  era=4.14, whip=1.24),
            dict(rank=10, pts=14,   r=690,  hr=186, rbi=667,  sb=45,  avg=0.242, w=55,  k=1019, sv=11,  era=4.46, whip=1.32),
        ],
        2021: [
            dict(rank=1,  pts=81,   r=1039, hr=305, rbi=991,  sb=127, avg=0.266, w=133, k=1963, sv=125, era=3.28, whip=1.08),
            dict(rank=2,  pts=79,   r=1035, hr=302, rbi=951,  sb=123, avg=0.265, w=112, k=1918, sv=123, era=3.38, whip=1.16),
            dict(rank=3,  pts=78,   r=997,  hr=299, rbi=929,  sb=118, avg=0.264, w=111, k=1829, sv=92,  era=3.55, whip=1.16),
            dict(rank=4,  pts=77,   r=966,  hr=293, rbi=922,  sb=106, avg=0.262, w=108, k=1738, sv=88,  era=3.78, whip=1.16),
            dict(rank=5,  pts=49,   r=965,  hr=277, rbi=894,  sb=101, avg=0.261, w=101, k=1453, sv=62,  era=3.8,  whip=1.19),
            dict(rank=6,  pts=48,   r=928,  hr=257, rbi=878,  sb=98,  avg=0.261, w=85,  k=1447, sv=58,  era=3.85, whip=1.21),
            dict(rank=7,  pts=42.5, r=813,  hr=257, rbi=839,  sb=87,  avg=0.261, w=80,  k=1427, sv=48,  era=3.88, whip=1.21),
            dict(rank=8,  pts=38.5, r=804,  hr=216, rbi=796,  sb=84,  avg=0.255, w=59,  k=1019, sv=17,  era=3.91, whip=1.22),
            dict(rank=9,  pts=36,   r=689,  hr=180, rbi=678,  sb=48,  avg=0.255, w=55,  k=927,  sv=2,   era=4.2,  whip=1.27),
            dict(rank=10, pts=21,   r=451,  hr=134, rbi=494,  sb=43,  avg=0.24,  w=29,  k=493,  sv=0,   era=4.46, whip=1.32),
        ],
    }

    # Flatten all team-seasons
    all_rows = []
    for yr, teams in HISTORIC.items():
        for t in teams:
            all_rows.append(t)

    cats_high = ['r', 'hr', 'rbi', 'sb', 'avg', 'w', 'k', 'sv']
    cats_low  = ['era', 'whip']
    all_cats  = cats_high + cats_low

    # Compute league-average per cat per season for z-score normalization
    from collections import defaultdict
    yr_stats = defaultdict(lambda: defaultdict(list))
    for yr, teams in HISTORIC.items():
        for t in teams:
            for c in all_cats:
                yr_stats[yr][c].append(t[c])

    yr_mean = {yr: {c: np.mean(v) for c,v in cats.items()} for yr, cats in yr_stats.items()}
    yr_std  = {yr: {c: np.std(v) + 1e-9 for c,v in cats.items()} for yr, cats in yr_stats.items()}

    # Build z-score matrix: each row = one team-season, columns = 10 cats
    # For ERA/WHIP: negate so higher = better
    X = []
    y = []
    for yr, teams in HISTORIC.items():
        for t in teams:
            row = []
            for c in all_cats:
                z = (t[c] - yr_mean[yr][c]) / yr_std[yr][c]
                if c in cats_low:
                    z = -z
                row.append(z)
            X.append(row)
            y.append(t['pts'])

    X = np.array(X)
    y = np.array(y)

    # Objective: maximize Spearman r between weighted sum and pts
    # Use all 50 team-seasons together (cross-season)
    def neg_spearman(weights):
        w = np.abs(weights)  # force non-negative
        score = X @ w
        r, _ = spearmanr(score, y)
        return -r  # minimize negative = maximize positive

    # Initial guess: equal weights
    w0 = np.ones(len(all_cats)) / len(all_cats)
    bounds = [(0.0, None)] * len(all_cats)

    result = minimize(neg_spearman, w0, method='L-BFGS-B', bounds=bounds,
                      options={'maxiter': 2000, 'ftol': 1e-10})

    w_opt = np.abs(result.x)
    w_opt = w_opt / w_opt.sum()  # normalize to sum = 1

    # Map category weights to positional scarcity
    # Concept: positions that contribute most to high-value cats get higher replacement rank
    # We use the weight to scale the hybrid preset
    HYBRID = {'C': 17, '1B': 23, '2B': 18, '3B': 25, 'SS': 32, 'OF': 85, 'SP': 123, 'RP': 53}
    total_slots = sum(HYBRID.values())

    # Hit weight = sum of hitting cat weights
    hit_w = sum(w_opt[i] for i, c in enumerate(all_cats) if c in cats_high and c not in ('w','k','sv'))
    pit_w = sum(w_opt[i] for i, c in enumerate(all_cats) if c in ('w','k','sv') or c in cats_low)
    total_w = hit_w + pit_w

    # Scale SP/RP vs hitters by pit_w / hit_w ratio
    pit_ratio = pit_w / total_w
    hit_ratio = hit_w / total_w

    # Rebalance: keep total slots same, but shift between hitters/pitchers
    hit_positions = ['C','1B','2B','3B','SS','OF']
    pit_positions = ['SP','RP']
    base_hit_slots = sum(HYBRID[p] for p in hit_positions)
    base_pit_slots = sum(HYBRID[p] for p in pit_positions)

    opt_total = total_slots
    opt_hit_slots = round(opt_total * hit_ratio)
    opt_pit_slots = opt_total - opt_hit_slots

    # Within hitters: scale by individual cat weights
    hit_cat_weights = {
        'C':   w_opt[all_cats.index('avg')] * 0.4 + w_opt[all_cats.index('hr')] * 0.3 + w_opt[all_cats.index('rbi')] * 0.3,
        '1B':  w_opt[all_cats.index('hr')]  * 0.4 + w_opt[all_cats.index('rbi')]* 0.4 + w_opt[all_cats.index('r')]  * 0.2,
        '2B':  w_opt[all_cats.index('r')]   * 0.4 + w_opt[all_cats.index('sb')] * 0.3 + w_opt[all_cats.index('avg')]* 0.3,
        '3B':  w_opt[all_cats.index('hr')]  * 0.3 + w_opt[all_cats.index('rbi')]* 0.4 + w_opt[all_cats.index('r')]  * 0.3,
        'SS':  w_opt[all_cats.index('sb')]  * 0.4 + w_opt[all_cats.index('r')]  * 0.3 + w_opt[all_cats.index('avg')]* 0.3,
        'OF':  w_opt[all_cats.index('r')]   * 0.3 + w_opt[all_cats.index('hr')] * 0.2 + w_opt[all_cats.index('rbi')]* 0.2 + w_opt[all_cats.index('sb')]* 0.3,
    }
    total_hcw = sum(hit_cat_weights.values())
    hit_ranks = {p: max(5, round(opt_hit_slots * hit_cat_weights[p] / total_hcw)) for p in hit_positions}

    # Within pitchers: SP vs RP by W+K vs SV weight
    sp_w = w_opt[all_cats.index('w')] + w_opt[all_cats.index('k')] + w_opt[all_cats.index('era')] + w_opt[all_cats.index('whip')]
    rp_w = w_opt[all_cats.index('sv')]
    total_pcw = sp_w + rp_w
    pit_ranks = {
        'SP': max(30, round(opt_pit_slots * sp_w / total_pcw)),
        'RP': max(10, round(opt_pit_slots * rp_w / total_pcw)),
    }

    optimal_weights = {**hit_ranks, **pit_ranks}

    # Compute final correlation with optimal weights
    final_r, _ = spearmanr(X @ w_opt, y)

    print(f"  Optimal category weights: { {c: round(float(w),3) for c,w in zip(all_cats, w_opt)} }")
    print(f"  Spearman r with pts: {final_r:.3f}")
    print(f"  Optimal positional ranks: {optimal_weights}")

    save("optimal_fwar_weights.json", {
        "positional_ranks": optimal_weights,
        "category_weights": {c: round(float(w), 4) for c, w in zip(all_cats, w_opt)},
        "spearman_r": round(float(final_r), 3),
        "n_seasons": len(HISTORIC),
        "n_team_seasons": len(all_rows),
        "note": "Optimized to maximize Spearman rank correlation between team fWAR and fantasy points across historical seasons"
    })
    print("Optimal fWAR weights saved to optimal_fwar_weights.json")

except ImportError as e:
    print(f"  Skipping optimization — missing library: {e}")
    print("  Install scipy: pip install scipy")
except Exception as e:
    print(f"  Optimization error: {e}")
    import traceback; traceback.print_exc()

# ── FantasyPros ROS Projections ───────────────────────────────────────────────
import re as _re

def fetch_fantasypros(url, cols):
    """Scrape a FantasyPros projection table and return list of dicts."""
    import requests as _req
    try:
        r = _req.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  FantasyPros fetch failed: {e}")
        return []

    html = r.text
    table_match = _re.search(r'<table[^>]*>(.*?)</table>', html, _re.DOTALL | _re.IGNORECASE)
    if not table_match:
        print("  FantasyPros: table not found")
        return []

    table_html = table_match.group(1)
    rows = _re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, _re.DOTALL | _re.IGNORECASE)

    def strip_tags(s):
        return _re.sub(r'<[^>]+>', '', s).strip()

    def norm_name(s):
        s = _re.sub(r'\s*\([^)]+\)', '', s).strip()
        return s.lower()

    players = []
    for row in rows:
        cells = _re.findall(r'<td[^>]*>(.*?)</td>', row, _re.DOTALL | _re.IGNORECASE)
        if len(cells) < len(cols) + 2:
            continue
        raw_name = strip_tags(cells[1])
        if not raw_name or raw_name.upper() == raw_name:
            continue
        entry = {"name": raw_name, "name_key": norm_name(raw_name)}
        for i, col in enumerate(cols):
            try:
                val = strip_tags(cells[2 + i])
                entry[col] = float(val) if val not in ('', '-', 'N/A') else None
            except (ValueError, IndexError):
                entry[col] = None
        players.append(entry)

    return players


print("Fetching FantasyPros ROS hitter projections...")
fp_hit_cols = ["AB", "R", "HR", "RBI", "SB", "AVG", "OBP", "H", "2B", "3B", "BB", "SO", "SLG", "OPS"]
fp_hitters = fetch_fantasypros(
    "https://www.fantasypros.com/mlb/projections/ros-hitters.php",
    fp_hit_cols
)
print(f"  {len(fp_hitters)} hitters fetched")
save("fantasypros_hitters.json", fp_hitters)

print("Fetching FantasyPros ROS pitcher projections...")
fp_pit_cols = ["IP", "K", "W", "SV", "ERA", "WHIP", "ER", "H", "BB", "HR", "G", "GS", "L", "CG"]
fp_pitchers = fetch_fantasypros(
    "https://www.fantasypros.com/mlb/projections/ros-pitchers.php",
    fp_pit_cols
)
print(f"  {len(fp_pitchers)} pitchers fetched")
save("fantasypros_pitchers.json", fp_pitchers)
