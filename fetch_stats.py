"""Henter PUBG-stats for holdet og gemmer dem i data/.

Kør:  py fetch_stats.py

- data/snapshot.json       seneste livstids-, sæson- og ranked-stats
- data/matches/<id>.json   kampe (gemmes permanent, API'et sletter dem efter 14 dage)
- data/history/<dato>.json dagligt snapshot, så udviklingen kan følges
"""
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
PLAYERS = ["El-Champo", "StrawberryBuun", "Abilden", "MountainEagle_12"]
SHARD = "steam"
BASE = f"https://api.pubg.com/shards/{SHARD}"


def api_key():
    if os.environ.get("PUBG_API_KEY"):  # GitHub Actions
        return os.environ["PUBG_API_KEY"].strip()
    for line in (ROOT / "key.env").read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("PUBG_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("PUBG_API_KEY mangler i key.env")


KEY = api_key()


def get(url, auth=True):
    headers = {"Accept": "application/vnd.api+json", "Accept-Encoding": "identity"}
    if auth:
        headers["Authorization"] = f"Bearer {KEY}"
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # rate limit: 10 kald i minuttet
                print("  rate limit, venter 60 sek ...", flush=True)
                time.sleep(60)
                continue
            if e.code == 404:
                return None
            raise
    raise SystemExit("Gav op efter gentagne rate limits")


def slim(m):
    """Beholder kun det, dashboardet bruger: rå kampe fylder ellers hundredvis af KB."""
    inc = {x["id"]: x for x in m["included"]}
    rosters = [x for x in m["included"] if x["type"] == "roster"]
    keep, out = [], []
    for ro in rosters:
        ids = [p["id"] for p in ro["relationships"]["participants"]["data"]]
        if any(inc[i]["attributes"]["stats"]["name"] in PLAYERS for i in ids):
            keep += [inc[i] for i in ids]
            out.append(ro)
        else:
            out.append({"type": "roster", "id": ro["id"], "relationships": {"participants": {"data": []}}})
    return {"data": {"id": m["data"]["id"], "attributes": m["data"]["attributes"]}, "included": out + keep}


def changed(snapshot):
    """True hvis noget andet end hentetidspunktet er ændret."""
    path = DATA / "snapshot.json"
    if not path.exists():
        return True
    old = json.loads(path.read_text(encoding="utf-8"))
    old.pop("fetchedAt", None)
    return old != {k: v for k, v in snapshot.items() if k != "fetchedAt"}


def main():
    (DATA / "matches").mkdir(parents=True, exist_ok=True)
    (DATA / "history").mkdir(parents=True, exist_ok=True)

    names = urllib.parse.quote(",".join(PLAYERS), safe=",")
    res = get(f"{BASE}/players?filter[playerNames]={names}")
    players = res["data"]
    found = {p["attributes"]["name"] for p in players}
    print("Fundet:", sorted(found))
    missing = set(PLAYERS) - found
    if missing:
        print("IKKE fundet:", sorted(missing))

    seasons = get(f"{BASE}/seasons")["data"]
    current = next(s["id"] for s in seasons if s["attributes"]["isCurrentSeason"])
    print("Aktuel sæson:", current)

    snapshot = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": current,
        "players": {},
    }
    match_ids = set()
    for p in players:
        name, pid = p["attributes"]["name"], p["id"]
        print("Henter", name, flush=True)
        ids = [m["id"] for m in p["relationships"]["matches"]["data"]]
        match_ids.update(ids)
        lifetime = get(f"{BASE}/players/{pid}/seasons/lifetime")
        season = get(f"{BASE}/players/{pid}/seasons/{current}")
        ranked = get(f"{BASE}/players/{pid}/seasons/{current}/ranked")
        snapshot["players"][name] = {
            "id": pid,
            "clanId": p["attributes"].get("clanId"),
            "banType": p["attributes"].get("banType"),
            "matchIds": ids,
            "lifetime": lifetime and lifetime["data"]["attributes"]["gameModeStats"],
            "season": season and season["data"]["attributes"]["gameModeStats"],
            "ranked": ranked and ranked["data"]["attributes"].get("rankedGameModeStats"),
        }

    if changed(snapshot):
        (DATA / "snapshot.json").write_text(json.dumps(snapshot, indent=1), encoding="utf-8")
        (DATA / "history" / f"{date.today().isoformat()}.json").write_text(json.dumps(snapshot), encoding="utf-8")
    else:
        print("Ingen ændringer i stats")

    new = 0
    for mid in sorted(match_ids):
        path = DATA / "matches" / f"{mid}.json"
        if path.exists():
            continue
        m = get(f"{BASE}/matches/{mid}", auth=False)  # kampkaldet tæller ikke med i rate limit
        if m:
            path.write_text(json.dumps(slim(m), separators=(",", ":")), encoding="utf-8")
            new += 1
    print(f"Kampe: {len(match_ids)} i API'et, {new} nye gemt")


if __name__ == "__main__":
    main()
