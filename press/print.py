#!/usr/bin/env python3
"""The Daily Commit press.

Typesets this profile's front page as SVG plates, one light and one dark per
plate, then writes README.md around them. Live numbers come from the GitHub
GraphQL API; when the wire is down, the last good copy in press/wire.json is
reprinted instead, so a bad morning never breaks the paper.

    pip install fonttools brotli
    GITHUB_TOKEN=... python3 press/print.py

Copy lives in press/content.py. Never hand-edit README.md or edition/.
"""

import base64
import io
import json
import math
import os
import subprocess
import sys
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "edition")
sys.path.insert(0, HERE)
import content as C  # noqa: E402

W = 840  # GitHub's README column, near enough; every plate scales to 100%.
# Phones get their own plates, set at 400 wide so they print near 1:1. The
# switch is a width query on <picture>; see pic() for why it's spelled oddly.
M = 400
PHONE = "(max-width: 640px)"
PHONE_COLUMN = 358  # the README column on a 390px phone
IST = ZoneInfo("Asia/Kolkata")

THEMES = {
    "light": {
        "ink": "#16161A", "muted": "#66666A", "hair": "rgba(22,22,26,.18)",
        "band": "#16161A", "on-band": "#FAFAF8", "wash": "rgba(22,22,26,.04)",
        "zero": "rgba(22,22,26,.14)", "screen": "rgba(255,255,255,.22)",
        "paper": "#FFFFFF", "edition": "MORNING EDITION",
    },
    "dark": {
        "ink": "#E9E7E1", "muted": "#9C9A94", "hair": "rgba(233,231,225,.2)",
        "band": "#E9E7E1", "on-band": "#101114", "wash": "rgba(233,231,225,.05)",
        "zero": "rgba(233,231,225,.16)", "screen": "rgba(0,0,0,.28)",
        "paper": "#0D1117", "edition": "NIGHT EDITION",
    },
}


# ── Type ────────────────────────────────────────────────────────────────────

class Face:
    """One static font: measures text, and subsets itself per plate."""

    def __init__(self, key):
        self.key = key
        with open(os.path.join(HERE, "fonts", f"{key}.ttf"), "rb") as fh:
            self.raw = fh.read()
        tt = TTFont(io.BytesIO(self.raw))
        self.cmap = tt.getBestCmap()
        self.adv = {g: m[0] for g, m in tt["hmtx"].metrics.items()}
        self.upm = tt["head"].unitsPerEm

    def width(self, s, size, track=0.0):
        units = sum(self.adv[self.cmap.get(ord(ch), self.cmap[32])] for ch in s)
        return units * size / self.upm + track * size * len(s)

    def woff2(self, chars):
        tt = TTFont(io.BytesIO(self.raw), recalcTimestamp=False)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga", "tnum"]
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)) + " ")
        sub.subset(tt)
        buf = io.BytesIO()
        tt.save(buf)
        return base64.b64encode(buf.getvalue()).decode()


FACES = {k: Face(k) for k in ("display", "head", "text", "textbold", "italic", "label", "mono")}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap(face, s, size, width, track=0.0):
    lines, cur = [], ""
    for word in s.split(" "):
        test = f"{cur} {word}" if cur else word
        if cur and FACES[face].width(test, size, track) > width:
            lines.append(cur)
            cur = word
        else:
            cur = test
    return lines + [cur]


def clamp(face, lines, n, size, width):
    if len(lines) <= n:
        return lines
    last = lines[n - 1]
    while FACES[face].width(last + "…", size) > width:
        last = last.rsplit(" ", 1)[0]
    return lines[: n - 1] + [last.rstrip(",;:—– ") + "…"]


def wrap_runs(runs, size, width_at):
    """Wrap mixed-face copy. runs: [(text, face)]; width_at(i) → line width."""
    words = [(w, f) for text, f in runs for w in text.split(" ") if w]
    lines, cur, used = [], [], 0.0
    for w, f in words:
        gap = FACES[f].width(" ", size) if cur else 0
        ww = FACES[f].width(w, size)
        if cur and used + gap + ww > width_at(len(lines)):
            lines.append(cur)
            cur, used, gap = [], 0.0, 0
        cur.append((w, f))
        used += gap + ww
    return lines + [cur]


# ── Plates ──────────────────────────────────────────────────────────────────

class Plate:
    """One SVG. Phone plates (`mobile`) print on solid paper: GitHub's theme
    script can't retheme them, so they must stay legible on either page."""

    def __init__(self, name, theme, title, width=None, mobile=False):
        self.name, self.theme, self.title, self.mobile = name, theme, title, mobile
        self.w = width or (M if mobile else W)
        self.t = THEMES[theme]
        self.body, self.defs, self.css = [], [], []
        self.used = defaultdict(set)

    def add(self, *parts):
        self.body.extend(parts)

    def text(self, x, y, s, face, size, color="ink", anchor="start", track=0.0, cls="", style=""):
        self.used[face].update(s)
        classes = f"f-{face} c-{color} {cls}".strip()
        attrs = f'x="{x:.1f}" y="{y:.1f}" class="{classes}" font-size="{size}"'
        if track:
            attrs += f' letter-spacing="{track * size:.2f}"'
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        if style:
            attrs += f' style="{style}"'
        self.add(f"<text {attrs}>{esc(s)}</text>")

    def runs(self, x, y, line, size, color="ink", style=""):
        """One line of mixed-face words from wrap_runs."""
        spans, prev = [], None
        for i, (w, f) in enumerate(line):
            s = (" " if i else "") + w
            self.used[f].update(s)
            if f == prev:
                spans[-1][1] += s
            else:
                spans.append([f, s])
            prev = f
        inner = "".join(f'<tspan class="f-{f}">{esc(s)}</tspan>' for f, s in spans)
        st = f' style="{style}"' if style else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="c-{color}" font-size="{size}"{st}>{inner}</text>')

    def line(self, x1, y1, x2, y2, color="ink", w=1, cls="", extra=""):
        classes = f"s-{color} {cls}".strip()
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{classes}" stroke-width="{w}" {extra}/>')

    def rect(self, x, y, w, h, color="band", extra=""):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="c-{color}" {extra}/>')

    def chip(self, x, y, label):
        """Black section chip, e.g. [LEAD STORY]. Returns its right edge."""
        w = FACES["label"].width(label, 9.5, 0.16) + 16
        self.rect(x, y - 13, w, 19)
        self.text(x + 8, y, label, "label", 9.5, "on-band", track=0.16)
        return x + w

    def section(self, label, aside="", right="", y=26):
        """Thick rule, chip, kicker, and an optional right-hand slug."""
        self.line(0, 1, self.w, 1, w=2)
        x = self.chip(0, y, label)
        if aside:
            self.text(x + 12, y, aside, "label", 9.5, "muted", track=0.16)
        if right:
            self.text(self.w, y, right, "label", 9.5, "muted", anchor="end", track=0.16)

    def image(self, x, y, w, h, slug, delay=0.0):
        with open(os.path.join(HERE, "img", f"{slug}.jpg"), "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        clip = f"clip-{slug}"
        self.defs.append(f'<clipPath id="{clip}"><rect x="{x}" y="{y}" width="{w}" height="{h}"/></clipPath>')
        self.add(
            f'<g clip-path="url(#{clip})">'
            f'<image href="data:image/jpeg;base64,{data}" x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid slice" class="develop" style="animation-delay:{delay:.2f}s"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#halftone)"/></g>'
        )
        self.add(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" fill="none" class="s-ink" stroke-width="1"/>')
        if "halftone" not in "".join(self.defs):
            self.defs.append(
                '<pattern id="halftone" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<circle cx="1.5" cy="1.5" r=".7" class="c-screen"/></pattern>'
            )

    def svg(self, h):
        t = self.t
        fonts = "".join(
            f'@font-face{{font-family:dc-{k};src:url(data:font/woff2;base64,{FACES[k].woff2(chars)}) format("woff2")}}'
            f".f-{k}{{font-family:dc-{k}}}"
            for k, chars in sorted(self.used.items())
        )
        colors = "".join(
            f".c-{k}{{fill:{t[k]}}}.s-{k}{{stroke:{t[k]}}}"
            for k in ("ink", "muted", "hair", "band", "on-band", "wash", "zero", "screen", "paper")
        )
        paper = '<rect width="100%" height="100%" class="c-paper"/>' if self.mobile else ""
        css = (
            fonts + colors
            + "text{font-kerning:normal;font-variant-ligatures:common-ligatures}"
            + "@keyframes ink{from{opacity:0}to{opacity:1}}"
            + "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
            + "@keyframes develop{0%{opacity:0;filter:blur(8px) contrast(.4) brightness(1.5)}"
            + "60%{opacity:1}100%{opacity:1;filter:none}}"
            + ".ink{animation:ink .5s ease-out both}.rise{animation:rise .7s cubic-bezier(.2,.7,.2,1) both}"
            + ".develop{animation:develop 2.2s ease-out both}"
            + "".join(self.css)
            + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{self.w}" height="{h:.0f}" '
            f'viewBox="0 0 {self.w} {h:.0f}" role="img" aria-label="{esc(self.title)}">'
            f"<title>{esc(self.title)}</title><style>{css}</style>"
            f'<defs>{"".join(self.defs)}</defs>{paper}{"".join(self.body)}</svg>'
        )

    def save(self, h):
        folder = os.path.join(OUT, "mobile") if self.mobile else OUT
        with open(os.path.join(folder, f"{self.name}-{self.theme}.svg"), "w") as fh:
            fh.write(self.svg(h))


# ── The wire (live data) ───────────────────────────────────────────────────

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes { name stargazerCount }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def token():
    for var in ("PRESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def wire():
    cache = os.path.join(HERE, "wire.json")
    try:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": QUERY, "variables": {"login": C.LOGIN}}).encode(),
            headers={"Authorization": f"bearer {token()}", "User-Agent": "the-daily-commit-press"},
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            user = json.load(res)["data"]["user"]
        cal = user["contributionsCollection"]["contributionCalendar"]
        data = {
            "followers": user["followers"]["totalCount"],
            "repos": user["repositories"]["totalCount"],
            "stars": {r["name"]: r["stargazerCount"] for r in user["repositories"]["nodes"]},
            "total": cal["totalContributions"],
            "weeks": [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]],
        }
        with open(cache, "w") as fh:
            json.dump(data, fh)
        return data
    except Exception as err:  # the paper still goes out; yesterday's numbers stand
        note = f"wire down ({err}); reprinting yesterday's numbers from {cache}"
        print(f"::warning::{note}" if os.environ.get("GITHUB_ACTIONS") else note, file=sys.stderr)
        with open(cache) as fh:
            return json.load(fh)


def ledger(weeks):
    days = [d for w in weeks for d in w]
    counts = [c for _, c in days]
    # Today's column is still being written at press time; don't let it break the streak.
    trail = counts[:-1] if counts and counts[-1] == 0 else counts
    current = 0
    for c in reversed(trail):
        if not c:
            break
        current += 1
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    busiest = max(days, key=lambda d: d[1]) if days else ("", 0)
    return {"current": current, "longest": longest, "busiest": busiest, "week": sum(counts[-7:])}


def forecast(week):
    if week == 0:
        return "Quiet on the wire. Expect a downpour of commits once the current refactor lands."
    if week < 6:
        return "Light commits through midweek, with scattered refactors toward the weekend."
    if week < 20:
        return "Steady commits through Friday, with scattered hotfixes after deploy."
    return "Heavy commit activity across the region. Expect green builds and a flood of PRs."


# ── The front page ──────────────────────────────────────────────────────────

def nameplate(p, x, y, size):
    """Each letter inks in on its own, like type hitting the sheet."""
    p.used["display"].update(C.PAPER)
    spans = "".join(
        f'<tspan class="ink" style="animation-delay:{.25 + i * .055:.3f}s">{esc(ch)}</tspan>'
        for i, ch in enumerate(C.PAPER)
    )
    p.add(
        f'<text x="{x}" y="{y:.1f}" class="f-display c-ink" font-size="{size:.1f}" '
        f'letter-spacing="{-0.02 * size:.2f}" text-anchor="middle">{spans}</text>'
    )
    p.css.append(
        "@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        ".draw{stroke-dasharray:1;animation:draw 1s cubic-bezier(.6,0,.2,1) both}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}.pulse{animation:pulse 1.6s ease-in-out infinite}"
    )


def tagline(p, y, size, reach):
    tag_w = FACES["label"].width(C.TAGLINE, size, 0.22)
    p.text(p.w / 2, y, C.TAGLINE, "label", size, "ink", "middle", 0.22, "ink", "animation-delay:1.2s")
    for side in (-1, 1):
        x0 = p.w / 2 + side * (tag_w / 2 + 12)
        p.line(x0, y - 3.5, x0 + side * reach, y - 3.5, cls="draw", extra='pathLength="1" style="animation-delay:1.3s"')


def ears(p, ed, top, motto_w, motto_size, status_size):
    """The motto box (left) and the CI weather box with the hire flag (right)."""
    box_h = motto_size * 3.55
    p.add(f'<rect x=".5" y="{top + .5}" width="{motto_w}" height="{box_h:.1f}" fill="none" class="s-ink ink" style="animation-delay:1s"/>')
    for i, ln in enumerate(C.MOTTO):
        p.text(motto_w / 2 + .5, top + box_h / 2 - 2 + i * motto_size * 1.26, ln, "italic", motto_size, "ink", "middle",
               cls="ink", style="animation-delay:1.05s")
    lead = status_size * 1.6
    p.add(f'<circle cx="{p.w - FACES["label"].width("AVAILABLE FOR WORK", status_size, .16) - 8:.1f}" '
          f'cy="{top + 12 - status_size * .36:.1f}" r="3" class="c-ink pulse"/>')
    p.text(p.w, top + 12, "AVAILABLE FOR WORK", "label", status_size, "ink", "end", 0.16, "ink", "animation-delay:1s")
    p.text(p.w, top + 12 + lead, "BUILD ✓ PASSING", "mono", status_size, "muted", "end", 0.06, "ink", "animation-delay:1.12s")
    p.text(p.w, top + 12 + 2 * lead, f"STARS {ed['stars']} · SUBS {ed['followers']}", "mono", status_size, "muted", "end", 0.06,
           "ink", "animation-delay:1.24s")
    return top + box_h


def masthead(theme, ed):
    p = Plate("masthead", theme, f"{C.PAPER} — {ed['edition_line']}")
    folio = f"{p.t['edition']} · {ed['long']} · VOL. {ed['vol']} · NO. {ed['issue']:,} · PRICE: FREE (MIT LICENSE)"
    p.line(0, 4.5, W, 4.5, "hair")
    p.text(W / 2, 20, folio, "mono", 9.5, "muted", "middle", 0.1, "ink")
    p.line(0, 30.5, W, 30.5, "hair")
    p.text(W / 2, 58, f"KOLKATA · GITHUB.COM/{C.LOGIN.upper()}", "label", 9.5, "muted", "middle", 0.22, "ink", "animation-delay:.2s")
    nameplate(p, W / 2, 128, min(86, 520 / FACES["display"].width(C.PAPER, 1)))
    tagline(p, 162, 10, 120)
    ears(p, ed, 86, 142, 13.5, 9.5)
    p.line(0, 184, W, 184, w=2)
    p.save(186)


def masthead_phone(theme, ed):
    p = Plate("masthead", theme, f"{C.PAPER} — {ed['edition_line']}", mobile=True)
    p.line(0, 4.5, M, 4.5, "hair")
    p.text(M / 2, 19, f"{p.t['edition']} · {ed['long']}", "mono", 8.5, "muted", "middle", 0.08, "ink")
    p.text(M / 2, 32, f"VOL. {ed['vol']} · NO. {ed['issue']:,} · PRICE: FREE (MIT LICENSE)", "mono", 8.5, "muted", "middle", 0.08, "ink")
    p.line(0, 41.5, M, 41.5, "hair")
    p.text(M / 2, 64, f"KOLKATA · GITHUB.COM/{C.LOGIN.upper()}", "label", 8.5, "muted", "middle", 0.2, "ink", "animation-delay:.2s")
    size = min(64, (M - 6) / FACES["display"].width(C.PAPER, 1))
    base = 74 + size * .74
    nameplate(p, M / 2, base, size)
    tagline(p, base + 28, 9, M)
    bottom = ears(p, ed, base + 48, 150, 12.5, 8.5)
    p.line(0, bottom + 16, M, bottom + 16, w=2)
    p.save(bottom + 18)


def nav(theme, mobile=False):
    """The ink nav bar, cut into segments so every label is a real link.

    The README pins each segment's width as a share of the column, so the
    phone segments keep those shares and stack long labels on two lines."""
    size, track, h = 10.5, 0.16, 38
    natural = [FACES["label"].width(label, size, track) + 28 for label, *_ in C.NAV]
    spare = (W - sum(natural)) / len(natural)
    widths = [round(n + spare) for n in natural]
    for i, ((label, _, name), w) in enumerate(zip(C.NAV, widths)):
        if mobile:
            sw = round(w * PHONE_COLUMN / W, 1)
            p = Plate(f"nav-{i}", theme, name, width=sw, mobile=True)
            h, fs, track = 42, 9.0, 0.06
            lines = [label] if FACES["label"].width(label, fs, track) <= sw - 8 else label.split(" ")
            while fs > 6.5 and max(FACES["label"].width(ln, fs, track) for ln in lines) > sw - 6:
                fs -= .25
        else:
            p = Plate(f"nav-{i}", theme, name, width=w)
            fs, lines = size, [label]
        p.rect(0, 0, p.w, h)
        if i:
            p.add(f'<line x1=".5" y1="9" x2=".5" y2="{h - 9}" stroke="{p.t["on-band"]}" stroke-opacity=".28"/>')
        lh = fs * 1.2
        for j, ln in enumerate(lines):
            p.text(p.w / 2, h / 2 + fs * .36 + (j - (len(lines) - 1) / 2) * lh, ln, "label", fs, "on-band", "middle", track)
        p.save(h)
    return widths


def ticker(theme, ed, mobile=False):
    p = Plate("ticker", theme, "Breaking: " + " / ".join(ed["ticker"]), mobile=mobile)
    size, h = 10.5, 34
    p.line(0, .5, p.w, .5, "hair")
    p.line(0, h - .5, p.w, h - .5, "hair")
    x = p.chip(0, 21.5, "BREAKING")
    gap = 36
    p.used["mono"].update("".join(ed["ticker"]))
    items, cx = [], 0.0
    for s in ed["ticker"]:
        items.append(f'<text x="{cx:.1f}" y="21.5" class="f-mono c-ink" font-size="{size}" letter-spacing=".4">{esc(s)}</text>')
        cx += FACES["mono"].width(s, size) + 0.4 * len(s)
        items.append(f'<rect x="{cx + gap / 2 - 3:.1f}" y="14" width="6" height="6" transform="rotate(45 {cx + gap / 2:.1f} 17)" class="c-muted"/>')
        cx += gap
    loop = "".join(items)
    p.defs.append(
        f'<clipPath id="wire"><rect x="{x + 12}" y="0" width="{p.w - x - 12}" height="{h}"/></clipPath>'
        '<linearGradient id="fade"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset=".04" stop-color="#fff"/><stop offset=".94" stop-color="#fff"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="edges"><rect x="{x + 12}" y="0" width="{p.w - x - 12}" height="{h}" fill="url(#fade)"/></mask>'
    )
    p.css.append(f"@keyframes tape{{to{{transform:translateX(-{cx:.1f}px)}}}}.tape{{animation:tape {cx / 48:.1f}s linear infinite}}")
    p.add(
        f'<g clip-path="url(#wire)" mask="url(#edges)"><g transform="translate({x + 24:.1f} 0)">'
        f'<g class="tape">{loop}<g transform="translate({cx:.1f} 0)">{loop}</g></g></g></g>'
    )
    p.save(h)


def standfirst(p, x, y, width, ts, tl):
    """Bold lead-in, three-line drop cap, then the teaser. Returns the last baseline."""
    L = C.LEAD
    # The cap's height spans two leads plus one cap height of the text.
    cs = (2 * tl + ts * .67) / .67
    cap_w = FACES["display"].width(L["standfirst_lead"][0], cs) + 6
    lines = wrap_runs(
        [(L["standfirst_lead"][1:], "textbold"), (L["standfirst"], "text")], ts,
        lambda i: width - cap_w if i < 3 else width,
    )
    p.text(x - 3, y + 2 * tl, L["standfirst_lead"][0], "display", round(cs, 1), cls="ink", style="animation-delay:.6s")
    for i, ln in enumerate(lines):
        p.runs(x + (cap_w if i < 3 else 0), y, ln, ts, style=f"animation:ink .6s {.7 + i * .05:.2f}s both")
        y += tl
    y += 8
    for ln in wrap("text", L["teaser"], 14, width):
        p.text(x, y, ln, "text", 14, "muted")
        y += 21
    return y


def continued(p, x, y):
    label = "CONTINUED ON ANIRBANDAS.COM"
    p.line(x, y, p.w, y, "hair")
    p.text(x, y + 20, label, "label", 9.5, track=0.16)
    aw = FACES["label"].width(label, 9.5, 0.16)
    p.text(x + aw + 4, y + 20.5, "→", "mono", 11)
    p.line(x, y + 25, x + aw + 14, y + 25, w=1)
    return y + 28


def headline(p, y, size, width):
    lh = size * 1.1
    for i, ln in enumerate(wrap("head", C.LEAD["headline"], size, width, -0.012)):
        p.text(0, y, ln, "head", size, track=-0.012, cls="rise", style=f"animation-delay:{.1 + i * .12:.2f}s")
        y += lh
    return y


def caption(p, y, width, size):
    lines = wrap("label", C.LEAD["caption"], size, width, 0.14)
    for i, ln in enumerate(lines):
        p.text(0, y + i * 13, ln, "label", size, "muted", track=0.14)
    return y + (len(lines) - 1) * 13


def lead(theme, ed):
    L = C.LEAD
    p = Plate("lead", theme, f"Lead story: {L['headline']} {L['standfirst_lead']}{L['standfirst']}")
    x = p.chip(0, 18, "LEAD STORY")
    p.text(x + 12, 18, L["kicker"], "label", 9.5, "muted", track=0.16)
    p.text(W, 18, f"BY {C.NAME.upper()} · {ed['short']}", "label", 9.5, "muted", "end", 0.16)
    top = headline(p, 72, 42, W) - 14
    pw, ph = 430, 287
    p.image(0, top, pw, ph, "lead", delay=.3)
    left_h = caption(p, top + ph + 18, pw, 9)
    cx = pw + 26
    p.line(pw + 13, top, pw + 13, left_h, "hair")
    y = standfirst(p, cx, top + 16, W - cx, 16.5, 25)
    p.save(max(left_h, continued(p, cx, y + 2)) + 6)


def lead_phone(theme, ed):
    L = C.LEAD
    p = Plate("lead", theme, f"Lead story: {L['headline']} {L['standfirst_lead']}{L['standfirst']}", mobile=True)
    x = p.chip(0, 18, "LEAD STORY")
    p.text(x + 10, 18, L["kicker"], "label", 9.5, "muted", track=0.16)
    y = headline(p, 62, 31, M)
    p.text(0, y - 6, f"BY {C.NAME.upper()} · {ed['short']}", "label", 9, "muted", track=0.16)
    top, ph = y + 8, M * 2 / 3
    p.image(0, top, M, ph, "lead", delay=.3)
    y = caption(p, top + ph + 17, M, 8.5)
    y = standfirst(p, 0, y + 34, M, 16, 24)
    p.save(continued(p, 0, y + 2) + 4)


def odometer(p, x, y, value, size, delay):
    """Digits roll up into place like a mechanical counter; anything else stays put."""
    pitch = size * 1.1
    for ch in value:
        cw = FACES["display"].width(ch, size)
        if not ch.isdigit():
            p.text(x, y, ch, "display", size)
            x += cw
            continue
        k = 10 + int(ch)
        clip = f"odo{len(p.defs)}"
        p.defs.append(f'<clipPath id="{clip}"><rect x="{x - 2:.1f}" y="{y - size * .9:.1f}" width="{cw + 4:.1f}" height="{pitch:.1f}"/></clipPath>')
        p.used["display"].update("0123456789")
        col = "".join(
            f'<text x="{x:.1f}" y="{y + j * pitch:.1f}" class="f-display c-ink" font-size="{size}">{j % 10}</text>'
            for j in range(k + 1)
        )
        p.add(
            f'<g clip-path="url(#{clip})"><g class="roll" '
            f'style="transform:translateY(-{k * pitch:.1f}px);animation-delay:{delay:.2f}s;--to:-{k * pitch:.1f}px">{col}</g></g>'
        )
        delay += .12
        x += cw
    return x


def grid(p, n, cols, top, row_h):
    """Cell origins for a ruled grid of n cells: four across, or 2×2 on a phone."""
    cw = p.w / cols
    cells = []
    for i in range(n):
        col, row = i % cols, i // cols
        y = top + row * row_h
        if col:
            p.line(col * cw + .5, y + 4, col * cw + .5, y + row_h - 12, "hair")
        elif row:
            p.line(0, y - 4, p.w, y - 4, "hair")
        cells.append((col * cw + (18 if col else 0), y, cw - (36 if col else 18)))
    return cells, top + (n + cols - 1) // cols * row_h


def numbers(theme, ed, mobile=False):
    p = Plate("numbers", theme, "By the numbers: " + "; ".join(f"{v} {l.lower()}" for v, l in ed["numbers"]), mobile=mobile)
    p.section("BY THE NUMBERS", right="LIVE FROM THE GITHUB API" + ("" if mobile else f" · {ed['short']}"))
    p.css.append(
        "@keyframes roll{from{transform:translateY(0)}to{transform:translateY(var(--to))}}"
        ".roll{animation:roll 1.8s cubic-bezier(.15,.75,.15,1) both}"
    )
    cells, bottom = grid(p, len(ed["numbers"]), 2 if mobile else 4, 42, 92)
    for i, ((value, label), (x, y, cw)) in enumerate(zip(ed["numbers"], cells)):
        if value == "∞":
            p.text(x, y + 50, "∞", "label", 44)
        else:
            odometer(p, x, y + 50, value, 40, .2 + i * .25)
        for j, ln in enumerate(wrap("label", label, 9, cw, 0.14)):
            p.text(x, y + 70 + j * 12, ln, "label", 9, "muted", track=0.14)
    p.line(0, bottom + 2, p.w, bottom + 2, "hair")
    p.save(bottom + 4)


def work_head(theme, mobile=False):
    p = Plate("work", theme, "Selected work: reports from the field", mobile=mobile)
    if mobile:
        p.section("SELECTED WORK", right=f"{len(C.WORK)} CASE FILES")
        p.text(0, 50, "REPORTS FROM THE FIELD · TAP A CARD TO OPEN", "label", 9, "muted", track=0.16)
        p.save(60)
    else:
        p.section("SELECTED WORK", "REPORTS FROM THE FIELD · 2024 — 2026", f"{len(C.WORK)} CASE FILES · EACH CARD OPENS IT")
        p.save(36)


def badge(p, item, stars, right, y, size):
    """Bottom-right of a card: the live star count, or what the project is."""
    if stars:
        label = f"{stars:,}"
        p.text(right, y, label, "mono", size, anchor="end")
        sx, sy, r = right - FACES["mono"].width(label, size) - size, y - size * .34, size * .52
        pts = " ".join(
            f"{sx + (r if k % 2 == 0 else r * .45) * math.sin(k * math.pi / 5):.2f},"
            f"{sy - (r if k % 2 == 0 else r * .45) * math.cos(k * math.pi / 5):.2f}"
            for k in range(10)
        )
        p.add(f'<polygon points="{pts}" class="c-ink"/>')
    else:
        p.text(right, y, "OPEN SOURCE" if item.get("repo") else "LIVE ON PLAY", "mono", size - 1, anchor="end", track=0.06)


def cta(p, x, y, label, size):
    p.text(x, y, label, "label", size, track=0.16)
    p.text(x + FACES["label"].width(label, size, .16) + 3, y + .5, "↗", "mono", size + 1)


def card(theme, item, stars):
    cw, pad = 412, 16
    p = Plate(f"card-{item['slug']}", theme, f"{item['kicker']}: {item['title']}. {item['summary']}", width=cw)
    iw = cw - 2 * pad
    p.add(f'<rect x=".5" y=".5" width="{cw - 1}" height="485" fill="none" class="s-hair"/>')
    p.text(pad, 24, item["kicker"], "label", 9, "muted", track=0.16)
    p.text(cw - pad, 24, item["year"], "mono", 10, "muted", "end")
    p.line(pad, 33, cw - pad, 33, "ink")
    p.image(pad, 42, iw, iw * 10 / 16, item["slug"], delay=.2)
    y = 42 + iw * 10 / 16 + 30
    for i, ln in enumerate(clamp("head", wrap("head", item["title"], 21, iw, -0.005), 2, 21, iw)):
        p.text(pad, y + i * 25, ln, "head", 21, track=-0.005)
    y += 50
    for i, ln in enumerate(clamp("text", wrap("text", item["summary"], 13, iw), 4, 13, iw)):
        p.text(pad, y + i * 19, ln, "text", 13, "muted")
    p.text(pad, 438, "  ·  ".join(item["stack"]), "mono", 9.5, "ink", track=0.06)
    p.line(pad, 452, cw - pad, 452, "hair")
    cta(p, pad, 472, item["cta"], 9.5)
    badge(p, item, stars, cw - pad, 472, 10.5)
    p.save(486)


def card_phone(theme, item, stars):
    """Half a phone column: picture, headline, stars. The summary is a tap away."""
    cw, pad, h = 180, 10, 250
    p = Plate(f"card-{item['slug']}", theme, f"{item['kicker']}: {item['title']}. {item['summary']}", width=cw, mobile=True)
    iw = cw - 2 * pad
    p.add(f'<rect x=".5" y=".5" width="{cw - 1}" height="{h - 1}" fill="none" class="s-hair"/>')
    p.text(pad, 20, item["kicker"].split(" · ")[0], "label", 8, "muted", track=0.12)
    p.text(cw - pad, 20, item["year"], "mono", 8.5, "muted", "end")
    p.line(pad, 27, cw - pad, 27, "ink")
    p.image(pad, 34, iw, iw * 10 / 16, item["slug"], delay=.2)
    y = 34 + iw * 10 / 16 + 22
    for i, ln in enumerate(clamp("head", wrap("head", item["title"], 15, iw, -0.005), 4, 15, iw)):
        p.text(pad, y + i * 18, ln, "head", 15, track=-0.005)
    p.line(pad, h - 30, cw - pad, h - 30, "hair")
    cta(p, pad, h - 13, "GOOGLE PLAY" if item.get("link") else "SOURCE", 8.5)
    if stars:  # at this width "OPEN SOURCE" beside "SOURCE" just stutters
        badge(p, item, stars, cw - pad, h - 13, 9.5)
    p.save(h)


def year(theme, ed, mobile=False):
    weeks, s = ed["weeks"][-26:] if mobile else ed["weeks"], ed["ledger"]
    p = Plate("year", theme, f"Fig. 1, the year in print: {ed['total']} contributions in the last twelve months, every day printed as a halftone dot.", mobile=mobile)
    if mobile:
        p.section("FIG. 1", "THE YEAR IN PRINT", "LAST SIX MONTHS")
    else:
        first = datetime.fromisoformat(weeks[0][0][0]).strftime("%b %Y").upper()
        p.section("FIG. 1", "THE YEAR IN PRINT — ONE DOT A DAY, INKED BY COMMITS", f"{ed['total']:,} CONTRIBUTIONS SINCE {first}")

    gx, gy = (30 if mobile else 34), 70
    pitch = (p.w - gx) / len(weeks)
    nonzero = sorted(c for w in weeks for _, c in w if c)
    cap = max(4, nonzero[int(len(nonzero) * .9)] if nonzero else 4)
    rmax = pitch * .47
    # A print head crosses the grid every `cycle` seconds. The first pass
    # inks the dots in; every later pass sends a ripple through them.
    cycle = 9
    step = 2.4 / len(weeks)
    pass_pct = len(weeks) * step / cycle * 100
    p.css.append(
        "@keyframes dot{from{transform:scale(0)}to{transform:scale(1)}}"
        f"@keyframes ripple{{0%,12%,100%{{transform:scale(1)}}6%{{transform:scale(1.4)}}}}"
        f"@keyframes ripple-z{{0%,12%,100%{{transform:scale(1)}}6%{{transform:scale(2.4)}}}}"
        ".dot,.zdot{transform-box:fill-box;transform-origin:center}"
        f".dot{{animation:dot .5s cubic-bezier(.3,1.6,.5,1) both,ripple {cycle}s ease-in-out infinite}}"
        f".zdot{{animation:ripple-z {cycle}s ease-in-out infinite}}"
        f"@keyframes sweep{{0%{{transform:translateX(0);opacity:1}}{pass_pct:.1f}%{{transform:translateX(var(--to));opacity:1}}"
        f"{pass_pct + .5:.1f}%,100%{{transform:translateX(var(--to));opacity:0}}}}"
        f".presshead{{opacity:0;animation:sweep {cycle}s linear .3s infinite}}"
    )
    starts = []
    for ci, w in enumerate(weeks):
        m = datetime.fromisoformat(w[0][0]).strftime("%b").upper()
        if not starts or starts[-1][1] != m:
            starts.append((ci, m))
    if len(starts) > 1 and starts[1][0] < 3:
        starts.pop(0)  # a sliver of a month gets no label
    for ci, m in starts:
        if ci < len(weeks) - 2:
            p.text(gx + ci * pitch, gy - 12, m, "label", 8.5, "muted", track=0.12)
    for ci, w in enumerate(weeks):
        x = gx + ci * pitch + pitch / 2
        here = .3 + ci * step  # when the head reaches this column
        ripple = here + cycle - cycle * .06  # peak of the ripple lands under the head
        for d, c in w:
            row = datetime.fromisoformat(d).isoweekday() % 7
            y = gy + row * pitch + pitch / 2
            if c:
                r = 1.6 + (rmax - 1.6) * math.sqrt(min(c, cap) / cap)
                p.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" class="c-ink dot" style="animation-delay:{here:.2f}s,{ripple:.2f}s"/>')
            else:
                p.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.1" class="c-zero zdot" style="animation-delay:{ripple - cycle:.2f}s"/>')
    for row, label in ((1, "MON"), (3, "WED"), (5, "FRI")):
        p.text(0, gy + row * pitch + pitch / 2 + 3, label, "label", 8, "muted", track=0.12)
    p.add(
        f'<rect x="{gx - 1}" y="{gy - 4}" width="2" height="{7 * pitch + 8:.1f}" class="c-ink presshead" '
        f'style="--to:{len(weeks) * pitch:.1f}px"/>'
    )

    gb = gy + 7 * pitch + 22
    p.text(gx, gb, "LESS", "label", 8, "muted", track=0.12)
    lx = gx + 34
    for k, frac in enumerate((0, .15, .4, .7, 1)):
        r = 1.1 if not frac else 1.6 + (rmax - 1.6) * math.sqrt(frac)
        p.add(f'<circle cx="{lx + k * 15:.1f}" cy="{gb - 3:.1f}" r="{r:.2f}" class="{"c-zero" if not frac else "c-ink"}"/>')
    p.text(lx + 5 * 15 + 2, gb, "MORE", "label", 8, "muted", track=0.12)
    p.text(p.w, gb, f"{ed['total']:,} IN 12 MONTHS" if mobile else "HALFTONE BY GITHUB ACTIONS · REPRINTED EVERY MORNING",
           "label", 8, "muted", "end", 0.12)

    sy = gb + 18
    p.line(0, sy, p.w, sy, "hair")
    busy_date, busy_n = s["busiest"]
    busy = datetime.fromisoformat(busy_date).strftime("%-d %b").upper() if busy_date else "—"
    stats = [
        (f"{s['current']}", "DAY" if s["current"] == 1 else "DAYS", "CURRENT STREAK"),
        (f"{s['longest']}", "DAY" if s["longest"] == 1 else "DAYS", "LONGEST STREAK, 12 MONTHS"),
        (f"{busy_n}", busy, "BUSIEST DAY ON THE PRESS"),
        (f"{s['week']}", "FILED", "CONTRIBUTIONS, LAST 7 DAYS"),
    ]
    cells, bottom = grid(p, len(stats), 2 if mobile else 4, sy + 8, 74)
    for (v, unit, label), (x, y, cw) in zip(stats, cells):
        p.text(x, y + 34, v, "display", 30)
        p.text(x + FACES["display"].width(v, 30) + 6, y + 34, unit, "label", 9.5, track=0.14)
        for j, ln in enumerate(wrap("label", label, 8.5, cw, 0.14)):
            p.text(x, y + 52 + j * 11, ln, "label", 8.5, "muted", track=0.14)
    fy = bottom
    p.line(0, fy, p.w, fy, "hair")
    p.text(0, fy + 24, "TODAY'S FORECAST", "label", 9.5, track=0.16)
    if mobile:
        y = fy + 46
        for ln in wrap("italic", ed["forecast"], 15, p.w):
            p.text(0, y, ln, "italic", 15)
            y += 21
        p.save(y - 9)
    else:
        p.text(130, fy + 24.5, ed["forecast"], "italic", 15)
        p.save(fy + 34)


def markets(theme, mobile=False):
    p = Plate("markets", theme, "Markets, the developer stock exchange: " + "; ".join(f"{n.title()} {c}" for _, n, _, c, _ in C.MARKETS) + ". And the practice: " + " ".join(f"{h}. {b}" for h, b in C.PRACTICE), mobile=mobile)
    lw = p.w if mobile else 392
    p.line(0, 1, lw, 1, w=2)
    p.chip(0, 26, "MARKETS")
    p.text(lw, 26, "DEVELOPER STOCK EXCHANGE", "label", 9.5, "muted", "end", 0.16)
    y = 54
    for x, label, anchor in ((0, "SYM", "start"), (48, "LISTING", "start"), (196, "7-DAY", "start"), (318, "LAST", "end"), (lw, "CHG", "end")):
        p.text(x, y, label, "mono", 8.5, "muted", anchor, 0.1)
    p.line(0, y + 8, lw, y + 8, "hair")
    p.css.append(
        "@keyframes trace{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}"
        ".trace{stroke-dasharray:1;animation:trace 1.4s ease-out both;fill:none;stroke-linejoin:round;stroke-linecap:round}"
        "@keyframes blink{0%,100%{opacity:1}50%{opacity:.15}}.tick{animation:blink 1.8s ease-in-out infinite}"
    )
    y += 32
    for i, (sym, name, last, chg, spark) in enumerate(C.MARKETS):
        up = not chg.startswith("-")
        p.text(0, y, sym, "mono", 11.5)
        p.text(48, y, name, "label", 9, track=0.1)
        pts = " ".join(f"{196 + k * 12:.0f},{y + 1 - v * 2.1:.1f}" for k, v in enumerate(spark))
        p.add(f'<polyline points="{pts}" pathLength="1" class="s-ink trace" stroke-width="1.4" style="animation-delay:{.3 + i * .1:.1f}s"/>')
        # The live quote: last point of the line keeps ticking.
        p.add(f'<circle cx="{196 + 6 * 12}" cy="{y + 1 - spark[-1] * 2.1:.1f}" r="2.2" class="c-ink tick" style="animation-delay:{i * .37:.2f}s"/>')
        p.text(318, y, last, "mono", 11, anchor="end")
        tri = (f"{lw - 52},{y - 1} {lw - 46},{y - 1} {lw - 49},{y - 8}" if up
               else f"{lw - 52},{y - 8} {lw - 46},{y - 8} {lw - 49},{y - 1}")
        p.add(f'<polygon points="{tri}" class="c-ink"/>')
        p.text(lw, y, chg, "mono", 11, anchor="end")
        p.line(0, y + 11, lw, y + 11, "hair")
        y += 30
    p.text(0, y + 2, "Self-assessed. Markets close whenever the editor says so.", "italic", 13, "muted")
    left_h = y + 8

    # The Practice: beside the markets on desktop, beneath them on a phone.
    if mobile:
        rx, rw, oy = 0, p.w, left_h + 34
    else:
        rx, rw, oy = lw + 40, W - lw - 40, 0
        p.line(lw + 20, 12, lw + 20, left_h, "hair")
    p.line(rx, oy + 1, p.w, oy + 1, w=2)
    p.chip(rx, oy + 26, "THE PRACTICE")
    p.text(p.w, oy + 26, "WHAT THE EDITOR DOES", "label", 9.5, "muted", "end", 0.16)
    y = oy + 62
    for i, (head, body) in enumerate(C.PRACTICE):
        if i:
            p.line(rx, y - 20, p.w, y - 20, "hair")
        p.text(rx, y, head, "head", 18)
        y += 22
        for ln in wrap("text", body, 13.5 if not mobile else 14, rw):
            p.text(rx, y, ln, "text", 13.5 if not mobile else 14, "muted")
            y += 19.5 if not mobile else 20.5
        y += 30
    p.save((y - 30 if mobile else max(left_h, y - 30)) + 8)


def classifieds(theme, mobile=False):
    cl = C.CLASSIFIEDS
    flat = [cl["display"][1]] + [a for col in cl["columns"] for _, ads in col for a in ads]
    p = Plate("classifieds", theme, "Classifieds: " + " ".join(flat), mobile=mobile)
    p.section("CLASSIFIEDS", "SMALL ADS · RATES ON APPLICATION")
    columns = [[s for col in cl["columns"] for s in col]] if mobile else cl["columns"]
    gut = 26
    cw = (p.w - (len(columns) - 1) * gut) / len(columns)
    size, lh = (13.5, 19) if mobile else (12.5, 17.5)
    heights = []
    for ci, col in enumerate(columns):
        x = ci * (cw + gut)
        y = 48
        if ci == 0:
            tag, body = cl["display"]
            lines = wrap("text", body, 13.5 if mobile else 13, cw - 28)
            bh = 54 + len(lines) * 18
            p.rect(x, y, cw, bh)
            p.text(x + cw / 2, y + 34, tag, "display", 24, "on-band", "middle", 0.04)
            for j, ln in enumerate(lines):
                p.text(x + 14, y + 58 + j * 18, ln, "text", 13.5 if mobile else 13, "on-band")
            y += bh + 26
        for header, ads in col:
            p.line(x, y - 12, x + cw, y - 12, "ink")
            p.line(x, y - 9, x + cw, y - 9, "ink")
            p.text(x + cw / 2, y + 6, header, "label", 10, "ink", "middle", 0.24)
            p.line(x, y + 14, x + cw, y + 14, "hair")
            y += 34
            for k, ad in enumerate(ads):
                if k:
                    p.line(x + cw / 2 - 16, y - 8, x + cw / 2 + 16, y - 8, "hair")
                    y += 10
                for ln in wrap("text", ad, size, cw):
                    p.text(x, y, ln, "text", size)
                    y += lh
                y += 6
            y += 22
        heights.append(y)
    h = max(heights) - 14
    for ci in range(1, len(columns)):
        x = ci * (cw + gut) - gut / 2
        p.line(x, 46, x, h - 6, "hair")
    p.save(h)


def coupon(theme, mobile=False):
    p = Plate("coupon", theme, f"Clip and send: write to the editor at {C.EMAIL}. Every dispatch gets a same-day reply.", mobile=mobile)
    pad = 20 if mobile else 26
    label = C.EMAIL.upper()
    if mobile:
        y = 70
        for ln in wrap("head", "Have a role, a bug, or a wild idea?", 24, p.w - 2 * pad, -0.01):
            p.text(pad, y, ln, "head", 24, track=-0.01)
            y += 28
        for ln in wrap("italic", "Write to the editor. Every dispatch gets a same-day reply.", 14.5, p.w - 2 * pad):
            p.text(pad, y + 2, ln, "italic", 14.5, "muted")
            y += 20
        bx, by, bw = pad, y + 12, p.w - 2 * pad
        h = by + 44 + pad + 2
    else:
        h = 132
        p.text(pad, 76, "Have a role, a bug, or a wild idea?", "head", 27, track=-0.01)
        p.text(pad, 104, "Write to the editor. Every dispatch gets a same-day reply.", "italic", 15, "muted")
        bw = FACES["label"].width(label, 10.5, 0.14) + 64
        bx, by = W - pad - bw, h / 2 - 22
    p.text(pad, 40, "CLIP & SEND · REPLY COUPON", "label", 9.5, "muted", track=0.18)
    p.rect(bx, by, bw, 44)
    p.text(bx + 20, by + 26, label, "label", 10.5, "on-band", track=0.14)
    p.text(bx + bw - 20, by + 26.5, "→", "mono", 13, "on-band", "end")
    p.add(f'<rect x="1" y="1" width="{p.w - 2}" height="{h - 2}" fill="none" class="s-ink" stroke-width="1.2" stroke-dasharray="7 5"/>')
    # Scissors that actually snip their way along the dotted line. One half is
    # drawn pointing right from the pivot; the other is its mirror image.
    half = (
        '<path d="M0 0 C6 -1.6 14 -3.4 24 -3.2 C15 -1.2 7 .4 0 1.6 Z" class="c-ink"/>'
        '<path d="M.5 .8 L-6.5 4.6" class="s-ink" stroke-width="2.2" stroke-linecap="round"/>'
        '<circle cx="-10.4" cy="6.6" r="4.4" fill="none" class="s-ink" stroke-width="2.2"/>'
    )
    p.add(
        '<g class="snipper"><g transform="translate(24 1)">'
        f'<g class="blade-a">{half}</g><g transform="scale(1 -1)"><g class="blade-a">{half}</g></g>'
        '<circle r="1.4" class="c-ink"/></g></g>'
    )
    p.css.append(
        f"@keyframes travel{{0%{{transform:translateX(0);opacity:0}}6%,94%{{opacity:1}}100%{{transform:translateX({p.w - 64}px);opacity:0}}}}"
        f".snipper{{animation:travel {11 * p.w / W:.1f}s linear infinite}}"
        "@keyframes snip{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(-15deg)}}"
        ".blade-a{animation:snip .42s ease-in-out infinite}"
    )
    p.save(h)


def colophon(theme, ed, mobile=False):
    co = C.COLOPHON
    p = Plate("colophon", theme, f"Colophon. {co['blurb']} Corrections: {co['corrections']} {co['printing']}", mobile=mobile)
    p.line(0, 1, p.w, 1, w=2)
    p.line(0, 5.5, p.w, 5.5)
    cols = [
        (C.PAPER.upper(), co["blurb"]),
        ("CORRECTIONS", co["corrections"]),
        ("PRINTING", f"{co['printing']} Last press run: {ed['stamp']}."),
    ]
    gut = 26
    cw = p.w if mobile else (W - 2 * gut) / 3
    size = 13.5 if mobile else 12.5
    bottom, top = 0, 0
    for i, (head, body) in enumerate(cols):
        x = 0 if mobile else i * (cw + gut)
        if i and not mobile:
            p.line(x - gut / 2, 22, x - gut / 2, 120, "hair")
        p.text(x, top + 34, head, "label", 9.5, track=0.18)
        y = top + 56
        for ln in wrap("text", body, size, cw):
            p.text(x, y, ln, "text", size, "muted")
            y += size * 1.44
        bottom = max(bottom, y)
        if mobile:
            top = y - 8
    p.text(p.w / 2, bottom + 26, "— 30 —", "head", 16, anchor="middle")
    p.text(p.w / 2, bottom + 48, "EOF · PRINTED ON 100% RECYCLED PIXELS", "mono", 9, "muted", "middle", 0.14)
    p.save(bottom + 58)


# ── README ──────────────────────────────────────────────────────────────────

def pic(name, alt, width="100%"):
    """Phone sources come first, and spell the scheme query without a space.

    GitHub's themed-picture script forces a viewer's chosen theme by rewriting
    any media that reads "prefers-color-scheme: dark", which would erase the
    width test. "(prefers-color-scheme:dark)" is the same query to a browser
    and invisible to the script, so phone plates follow the OS theme instead,
    and print on solid paper to stay legible if the two disagree."""
    alt = alt.replace("&", "&amp;").replace('"', "&quot;")
    return (
        f'<picture><source media="{PHONE} and (prefers-color-scheme:dark)" srcset="edition/mobile/{name}-dark.svg">'
        f'<source media="{PHONE}" srcset="edition/mobile/{name}-light.svg">'
        f'<source media="(prefers-color-scheme: dark)" srcset="edition/{name}-dark.svg">'
        f'<img src="edition/{name}-light.svg" alt="{alt}" width="{width}"></picture>'
    )


def readme(ed, nav_widths):
    L = C.LEAD
    navbar = "".join(
        f'<a href="{href}">{pic(f"nav-{i}", name, f"{math.floor(w / W * 10000) / 100}%")}</a>'
        for i, ((_, href, name), w) in enumerate(zip(C.NAV, nav_widths))
    )
    def href(w):
        return w.get("link") or f"https://github.com/{C.LOGIN}/{w['repo']}"

    cards = [
        " ".join(
            f'<a href="{href(w)}">' + pic("card-" + w["slug"], f"{w['title']} — {w['summary']}", "49%") + "</a>"
            for w in pair
        )
        for pair in zip(C.WORK[::2], C.WORK[1::2])
    ]
    work_list = "\n".join(f"- **[{w['title']}]({href(w)})** — {w['summary']}" for w in C.WORK)
    blocks = [
        f"<!-- {C.PAPER}: printed by press/print.py on {ed['stamp']}. Edit press/content.py, not this file. -->",
        '<div align="center">',
        f'<a href="{C.SITE}">{pic("masthead", f"{C.PAPER} — {ed["edition_line"]}")}</a>',
        navbar,
        pic("ticker", "Breaking: " + " / ".join(ed["ticker"])),
        f'<a href="{C.SITE}/about">{pic("lead", L["headline"])}</a>',
        pic("numbers", "By the numbers: " + "; ".join(f"{v} {l.lower()}" for v, l in ed["numbers"])),
        pic("work", "Selected work"),
        *cards,
        pic("year", f"The year in print: {ed['total']} contributions in the last twelve months"),
        pic("markets", "Markets and the practice"),
        pic("classifieds", "Classifieds"),
        f'<a href="mailto:{C.EMAIL}">{pic("coupon", f"Write to the editor: {C.EMAIL}")}</a>',
        pic("colophon", "Colophon"),
        f'<img src="https://komarev.com/ghpvc/?username={C.LOGIN}&label=CIRCULATION&color=16161a&style=flat-square" alt="Circulation">',
        "</div>",
        "<details>\n<summary><b>Text-only edition</b> · for screen readers, crawlers, and the terminally curious</summary>",
        f"### {L['headline'].replace(chr(0x2011), '-')}",
        f"**{L['standfirst_lead']}**{L['standfirst']}",
        L["teaser"],
        f"#### Selected work\n\n{work_list}",
        "#### The practice\n\n" + "\n".join(f"- **{h}.** {b}" for h, b in C.PRACTICE),
        f"#### Write to the editor\n\n[{C.EMAIL}](mailto:{C.EMAIL}) · [anirbandas.com]({C.SITE}) · "
        + " · ".join(f"[{name}]({href})" for _, href, name in C.NAV[3:7]),
        "</details>",
    ]
    with open(os.path.join(ROOT, "README.md"), "w") as fh:
        fh.write("\n\n".join(blocks) + "\n")


# ── Press run ───────────────────────────────────────────────────────────────

def roman(n):
    out = ""
    for v, s in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out, n = out + s, n - v
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(IST)
    today = now.date()
    founded = date.fromisoformat(C.FOUNDED)
    years = today.year - founded.year - ((today.month, today.day) < (founded.month, founded.day))
    w = wire()
    s = ledger(w["weeks"])
    total_stars = sum(w["stars"].values())
    ed = {
        "long": now.strftime("%A, %-d %B %Y").upper(),
        "short": now.strftime("%-d %b %Y").upper(),
        "stamp": now.strftime("%-d %B %Y, %H:%M IST"),
        "vol": roman(years + 1),
        "issue": (today - founded).days + 1,
        "stars": total_stars,
        "repos": w["repos"],
        "followers": w["followers"],
        "total": w["total"],
        "weeks": w["weeks"],
        "ledger": s,
        "forecast": forecast(s["week"]),
    }
    ed["edition_line"] = f"{ed['long'].title()}, Vol. {ed['vol']}, No. {ed['issue']:,}"
    ed["numbers"] = [
        (f"{w['total']}", "CONTRIBUTIONS FILED IN THE LAST TWELVE MONTHS"),
        (f"{total_stars}", "STARS EARNED ACROSS PUBLIC REPOSITORIES"),
        ("4+ yrs", "SHIPPING PRODUCTION SOFTWARE"),
        ("∞", "BROWSER TABS OPEN RIGHT NOW"),
    ]
    filed = f"{s['week']} CONTRIBUTION{'' if s['week'] == 1 else 'S'} FILED"
    if s["week"] == 0:
        week_line = "THIS WEEK — WIRE QUIET; EDITOR REPORTEDLY DEEP IN A REFACTOR"
    elif s["current"] > 1:
        week_line = f"THIS WEEK — {filed}, {s['current']}-DAY STREAK ON THE BOOKS"
    else:
        week_line = f"THIS WEEK — {filed} AND COUNTING"
    ed["ticker"] = [
        f"PRESS — VOL. {ed['vol']}, NO. {ed['issue']:,} ROLLS OFF THE LINE AT 06:00 IST",
        week_line,
        f"MARKETS — BLUEKEYS CLOSES AT {w['stars'].get('bluekeys', 0)} STARS",
        *C.TICKER,
    ]

    os.makedirs(os.path.join(OUT, "mobile"), exist_ok=True)
    widths = []
    for theme in THEMES:
        masthead(theme, ed)
        masthead_phone(theme, ed)
        lead(theme, ed)
        lead_phone(theme, ed)
        for item in C.WORK:
            stars = w["stars"].get(item["repo"]) if item.get("repo") else None
            card(theme, item, stars)
            card_phone(theme, item, stars)
        for mobile in (False, True):
            widths = nav(theme, mobile)
            ticker(theme, ed, mobile)
            numbers(theme, ed, mobile)
            work_head(theme, mobile)
            year(theme, ed, mobile)
            markets(theme, mobile)
            classifieds(theme, mobile)
            coupon(theme, mobile)
            colophon(theme, ed, mobile)
    readme(ed, widths)
    print(f"Printed Vol. {ed['vol']}, No. {ed['issue']:,} · {ed['stamp']}")


if __name__ == "__main__":
    main()
