import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"
USERNAME = os.environ["FANTRAX_USERNAME"]
PASSWORD = os.environ["FANTRAX_PASSWORD"]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Referer": "https://www.fantrax.com/login",
})

def fetch_all(method_list, refUrl):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    msgs = [{"method": "login", "data": {
        "username": USERNAME,
        "password": PASSWORD,
        "stayLoggedIn": True
    }}]
    for method, data in method_list:
        msgs.append({"method": method, "data": data})
    body = {
        "msgs": msgs,
        "uiv": 3,
        "refUrl": refUrl,
        "dt": 0,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    print(f"Status: {r.status_code}")
    return r.json()

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Fetch standings + rosters in one request with login
print("Fetching standings and rosters...")
result = fetch_all([
    ("getStandings", {"leagueId": LEAGUE_ID}),
    ("getRosters", {"leagueId": LEAGUE_ID}),
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings")

responses = result.get("responses", [])
print(f"Got {len(responses)} responses")

# responses[0] = login, [1] = standings, [2] = rosters
if len(responses) > 1:
    save("standings.json", responses[1])
if len(responses) > 2:
    save("rosters.json", responses[2])

# Fetch free agents (hitters)
print("Fetching free agent hitters...")
fa_hit = fetch_all([
    ("getPlayerStats", {
        "positionOrGroup": "BASEBALL_HITTING",
        "miscDisplayType": "1",
        "pageNumber": "1",
        "sortType": "SCORING_CATEGORY",
        "statusOrTeamFilter": "FA"
    }),
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players")
fa_hit_responses = fa_hit.get("responses", [])
if len(fa_hit_responses) > 1:
    save("free_agents_hitting.json", fa_hit_responses[1])

# Fetch free agents (pitchers)
print("Fetching free agent pitchers...")
fa_pit = fetch_all([
    ("getPlayerStats", {
        "positionOrGroup": "BASEBALL_PITCHING",
        "miscDisplayType": "1",
        "pageNumber": "1",
        "sortType": "SCORING_CATEGORY",
        "statusOrTeamFilter": "FA"
    }),
], f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players")
fa_pit_responses = fa_pit.get("responses", [])
if len(fa_pit_responses) > 1:
    save("free_agents_pitching.json", fa_pit_responses[1])

print("All done!")
