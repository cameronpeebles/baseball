import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Referer": f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/home",
})

# Set long-lived cookies
session.cookies.set("FX_RM", os.environ["FANTRAX_FX_RM"], domain=".fantrax.com")
session.cookies.set("cf_clearance", os.environ["FANTRAX_CF_CLEARANCE"], domain=".fantrax.com")
session.cookies.set("ui", "xvxwu418k69yvpe7", domain=".fantrax.com")

def fetch(method, data, refUrl=None):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    body = {
        "msgs": [{"method": method, "data": data}],
        "uiv": 3,
        "refUrl": refUrl or f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/home",
        "dt": 0,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    print(f"{method}: {r.status_code}")
    result = r.json()
    if "WARNING_NOT_LOGGED_IN" in str(result):
        print("ERROR: Cookies have expired - please update GitHub Secrets with fresh cookies")
        print(json.dumps(result, indent=2))
        exit(1)
    return result

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
