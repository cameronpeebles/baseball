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

MAX_PERIODS = 30

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

    # Find the main stats table for this period (skip SECTION_HEADING rows)
    stat_table = None
    for t in tables:
        if t.get("tableType") == "SECTION_HEADING":
            continue
        rows = t.get("rows") or []
        if rows:
            stat_table = t
            break

    if not stat_table:
        print(f"  Period {period}: no data, stopping.")
        break

    rows        = stat_table.get("rows") or []
    var_headers = (stat_table.get("header") or {}).get("cells") or []

    if not rows:
        print(f"  Period {period}: empty rows, stopping.")
        break

    # Build key → column-index map from headers
    idx = {}
    for i, h in enumerate(var_headers):
        if h.get("key"):  idx[h["key"].upper()]          = i
        if h.get("name"): idx[h["name"].upper()]         = i
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

    for row in rows:
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

    print(f"  Period {period}: {len(period_teams)} teams, {len(period_teams)//2} matchups")

joe_stats.sort(key=lambda x: (x["week"], x["team"]))
schedule.sort(key=lambda x: (x["week"], x["away"]))

save("joe_stats.json", joe_stats)
save("schedule.json", schedule)

print(f"Saved {len(joe_stats)} team-week stat rows.")
print(f"Saved {len(schedule)} matchups across {len(set(m['week'] for m in schedule))} weeks.")
print("All done!")
