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
})

# Log in to Fantrax
def login():
    url = "https://www.fantrax.com/fxpa/req?leagueId="
    body = {
        "msgs": [{"method": "login", "data": {
            "username": USERNAME,
            "password": PASSWORD,
            "stayLoggedIn": True
        }}],
        "uiv": 3,
        "refUrl": "",
        "dt": 0,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    print(f"Login: {r.status_code}")
    data = r.json()
    if "WARNING_NOT_LOGGED_IN" in str(data):
        print("Login failed!")
        print(json.dumps(data, indent=2))
        exit(1)
    print("Login successful!")
    return data

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
    return r.json()

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

# Login first
login()

# Fetch standings
standings = fetch(
    "getStandings",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings"
)
save("standings.json", standings)

# Fetch rosters
rosters = fetch(
    "getRosters",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/rosters"
)
save("rosters.json", rosters)

# Fetch free agents (hitters)
free_agents_hitting = fetch(
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
save("free_agents_hitting.json", free_agents_hitting)

# Fetch free agents (pitchers)
free_agents_pitching = fetch(
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
save("free_agents_pitching.json", free_agents_pitching)

print("All done!")
