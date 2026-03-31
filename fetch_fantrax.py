import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

USERNAME = os.environ.get("FANTRAX_USERNAME", "")
PASSWORD = os.environ.get("FANTRAX_PASSWORD", "")
FX_RM = os.environ.get("FANTRAX_FX_RM", "")
CF_CLEARANCE = os.environ.get("FANTRAX_CF_CLEARANCE", "")

print(f"FX_RM loaded: {'YES' if FX_RM else 'NO'}")
print(f"CF_CLEARANCE loaded: {'YES' if CF_CLEARANCE else 'NO'}")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Referer": f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
})

# Set all available cookies
if FX_RM:
    session.cookies.set("FX_RM", FX_RM, domain=".fantrax.com")
if CF_CLEARANCE:
    session.cookies.set("cf_clearance", CF_CLEARANCE, domain=".fantrax.com")
session.cookies.set("ui", "xvxwu418k69yvpe7", domain=".fantrax.com")

def fetch(method, data, refUrl):
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
    responses = result.get("responses", [])
    if len(responses) < 2:
        print("ERROR: Not enough responses")
        print(json.dumps(result, indent=2))
        exit(1)
    if "WARNING_NOT_LOGGED_IN" in str(responses[1]):
        print(f"ERROR: {method} not logged in")
        print(json.dumps(responses[1], indent=2))
        exit(1)
    return responses[1]

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Fetch standings
print("Fetching standings...")
standings = fetch(
    "getStandings",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings"
)
save("standings.json", standings)

# Fetch rosters
print("Fetching rosters...")
rosters = fetch(
    "getRosters",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/rosters"
)
save("rosters.json", rosters)

# Fetch free agents - hitters
print("Fetching free agent hitters...")
fa_hitting = fetch(
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
fa_pitching = fetch(
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
