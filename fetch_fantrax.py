import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

USERNAME = os.environ.get("FANTRAX_USERNAME", "")
PASSWORD = os.environ.get("FANTRAX_PASSWORD", "")
FX_RM = os.environ.get("FANTRAX_FX_RM", "")
CF_CLEARANCE = os.environ.get("FANTRAX_CF_CLEARANCE", "")

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
    # responses[0] is login, rest are data
    data_responses = responses[1:]
    for i, resp in enumerate(data_responses):
        if "WARNING_NOT_LOGGED_IN" in str(resp):
            print(f"ERROR: Request {i} returned not logged in")
            exit(1)
    return data_responses

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Fetch season stats standings
print("Fetching season stats standings...")
responses = fetch([
    {"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "SEASON_STATS"}}
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=SEASON_STATS")
save("standings_season.json", responses[0])

# Fetch combined standings
print("Fetching combined standings...")
responses = fetch([
    {"method": "getStandings", "data": {"leagueId": LEAGUE_ID, "view": "COMBINED"}}
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings;view=COMBINED")
save("standings_combined.json", responses[0])

# Fetch all hitting stats
print("Fetching hitting stats...")
responses = fetch([
    {"method": "getPlayerStats", "data": {
        "statusOrTeamFilter": "ALL",
        "pageNumber": "1",
        "positionOrGroup": "BASEBALL_HITTING",
        "miscDisplayType": "1"
    }}
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players;statusOrTeamFilter=ALL;pageNumber=1;positionOrGroup=BASEBALL_HITTING;miscDisplayType=1")
save("players_hitting.json", responses[0])

# Fetch all pitching stats
print("Fetching pitching stats...")
responses = fetch([
    {"method": "getPlayerStats", "data": {
        "statusOrTeamFilter": "ALL",
        "pageNumber": "1",
        "positionOrGroup": "BASEBALL_PITCHING",
        "miscDisplayType": "1"
    }}
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players;statusOrTeamFilter=ALL;pageNumber=1;positionOrGroup=BASEBALL_PITCHING;miscDisplayType=1")
save("players_pitching.json", responses[0])

# Fetch rosters
print("Fetching rosters...")
responses = fetch([
    {"method": "getFantasyTeams", "data": {}},
    {"method": "getFantasyColumns", "data": {"maxResult": 8}},
    {"method": "getRefObject", "data": {"type": "FantasyItemStatus"}}
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/team/roster;reload=2")
save("rosters.json", responses[0])
save("roster_columns.json", responses[1])
save("roster_status.json", responses[2])

print("All done!")
