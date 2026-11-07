"""Laver dashboardets datafiler ud fra data/snapshot.json og data/matches/.

Kør efter fetch_stats.py:  py build_dashboard_data.py
Output i data/dashboard/: player_stats.json, match_players.json, team_matches.json, meta.json
"""
import json
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
OUT = DATA / "dashboard"
PLAYERS = ["El-Champo", "StrawberryBuun", "Abilden", "MountainEagle_12"]
MAPS = {
    "Baltic_Main": "Erangel", "Erangel_Main": "Erangel", "Desert_Main": "Miramar",
    "DihorOtok_Main": "Vikendi", "Neon_Main": "Rondo", "Tiger_Main": "Taego",
    "Chimera_Main": "Paramo", "Summerland_Main": "Karakin", "Savage_Main": "Sanhok",
    "Kiki_Main": "Deston", "Heaven_Main": "Haven",
}
MODES = {
    "squad": "Squad TPP", "squad-fpp": "Squad FPP", "duo": "Duo TPP",
    "duo-fpp": "Duo FPP", "solo": "Solo TPP", "solo-fpp": "Solo FPP",
}
SUM = ["roundsPlayed", "wins", "top10s", "kills", "assists", "damageDealt", "headshotKills",
       "losses", "revives", "dBNOs", "timeSurvived", "teamKills", "roadKills"]


def rates(row):
    r, l = row["kampe"], max(row["losses"], 1)
    row["kd"] = round(row["kills"] / l, 2)
    row["win_pct"] = round(row["wins"] / r, 4) if r else 0
    row["top10_pct"] = round(row["top10"] / r, 4) if r else 0
    row["adr"] = round(row["skade"] / r, 1) if r else 0
    row["hs_pct"] = round(row["headshots"] / row["kills"], 4) if row["kills"] else 0
    row["skade"] = round(row["skade"])
    return row


def player_rows(snapshot):
    rows = []
    for scope, scope_label in (("lifetime", "Livstid"), ("season", "Sæson")):
        for name in PLAYERS:
            modes = snapshot["players"][name][scope] or {}
            total = defaultdict(float)
            longest = 0
            for mode, st in modes.items():
                if not st.get("roundsPlayed"):
                    continue
                longest = max(longest, st["longestKill"])
                for k in SUM:
                    total[k] += st[k]
                rows.append(make(scope, scope_label, mode, MODES.get(mode, mode), name, st, st["longestKill"]))
            if total:
                rows.append(make(scope, scope_label, "all", "Alle", name, total, longest))
    return rows


def make(scope, scope_label, mode, mode_label, name, st, longest):
    return rates({
        "key": f"{scope}|{mode}|{name}", "periode": scope_label, "scope": scope, "mode": mode,
        "tilstand": mode_label, "spiller": name, "kampe": int(st["roundsPlayed"]),
        "wins": int(st["wins"]), "top10": int(st["top10s"]), "kills": int(st["kills"]),
        "assists": int(st["assists"]), "skade": st["damageDealt"], "headshots": int(st["headshotKills"]),
        "losses": int(st["losses"]), "revives": int(st["revives"]), "knocks": int(st["dBNOs"]),
        "team_kills": int(st["teamKills"]), "laengste_kill": round(longest),
        "timer": round(st["timeSurvived"] / 3600, 1),
    })


def match_rows():
    players, teams = [], []
    skipped = 0
    for f in sorted((DATA / "matches").glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        a = m["data"]["attributes"]
        if a["matchType"] != "official":  # træningsbanen tæller ikke
            skipped += 1
            continue
        inc = {x["id"]: x for x in m["included"]}
        rosters = [x for x in m["included"] if x["type"] == "roster"]
        for ro in rosters:
            members = [inc[p["id"]]["attributes"]["stats"] for p in ro["relationships"]["participants"]["data"] if p["id"] in inc]
            ours = [s for s in members if s["name"] in PLAYERS]
            if not ours:
                continue
            rank = ro["attributes"]["stats"]["rank"]
            won = ro["attributes"]["won"] == "true"
            lineup = sorted(s["name"] for s in ours)
            mid = f"{m['data']['id']}|{ro['id']}"
            teams.append({
                "id": mid, "dato": a["createdAt"], "kort": MAPS.get(a["mapName"], a["mapName"]),
                "tilstand": MODES.get(a["gameMode"], a["gameMode"]), "mode": a["gameMode"],
                "placering": rank, "hold_i_alt": len(rosters), "vundet": won,
                "antal_af_os": len(ours), "spillere": ", ".join(lineup),
                "hold_kills": sum(s["kills"] for s in members),
                "hold_skade": round(sum(s["damageDealt"] for s in members)),
                "varighed_min": round(a["duration"] / 60),
            })
            for s in ours:
                players.append({
                    "key": f"{mid}|{s['name']}", "match": mid, "dato": a["createdAt"],
                    "kort": MAPS.get(a["mapName"], a["mapName"]), "mode": a["gameMode"],
                    "spiller": s["name"], "placering": rank, "vundet": won, "antal_af_os": len(ours),
                    "kills": s["kills"], "assists": s["assists"], "skade": round(s["damageDealt"]),
                    "knocks": s["DBNOs"], "headshots": s["headshotKills"], "revives": s["revives"],
                    "overlevet_min": round(s["timeSurvived"] / 60, 1),
                    "laengste_kill": round(s["longestKill"]),
                    "gaa_km": round(s["walkDistance"] / 1000, 2),
                })
    teams.sort(key=lambda r: r["dato"], reverse=True)
    players.sort(key=lambda r: r["dato"], reverse=True)
    return players, teams, skipped


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshot = json.loads((DATA / "snapshot.json").read_text(encoding="utf-8"))
    stats = player_rows(snapshot)
    players, teams, skipped = match_rows()
    for name, rows in (("player_stats", stats), ("match_players", players), ("team_matches", teams)):
        (OUT / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    meta = [{
        "hentet": snapshot["fetchedAt"], "saeson": snapshot["season"],
        "foerste_kamp": min(t["dato"] for t in teams), "seneste_kamp": max(t["dato"] for t in teams),
        "kampe": len({t["id"].split("|")[0] for t in teams}), "traening_fravalgt": skipped,
    }]
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=0), encoding="utf-8")
    print(meta[0], len(stats), len(players), len(teams))


if __name__ == "__main__":
    main()
