import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

USERNAME = os.environ["FANTRAX_USERNAME"]
PASSWORD = os.environ["FANTRAX_PASSWORD"]

print(f"Username loaded: {USERNAME[:3]}***")

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://www.fantrax.com",
    "Referer": "https://www.fantrax.com/login",
})

def login():
    # First visit the login page to get initial cookies
    session.get("https://www.fantrax.com/login")
    
    url = "https://www.fantrax.com/fxpa/req?leagueId="
    body = {
        "msgs": [{"method": "login", "data": {
            "username": USERNAME,
            "password": PASSWORD,
            "stayLoggedIn": True
        }}],
        "uiv": 3,
        "refUrl": "https://www.fantrax.com/login",
        "dt": 0,
        "at": 0,
        "tz": "America/Denver",
        "v": "180.1.2"
    }
    r = session.post(url, json=body)
    print(f"Login status: {r.status_code}")
    data = r.json()
    print("Login response:")
    print(json.dumps(data, indent=2))
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
    result = r.json()
    print(json.dumps(result, indent=2))
    return result

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

login()

standings = fetch(
    "getStandings",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings"
)
save("standings.json", standings)

print("Done!")
