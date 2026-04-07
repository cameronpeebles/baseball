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

    # Collect ALL non-heading tables — Fantrax sometimes splits the 10 teams
    # across multiple tables (e.g. two groups of 5). We need every table.
    stat_tables = []
    for t in tables:
        if t.get("tableType") == "SECTION_HEADING":
            continue
        if t.get("rows"):
            stat_tables.append(t)

    if not stat_tables:
        print(f"  Period {period}: no data, stopping.")
        break

    # Use headers from the first table (all tables share the same header shape)
    var_headers = (stat_tables[0].get("header") or {}).get("cells") or []
    all_rows = []
    for t in stat_tables:
        all_rows.extend(t.get("rows") or [])

    if not all_rows:
        print(f"  Period {period}: empty rows, stopping.")
        break

    # Build key → column-index map from headers
    idx = {}
    for i, h in enumerate(var_headers):
        if h.get("key"):       idx[h["key"].upper()]       = i
        if h.get("name"):      idx[h["name"].upper()]      = i
        if h.get("shortName"): idx[h["shortName"].upper()] = i

    def get_stat(cells, key, default=0):
        i = idx.get(key.upper())
        if i is None:
            return default
        try:
            v = float((cells[i] or {}).get("content") or default)
            return v
        except (ValueError, TypeError):
            return default

    period_teams = []   # collect for schedule derivation

    for row in all_rows:
        fc    = row.get("fixedCells") or []
        cells = row.get("cells") or []

        # Resolve team name from teamId in fixed cells
        team_name = ""
        for fc_cell in fc:
            if fc_cell.get("teamId"):
                ti = team_info.get(fc_cell["teamId"]) or {}
                team_name = ti.get("name") or fc_cell.get("content") or ""
                break
        if not team_name:
            continue

        # Category stats — try both key and common shortName variants
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
        w = get_stat(cells, "W")   if "W"   in idx else get_stat(cells, "WIN")
        l = get_stat(cells, "L")   if "L"   in idx else get_stat(cells, "LOSS")
        t = get_stat(cells, "T")   if "T"   in idx else get_stat(cells, "TIE")
        period_teams.append({"team": team_name, "W": w, "L": l, "T": t})

    # Derive matchups: two teams played each other when W_a + W_b + T = 10
    paired = set()
    for i, a in enumerate(period_teams):
        if a["team"] in paired:
            continue
        for b in period_teams[i+1:]:
            if b["team"] in paired:
                continue
            if abs(a["T"] - b["T"]) < 0.01 and abs(a["W"] + b["W"] + a["T"] - 10) < 0.01:
                schedule.append({"week": period, "away": a["team"], "home": b["team"]})
                paired.add(a["team"])
                paired.add(b["team"])
                break

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

    is_under = (delta_xwoba  is not None and delta_xwoba  >= 0.020 and
                delta_babip  is not None and delta_babip  <= -0.020 and
                delta_barrel is not None and delta_barrel >= 0.0)
    is_over  = (delta_xwoba  is not None and delta_xwoba  <= -0.020 and
                delta_babip  is not None and delta_babip  >= 0.020 and
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
print("Targets fetch complete!")
