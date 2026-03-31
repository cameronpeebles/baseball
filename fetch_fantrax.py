import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

USERNAME = os.environ.get("FANTRAX_USERNAME", "")
PASSWORD = os.environ.get("FANTRAX_PASSWORD", "")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Referer": f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings",
})

def fetch_with_login(method, data, refUrl):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    body = {
        "msgs": [
            {"method": "login", "data": {
                "username": USERNAME,
                "password": PASSWORD,
                "stayLoggedIn": True
            }},
            {"method": method, "data": data}
        ],
        "uiv": 3,
        "refUrl": refUrl,
        "dt": 0,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    print(f"{method}: {r.status_code}")
    result = r.json()
    print(json.dumps(result, indent=2))
    responses = result.get("responses", [])
    if len(responses) < 2:
        print("ERROR: Not enough responses returned")
        exit(1)
    if "WARNING_NOT_LOGGED_IN" in str(responses[1]):
        print(f"ERROR: {method} returned not logged in")
        exit(1)
    return responses[1]

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Fetch standings
print("Fetching standings...")
standings = fetch_with_login(
    "getStandings",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings"
)
save("standings.json", standings)

# Fetch rosters
print("Fetching rosters...")
rosters = fetch_with_login(
    "getRosters",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/rosters"
)
save("rosters.json", rosters)

# Fetch free agents - hitters
print("Fetching free agent hitters...")
fa_hitting = fetch_with_login(
    "getPlayerStats",
    {
        "positionOrGroup": "BASEBALL_HITTING",
        "miscDisplayType": "1",
        "pageNumber": "1",
        "sortType": "SCORING_CATEGORY",
        "statusOrTeamFilter": "FA"
    },
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players"
)
save("free_agents_hitting.json", fa_hitting)

# Fetch free agents - pitchers
print("Fetching free agent pitchers...")
fa_pitching = fetch_with_login(
    "getPlayerStats",
    {
        "positionOrGroup": "BASEBALL_PITCHING",
        "miscDisplayType": "1",
        "pageNumber": "1",
        "sortType": "SCORING_CATEGORY",
        "statusOrTeamFilter": "FA"
    },
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/players"
)
save("free_agents_pitching.json", fa_pitching)

print("All done!")
