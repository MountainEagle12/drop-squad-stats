"""Bygger dashboard/standalone.html: samme side som dashboardet, men med alle data
indlejret, så den kan ses uden login. Kør efter build_dashboard_data.py."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "dashboard" / "index.html"
OUT = ROOT / "dashboard" / "standalone.html"
PAGES = ROOT / "docs" / "index.html"
DATA = ROOT / "data" / "dashboard"
PAGES_HEAD = """<!doctype html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>body { margin: 0; font-size: 14px; } img { max-width: 100%; } [hidden] { display: none !important; }</style>
</head>
<body>
"""

HEAD = """<title>DROP Squad Stats</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600&family=Barlow:wght@400;500;600&display=swap">
<style>
/* HUD-agtig opstilling: smal overskriftsskrift, stille flader, amber som spillets markeringsfarve */
:root {
  --bg: #f3f4f1; --panel: #ffffff; --fg: #1c211f; --muted: #5b6460; --line: #d9ddd8; --ok: #18794e; --warn: #9a6700; --bad: #b42318;
  --grid: #e5e8e3; --chart-muted: #9aa39e; --s1: #b87700; --s2: #2563c9; --s3: #0e8f6e; --s4: #c4387f; --shadow: 0 4px 16px rgb(20 30 25 / .14);
  --font-anthropic-sans: "Barlow", "Segoe UI", system-ui, sans-serif;
  --font-anthropic-serif: "Barlow Condensed", "Arial Narrow", "Segoe UI", sans-serif;
  --cds-font-size-caption: .8125rem; --cds-font-size-body: 1rem; --cds-font-size-heading: 1.1rem; --cds-font-size-title: 2rem;
  --cds-font-weight-medium: 600;
  --cds-gap-xs: .25rem; --cds-gap-sm: .5rem; --cds-gap-md: .875rem; --cds-gap-lg: 1.25rem; --cds-gap-xl: 2rem;
  --cds-pad-xs: .3rem; --cds-pad-sm: .55rem; --cds-pad-md: .875rem; --cds-pad-lg: 1.1rem;
  --cds-radius: 6px; --cds-dur-slow: .3s;
  --color-fg: var(--fg); --color-fg-muted: var(--muted); --color-bg: var(--bg); --color-panel: var(--panel); --color-border-line: var(--line);
  --color-ok: var(--ok); --color-warn: var(--warn); --color-bad: var(--bad);
  --cds-chart-grid: var(--grid); --cds-chart-muted: var(--chart-muted); --cds-surface-popover: var(--panel); --cds-border: var(--line);
  --cds-shadow-popover: var(--shadow); --cds-text-secondary: var(--muted);
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #111413; --panel: #1a1e1c; --fg: #eceeea; --muted: #a0a9a4; --line: #2f3532; --ok: #5fd39b; --warn: #e8b84b; --bad: #f28b82;
  --grid: #2a2f2c; --chart-muted: #6d7671; --s1: #f2a900; --s2: #6ea8fe; --s3: #3ccb9f; --s4: #f07cb4; --shadow: 0 4px 16px rgb(0 0 0 / .5); color-scheme: dark;
} }
:root[data-theme="dark"] {
  --bg: #111413; --panel: #1a1e1c; --fg: #eceeea; --muted: #a0a9a4; --line: #2f3532; --ok: #5fd39b; --warn: #e8b84b; --bad: #f28b82;
  --grid: #2a2f2c; --chart-muted: #6d7671; --s1: #f2a900; --s2: #6ea8fe; --s3: #3ccb9f; --s4: #f07cb4; --shadow: 0 4px 16px rgb(0 0 0 / .5); color-scheme: dark;
}
body { background: var(--bg); color: var(--fg); font-family: var(--font-anthropic-sans); line-height: 1.45; }
.ds-wrap { box-sizing: border-box; max-width: 1240px; margin-inline: auto; padding-block: 1.5rem 3rem; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.ds-title { font-size: 2.4rem; letter-spacing: .01em; line-height: 1.05; }
.ds-title, .ds-tile-value { font-weight: 600 !important; }
.dash-select { font: inherit; font-size: var(--cds-font-size-caption); color: var(--fg); background-color: var(--panel); border: 1px solid var(--line); border-radius: var(--cds-radius); padding: var(--cds-pad-xs) var(--cds-pad-sm); }
:is(button, select, input):focus-visible { outline: 2px solid var(--s1); outline-offset: 1px; }
</style>
"""

SHIM = """<script>
window.dash = (() => {
  const kilder = JSON.parse(document.getElementById('ds-data').textContent);
  const params = {};
  const draws = new Map();
  const lyttere = [];
  let klar = false;
  let ventende = false;
  const tegn = (el, fn) => { if (!el.closest('[hidden]')) fn(el); };
  const run = () => {
    ventende = false;
    if (!klar) return;
    lyttere.forEach((f) => f());
    draws.forEach((fn, navn) => document.querySelectorAll(`[data-draw="${navn}"]`).forEach((el) => tegn(el, fn)));
  };
  const senere = () => { if (!ventende) { ventende = true; requestAnimationFrame(run); } };
  addEventListener('resize', senere);
  return {
    colors: ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)'],
    data: (id) => ({status: 'ok', data: kilder[id] ?? [], message: '', refreshing: false, meta: []}),
    params: () => ({...params}),
    setParams: (p) => { Object.entries(p).forEach(([k, v]) => { if (v == null) delete params[k]; else params[k] = v; }); senere(); },
    setLink: (n) => { try { history.replaceState(null, '', '#' + n); } catch (e) { /* adressen er ikke vigtig */ } },
    draw: (navn, fn) => { if (fn) draws.set(navn, fn); else document.querySelectorAll(`[data-draw="${navn}"]`).forEach((el) => tegn(el, draws.get(navn))); },
    onData: (fn) => lyttere.push(fn),
    start: () => { klar = true; run(); },
  };
})();
</script>
"""


def main():
    src = SRC.read_text(encoding="utf-8").replace('<meta name="dash-one-writer">\n', "")
    style_end = src.index("</style>") + len("</style>")
    style, rest = src[:style_end], src[style_end:]
    i = rest.rindex("<script>")
    markup, script = rest[:i], rest[i + len("<script>"):rest.rindex("</script>")]

    data = {n: json.loads((DATA / f"{n}.json").read_text(encoding="utf-8"))
            for n in ("team_matches", "match_players", "player_stats", "meta")}
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    page = (HEAD + style + '\n<main class="ds-wrap">' + markup + "</main>\n"
            + f'<script type="application/json" id="ds-data">{blob}</script>\n'
            + SHIM
            + '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
            + "<script>\n(() => {" + script + "})();\ndash.start();\n</script>\n")

    defined = set(re.findall(r"(--[\w-]+)\s*:", HEAD))
    used = set(re.findall(r"var\((--[\w-]+)", src))
    missing = used - defined
    if missing:
        raise SystemExit(f"Mangler tokens: {sorted(missing)}")
    OUT.write_text(page, encoding="utf-8")
    PAGES.parent.mkdir(exist_ok=True)
    PAGES.write_text(PAGES_HEAD + page + "</body>" + chr(10) + "</html>" + chr(10), encoding="utf-8")
    print(f"{OUT} {len(page.encode()) // 1024} KB, plus {PAGES}")


if __name__ == "__main__":
    main()
