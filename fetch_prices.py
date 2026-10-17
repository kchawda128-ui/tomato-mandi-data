"""Fetch 14 days of Agmarknet tomato prices for the mandis in mandis.json and save them.

Runs on GitHub Actions each morning. Needs the secret DATA_GOV_IN_API_KEY.
Writes data/series-<date>.json and data/latest.json:
  {"day": "yyyy-mm-dd", "records_per_day": [...14 counts...], "series": {market: "min/max/modal ... (14 entries, '-' = no report)"}}
"""
import json, os, sys, time, re
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

RES = "35985678-0d79-46b4-9ed6-6f13308a1d24"  # Variety-wise Daily Market Prices (Agmarknet, DMI)
ROOT = Path(__file__).parent
KEY = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
if not KEY:
    sys.exit("DATA_GOV_IN_API_KEY is not set")

ist = timezone(timedelta(hours=5, minutes=30))
day = datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else (datetime.now(ist) - timedelta(days=1)).date()
days = [day - timedelta(days=13 - i) for i in range(14)]
mandis = json.loads((ROOT / "mandis.json").read_text())
norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
want = {m["state_agmarknet"] + "|" + norm(m["market"]): m["market"] for m in mandis}
acc = {m["market"]: [[] for _ in days] for m in mandis}
totals = []


def get(params):
    url = f"https://api.data.gov.in/resource/{RES}?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "tomato-mandi-report/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:  # show what the server said
            body = e.read()[:300].decode("utf-8", "replace")
            last = f"HTTP {e.code}: {body}"
            print(f"attempt {attempt + 1}: {last}", flush=True)
        except Exception as e:  # network hiccups and WAF blocks
            last = repr(e)
            print(f"attempt {attempt + 1}: {last}", flush=True)
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f"data.gov.in did not answer: {last}")


for i, d in enumerate(days):
    recs, offset = [], 0
    while True:
        j = get({"api-key": KEY, "format": "json", "limit": 1000, "offset": offset,
                 "filters[Commodity]": "Tomato", "filters[Arrival_Date]": d.strftime("%d/%m/%Y")})
        page = j.get("records") or []
        recs += page
        if len(page) < 1000:
            break
        offset += 1000
    totals.append(len(recs))
    for r in recs:
        mk = want.get(r.get("State", "") + "|" + norm(r.get("Market", "")))
        if mk:
            acc[mk][i].append(r)

series = {}
for mk, per_day in acc.items():
    toks = []
    for a in per_day:
        if not a:
            toks.append("-")
            continue
        mn = min(float(x["Min_Price"]) for x in a)
        mx = max(float(x["Max_Price"]) for x in a)
        md = sum(float(x["Modal_Price"]) for x in a) / len(a)
        toks.append(f"{round(mn)}/{round(mx)}/{round(md)}")
    series[mk] = " ".join(toks)

out = {"day": day.isoformat(), "records_per_day": totals, "series": series,
       "fetched_at": datetime.now(ist).isoformat(timespec="minutes")}
(ROOT / "data").mkdir(exist_ok=True)
for name in (f"series-{day.isoformat()}.json", "latest.json"):
    (ROOT / "data" / name).write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(f"{day}: {totals[-1]} tomato records on the day; {sum(1 for v in series.values() if v.split()[-1] != '-')} of {len(series)} mandis reported")
