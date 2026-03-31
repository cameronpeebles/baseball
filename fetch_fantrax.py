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

# Fetch hitting stats
print("Fetching hitting stats...")
r = fetch([{"method": "getPlayerStats", "data": {
    "statusOrTeamFilter": "ALL",
    "pageNumber": "1",
    "positionOrGroup": "BASEBALL_HITTING",
    "miscDisplayType": "1"
}}], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players;statusOrTeamFilter=ALL;pageNumber=1;positionOrGroup=BASEBALL_HITTING;miscDisplayType=1")
save("players_hitting.json", r[0])

# Fetch pitching stats
print("Fetching pitching stats...")
r = fetch([{"method": "getPlayerStats", "data": {
    "statusOrTeamFilter": "ALL",
    "pageNumber": "1",
    "positionOrGroup": "BASEBALL_PITCHING",
    "miscDisplayType": "1"
}}], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players;statusOrTeamFilter=ALL;pageNumber=1;positionOrGroup=BASEBALL_PITCHING;miscDisplayType=1")
save("players_pitching.json", r[0])

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
