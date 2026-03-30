import requests
import json
import os

LEAGUE_ID = "x4rx6jlimiytz3co"

cookies = {
    "cookie": os.environ["FANTRAX_COOKIE"],
    "cf_clearance": os.environ["FANTRAX_CF_CLEARANCE"],
    "__cf_bm": os.environ["FANTRAX_CF_BM"],
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": f"https://www.fantrax.com/fantasy/league/{LEAGUE_ID}/home",
    "Content-Type": "application/json",
}

def fetch(endpoint, payload):
    url = f"https://www.fantrax.com/fxpa/req?leagueId={LEAGUE_ID}"
    body = {"msgs": [{"method": endpoint, "data": payload}]}
    r = requests.post(url, headers=headers, cookies=cookies, json=body)
    print(f"{endpoint}: {r.status_code}")
    return r.json()

def save(filename, data):
    os.makedirs("data", exist_ok=True)
    with open(f"data/{filename}", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved data/{filename}")

standings = fetch("getStandings", {"leagueId": LEAGUE_ID})
save("standings.json", standings)

rosters = fetch("getRosters", {"leagueId": LEAGUE_ID})
save("rosters.json", rosters)

free_agents = fetch("getAvailablePlayers", {
    "leagueId": LEAGUE_ID,
    "scoringCategoryType": "5",
    "statusOrTeamFilter": "FA",
    "pageNumber": "0",
})
save("free_agents.json", free_agents)

print("All done!")
