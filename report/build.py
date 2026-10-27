"""Build the daily tomato mandi report page from a 14-day price series.

Usage: python3 build.py series.json 2026-10-16 out.html [--sample]
Mandis come from mandis.json; the map from states.json; the page from template.html.
series.json maps the Agmarknet market name to 14 space-separated day entries
(oldest first, ending on the report date), each "min/max/modal" or "-".
"""
import json, math, sys, html, statistics
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
MAP = HERE / "states.json"

# Agmarknet name, display name, state, district, lat, lon
_MP = HERE / "mandis.json" if (HERE / "mandis.json").exists() else HERE.parent / "mandis.json"
_M = json.loads(_MP.read_text())
MANDIS = [(m["market"], m["name"], m["state"], m["district"], m["lat"], m["lon"]) for m in _M]

# preferred label offsets for crowded clusters (dx, dy from the pin)
PREF = {"Azadpur": [(10, -24)], "Keshopur": [(-9, -10), (-9, 0)], "Ballabhgarh": [(9, 0), (9, 6)],
        "Pimpalgaon Baswant": [(9, -10)], "Sangamner": [(9, -1), (9, 3)], "Narayangaon (Junnar)": [(12, 6), (12, 7)], "Pune (Manjri)": [(-9, 6), (-9, 10)],
        "Mumbai (Vashi)": [(-9, -8)],
        "Madanapalle": [(10, -22)], "Palamaner": [(12, -9)], "Vellore": [(10, 4)], "Chintamani": [(-10, -16)], "Kolar": [(-10, 2)]}

SHORT = {"Solan (Kather)": "Solan", "Kolkata (Sealdah Koley)": "Kolkata", "Mumbai (Vashi)": "Mumbai", "Pune (Manjri)": "Pune",
         "Hyderabad (Bowenpally)": "Hyderabad", "Pimpalgaon Baswant": "Pimpalgaon", "Narayangaon (Junnar)": "Narayangaon"}

BANDS = [(1500, "b1", "below ₹1,500"), (2500, "b2", "₹1,500–2,499"), (3500, "b3", "₹2,500–3,499"), (10**9, "b4", "₹3,500 and above")]

# ---------- projection: Lambert conformal conic (Survey of India style) ----------
P1, P2, LAT0, LON0 = map(math.radians, (12.472944, 35.172806, 24.0, 80.0))
N_ = math.log(math.cos(P1) / math.cos(P2)) / math.log(math.tan(math.pi / 4 + P2 / 2) / math.tan(math.pi / 4 + P1 / 2))
F_ = math.cos(P1) * math.tan(math.pi / 4 + P1 / 2) ** N_ / N_
RHO0 = F_ / math.tan(math.pi / 4 + LAT0 / 2) ** N_


def lcc(lon, lat):
    la, lo = math.radians(lat), math.radians(lon)
    rho = F_ / math.tan(math.pi / 4 + la / 2) ** N_
    t = N_ * (lo - LON0)
    return rho * math.sin(t), RHO0 - rho * math.cos(t)


def build_map(W=560):
    gj = json.loads(MAP.read_text())
    pts = []

    def rings(geom):
        if geom["type"] == "Polygon":
            yield from geom["coordinates"]
        else:
            for poly in geom["coordinates"]:
                yield from poly

    for f in gj["features"]:
        for r in rings(f["geometry"]):
            pts += [lcc(*p) for p in r]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 12
    s = (W - 2 * pad) / (maxx - minx)
    H = round((maxy - miny) * s + 2 * pad)

    def xy(lon, lat):
        x, y = lcc(lon, lat)
        return (pad + (x - minx) * s, pad + (maxy - y) * s)

    paths = []
    for f in gj["features"]:
        d = []
        for r in rings(f["geometry"]):
            q = [xy(*p) for p in r]
            d.append("M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in q) + "Z")
        paths.append(f'<path d="{"".join(d)}"><title>{html.escape(f["properties"]["st_nm"])}</title></path>')
    return W, H, "\n".join(paths), xy


# ---------- data ----------
def parse(series):
    out = {}
    for k, v in series.items():
        days = []
        for tok in v.split():
            days.append(None if tok == "-" else tuple(round(float(x)) for x in tok.split("/")))
        out[k] = days
    return out


def band(v):
    for lim, cls, _ in BANDS:
        if v < lim:
            return cls


def inr(n):
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def analyse(series, report_day):
    days = [report_day - timedelta(days=13 - i) for i in range(14)]
    rows = []
    for key, name, st, di, lat, lon in MANDIS:
        s = series.get(key, [None] * 14)
        idx = [i for i, v in enumerate(s) if v]
        r = dict(key=key, name=name, st=st, di=di, lat=lat, lon=lon, series=[v[2] if v else None for v in s])
        if not idx:
            r.update(status="none")
            rows.append(r)
            continue
        li = idx[-1]
        mn, mx, md = s[li]
        r.update(min=mn, max=mx, modal=md, last_day=days[li], fresh=(li == 13))
        if len(idx) > 1:
            pv = s[idx[-2]][2]
            r.update(prev=pv, chg=md - pv, pct=(md - pv) / pv * 100 if pv else 0, prev_day=days[idx[-2]])
        week = [s[i][2] for i in idx if i >= 7]
        r["avg7"] = sum(week) / len(week) if week else None
        flat = 0
        for i in reversed(idx):
            if abs(s[i][2] - md) <= 0.03 * md:
                flat += 1
            else:
                break
        r["flat"] = flat
        r["status"] = "ok"
        rows.append(r)
    return rows, days


# ---------- label placement on the map ----------
def place_labels(pins, W, H):
    boxes = [(x - 4, y - 4, x + 4, y + 4) for (x, y, _, _) in pins]
    cands = [(9, -8), (-9, -8), (0, -22), (0, 7), (12, -22), (-12, -22), (12, 7), (-12, 7), (26, -8), (-26, -8),
             (20, -30), (-20, -30), (20, 16), (-20, 16), (40, -16), (-40, -16), (40, 2), (-40, 2), (0, -38), (0, 24),
             (44, -32), (-44, -32), (44, 20), (-44, 20), (60, -8), (-60, -8), (60, -26), (-60, -26), (60, 10), (-60, 10)]
    out = []
    order = sorted(range(len(pins)), key=lambda i: pins[i][1])
    placed = [None] * len(pins)
    for i in order:
        x, y, text, _ = pins[i]
        w, h = 5.9 * len(text[0]) + 6.4 * len(text[1]) + 16, 16
        best = None
        for dx, dy in PREF.get(pins[i][3]["name"], []) + cands:
            if dx > 0:
                bx = x + dx
            elif dx < 0:
                bx = x + dx - w
            else:
                bx = x - w / 2
            by = y + dy
            b = (bx, by, bx + w, by + h)
            if b[0] < 2 or b[2] > W - 2 or b[1] < 2 or b[3] > H - 2:
                continue
            if any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in boxes):
                continue
            best = b
            break
        if best is None:
            bx, by = x + 9, y - 7
            best = (bx, by, bx + w, by + h)
        boxes.append(best)
        placed[i] = best
    return placed


# ---------- page ----------
def fmt_day(d, short=False):
    return d.strftime("%-d %b") if short else d.strftime("%A, %-d %B %Y")


def spark(vals, w=84, h=22):
    pts = [(i, v) for i, v in enumerate(vals) if v]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    rng = (hi - lo) or 1
    xy = [(2 + i * (w - 4) / 13, h - 3 - (v - lo) / rng * (h - 6)) for i, v in pts]
    d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    ex, ey = xy[-1]
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<path d="{d}"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.2"/></svg>')


def build(series_path, report_day, out_path, sample=False):
    series = parse(json.loads(Path(series_path).read_text()))
    rows, days = analyse(series, report_day)
    W, H, statepaths, xy = build_map()

    # state order: north to south by each state's northernmost mandi
    states = []
    for r in sorted(rows, key=lambda r: -r["lat"]):
        if r["st"] not in states:
            states.append(r["st"])

    fresh = [r for r in rows if r["status"] == "ok" and r["fresh"]]
    stale = [r for r in rows if r["status"] == "ok" and not r["fresh"]]
    none = [r for r in rows if r["status"] == "none"]
    med = statistics.median(r["modal"] for r in fresh) if fresh else 0
    mean = statistics.mean(r["modal"] for r in fresh) if fresh else 0
    hi = max(fresh, key=lambda r: r["modal"])
    lo = min(fresh, key=lambda r: r["modal"])
    movers = [r for r in fresh if "pct" in r and r["flat"] < 5 and abs(r["pct"]) >= 0.5]
    falls = sorted([r for r in movers if r["pct"] < 0], key=lambda r: r["pct"])[:4]
    rises = sorted([r for r in movers if r["pct"] > 0], key=lambda r: -r["pct"])[:4]
    flats = [r for r in rows if r["status"] == "ok" and r["flat"] >= 5]

    # map pins
    pins = []
    for r in rows:
        if r["status"] != "ok":
            continue
        x, y = xy(r["lon"], r["lat"])
        short = SHORT.get(r["name"], r["name"])
        pins.append((x, y, (short, inr(r["modal"]) + ("*" if not r["fresh"] else "")), r))
    labels = place_labels(pins, W, H)
    pin_svg = []
    for (x, y, text, r), b in zip(pins, labels):
        cls = band(r["modal"])
        lx, ly = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        # leader line from pin to nearest edge of label
        ex = min(max(x, b[0]), b[2])
        ey = min(max(y, b[1]), b[3])
        lead = ""
        if math.hypot(ex - x, ey - y) > 6:
            lead = f'<line class="lead" x1="{x:.1f}" y1="{y:.1f}" x2="{ex:.1f}" y2="{ey:.1f}"/>'
        tip = f'{r["name"]}, {r["st"]}: ₹{inr(r["modal"])}/qtl' + ("" if r["fresh"] else f' (last report {fmt_day(r["last_day"], True)})')
        pin_svg.append(
            f'<g class="pin {cls}{"" if r["fresh"] else " old"}"><title>{html.escape(tip)}</title>{lead}'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4"/>'
            f'<rect x="{b[0]:.1f}" y="{b[1]:.1f}" width="{b[2]-b[0]:.1f}" height="{b[3]-b[1]:.1f}" rx="4"/>'
            f'<text x="{lx:.1f}" y="{ly + 3.8:.1f}"><tspan class="nm">{html.escape(text[0])}</tspan> {text[1]}</text></g>')

    # table
    trs = []
    for st in states:
        grp = sorted([r for r in rows if r["st"] == st], key=lambda r: -r["lat"])
        sf = [r["modal"] for r in grp if r["status"] == "ok" and r["fresh"]]
        smean = f'<span class="smean">State mean ₹{inr(statistics.mean(sf))}</span>' if len(sf) > 1 else ""
        trs.append(f'<tr class="state"><th colspan="8" scope="colgroup">{html.escape(st)}{smean}</th></tr>')
        for r in grp:
            if r["status"] != "ok":
                trs.append(f'<tr><td class="mk">{html.escape(r["name"])}</td><td colspan="7" class="note">No report in the last 14 days</td></tr>')
                continue
            notes = []
            if not r["fresh"]:
                notes.append(f'No report for {fmt_day(report_day, True)}; figures are from {fmt_day(r["last_day"], True)}')
            if r["flat"] >= 5:
                notes.append(f'Same price for {r["flat"]} reports in a row; may not be updated daily')
            if "chg" in r:
                if r["chg"] == 0:
                    chg = '<span class="chg flat">no change</span>'
                else:
                    up = r["chg"] > 0
                    chg = (f'<span class="chg {"up" if up else "down"}">{"▲" if up else "▼"} {inr(abs(r["chg"]))}'
                           f' <small>({r["pct"]:+.0f}%)</small></span>')
            else:
                chg = "–"
            trs.append(
                f'<tr class="{"" if r["fresh"] else "oldrow"}">'
                f'<td class="mk"><span class="sw {band(r["modal"])}"></span>{html.escape(r["name"])}<div class="sub">{html.escape(r["di"])}</div></td>'
                f'<td class="num">{inr(r["min"])}</td><td class="num">{inr(r["max"])}</td>'
                f'<td class="num modal">{inr(r["modal"])}<div class="sub">₹{r["modal"]/100:.0f}/kg</div></td>'
                f'<td class="num">{chg}</td>'
                f'<td class="num">{inr(r["avg7"]) if r["avg7"] else "–"}</td>'
                f'<td class="sp">{spark(r["series"])}</td>'
                f'<td class="note">{html.escape("; ".join(notes))}</td></tr>')

    def mover_li(r):
        up = r["pct"] > 0
        return (f'<li><span>{html.escape(r["name"])} <span class="sub">{html.escape(r["st"])}</span></span>'
                f'<span class="chg {"up" if up else "down"}">{r["pct"]:+.0f}% <small>to ₹{inr(r["modal"])}</small></span></li>')

    legend = "".join(f'<li><span class="sw {cls}"></span>{lab}</li>' for _, cls, lab in BANDS)
    page = TEMPLATE
    repl = {
        "@@DATE@@": fmt_day(report_day),
        "@@DATESHORT@@": fmt_day(report_day, True),
        "@@SAMPLE@@": '<span class="badge">Sample</span>' if sample else "",
        "@@NREP@@": str(len(fresh)),
        "@@NALL@@": str(len(rows)),
        "@@MED@@": inr(med),
        "@@MEDKG@@": f"{med/100:.0f}",
        "@@MEAN@@": inr(mean),
        "@@MEANKG@@": f"{mean/100:.0f}",
        "@@HI@@": f'₹{inr(hi["modal"])} <span class="sub">{html.escape(hi["name"])}, {html.escape(hi["st"])}</span>',
        "@@LO@@": f'₹{inr(lo["modal"])} <span class="sub">{html.escape(lo["name"])}, {html.escape(lo["st"])}</span>',
        "@@STALE@@": ", ".join(f'{html.escape(r["name"])} ({fmt_day(r["last_day"], True)})' for r in stale) or "none",
        "@@FALLS@@": "".join(mover_li(r) for r in falls) or '<li class="sub">No falls</li>',
        "@@RISES@@": "".join(mover_li(r) for r in rises) or '<li class="sub">No rises</li>',
        "@@FLATS@@": ", ".join(html.escape(r["name"]) for r in flats) or "none",
        "@@W@@": str(W), "@@H@@": str(H),
        "@@STATES@@": statepaths,
        "@@PINS@@": "\n".join(pin_svg),
        "@@LEGEND@@": legend,
        "@@ROWS@@": "\n".join(trs),
        "@@FROM@@": fmt_day(days[0], True),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    Path(out_path).write_text(page)
    return rows


TEMPLATE = (HERE / "template.html").read_text()

if __name__ == "__main__":
    sp, d, out = sys.argv[1], date.fromisoformat(sys.argv[2]), sys.argv[3]
    rows = build(sp, d, out, sample="--sample" in sys.argv)
    for r in rows:
        print(r["name"], r.get("modal"), r.get("last_day"), r.get("flat"), round(r.get("pct", 0), 1))
