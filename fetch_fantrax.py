Login works perfectly but the session cookie isn't carrying over. I can see exactly what's happening — Fantrax sets a session cookie after login that we need to capture and reuse. Let me print the cookies after login to see what we get.
Replace fetch_fantrax.py with this:
pythonimport requests
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
    "Referer": "https://www.fantrax.com/login",
})

def login():
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
    
    # Print all cookies we have after login
    print("Cookies after login:")
    for cookie in session.cookies:
        print(f"  {cookie.name} = {cookie.value[:30]}... (domain: {cookie.domain})")
    
    data = r.json()
    if "WARNING_NOT_LOGGED_IN" in str(data):
        print("Login failed!")
        exit(1)
    print("Login successful!")

def fetch(method, data, refUrl=None):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    
    # Print cookies being sent
    print(f"Cookies being sent for {method}:")
    for cookie in session.cookies:
        print(f"  {cookie.name} (domain: {cookie.domain})")
    
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
        print(f"ERROR: {method} returned not logged in")
        exit(1)
    return result

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

login()

print("Fetching standings...")
standings = fetch(
    "getStandings",
    {"leagueId": LEAGUE_ID},
    f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/standings"
)
save("standings.json", standings)

print("All done!")
