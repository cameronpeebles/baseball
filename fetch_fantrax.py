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
# Fetch schedule / matchup results and save as schedule.json
# This is used by the JOE Factor luck calculator on the website.
# It fetches every completed scoring period and figures out who played whom
# each week by matching up teams whose category win totals add up to 10.
# ---------------------------------------------------------------------------
print("Fetching schedule / matchup data...")

r = fetch([{"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "COMBINED"}}],
          f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=COMBINED")

combined_data = r[0]
tables = (combined_data.get("data") or {}).get("tableList") or []
team_info = (combined_data.get("data") or {}).get("fantasyTeamInfo") or {}

schedule = []

for table in tables:
    caption = table.get("caption") or ""

    # Each weekly table is labelled something like "Week 1" or "Scoring Period 3"
    import re
    week_match = re.search(r'(?:week|period|wk)\s*(\d+)', caption, re.IGNORECASE)
    if not week_match:
        continue
    week = int(week_match.group(1))

    rows = table.get("rows") or []
    fixed_headers = (table.get("fixedHeader") or {}).get("cells") or []
    var_headers = (table.get("header") or {}).get("cells") or []

    # Find the index of W, L, T columns in the variable cells
    w_idx = l_idx = t_idx = None
    for i, h in enumerate(var_headers):
        key = (h.get("key") or "").upper()
        name = (h.get("name") or "").upper()
        if key == "W" or name == "W":
            w_idx = i
        elif key == "L" or name == "L":
            l_idx = i
        elif key == "T" or name == "T":
            t_idx = i

    if w_idx is None or l_idx is None:
        continue

    week_teams = []
    for row in rows:
        fixed_cells = row.get("fixedCells") or []
        cells = row.get("cells") or []

        # Get team name from the fixed cells (teamId lookup)
        team_id = None
        team_name = None
        for fc in fixed_cells:
            if fc.get("teamId"):
                team_id = fc["teamId"]
                ti = team_info.get(team_id) or {}
                team_name = ti.get("name") or fc.get("content") or ""
                break

        if not team_name:
            continue

        try:
            w = float(cells[w_idx].get("content") or 0) if w_idx < len(cells) else 0
            l = float(cells[l_idx].get("content") or 0) if l_idx < len(cells) else 0
            t = float(cells[t_idx].get("content") or 0) if t_idx is not None and t_idx < len(cells) else 0
        except (ValueError, TypeError, AttributeError):
            continue

        week_teams.append({"team": team_name, "W": w, "L": l, "T": t})

    # Match up opponents: two teams played each other when W_a + W_b + T = 10
    # (ties are shared: both teams get the same T count)
    paired = set()
    for i, a in enumerate(week_teams):
        if a["team"] in paired:
            continue
        for b in week_teams[i+1:]:
            if b["team"] in paired:
                continue
            if a["T"] == b["T"] and abs(a["W"] + b["W"] + a["T"] - 10) < 0.01:
                schedule.append({"week": week, "away": a["team"], "home": b["team"]})
                paired.add(a["team"])
                paired.add(b["team"])
                break

schedule.sort(key=lambda x: (x["week"], x["away"]))
save("schedule.json", schedule)

print(f"Saved {len(schedule)} matchups across {len(set(m['week'] for m in schedule))} weeks.")
print("All done!")
