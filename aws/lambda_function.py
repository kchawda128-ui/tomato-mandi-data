"""AWS Lambda (Mumbai, ap-south-1): fetch 14 days of Agmarknet tomato prices from data.gov.in
for the mandis in mandis.json and save them to the GitHub repository.

Environment variables (set in the Lambda console, never in code):
  DATA_GOV_IN_API_KEY  your data.gov.in API key
  GITHUB_TOKEN         fine-grained GitHub token, Contents: read and write, this repository only
  GITHUB_REPO          kchawda128-ui/tomato-mandi-data
Optional test event: {"day": "2026-10-16"}  (default: yesterday in IST)
Standard library only; no layers or packages needed. Python 3.12 runtime, timeout 3 minutes.
"""
import base64, json, os, re, time
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

RES = "35985678-0d79-46b4-9ed6-6f13308a1d24"  # Variety-wise Daily Market Prices (Agmarknet, DMI)
IST = timezone(timedelta(hours=5, minutes=30))


def http(method, url, headers=None, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def gh(method, path, token, body=None):
    return http(method, "https://api.github.com" + path, {
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tomato-mandi-lambda"}, body)


def gh_get_file(repo, path, token):
    try:
        j = gh("GET", f"/repos/{repo}/contents/{path}", token)
        return base64.b64decode(j["content"]).decode("utf-8"), j["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise


def gh_put_file(repo, path, token, text, message):
    _, sha = gh_get_file(repo, path, token)
    body = {"message": message, "content": base64.b64encode(text.encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    gh("PUT", f"/repos/{repo}/contents/{path}", token, body)


def fetch_day(key, d):
    recs, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"api-key": key, "format": "json", "limit": 1000, "offset": offset,
                                    "filters[Commodity]": "Tomato", "filters[Arrival_Date]": d.strftime("%d/%m/%Y")})
        last = None
        for attempt in range(4):
            try:
                j = http("GET", f"https://api.data.gov.in/resource/{RES}?{q}",
                         {"User-Agent": "tomato-mandi-report/1.0", "Accept": "application/json"}, timeout=40)
                break
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"data.gov.in did not answer for {d}: {last}")
        page = j.get("records") or []
        recs += page
        if len(page) < 1000:
            return recs
        offset += 1000


def lambda_handler(event, context):
    key, token, repo = os.environ["DATA_GOV_IN_API_KEY"], os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPO"]
    event = event or {}
    day = (datetime.strptime(event["day"], "%Y-%m-%d").date() if event.get("day")
           else (datetime.now(IST) - timedelta(days=1)).date())
    days = [day - timedelta(days=13 - i) for i in range(14)]

    text, _ = gh_get_file(repo, "mandis.json", token)
    mandis = json.loads(text)
    norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    want = {m["state_agmarknet"] + "|" + norm(m["market"]): m["market"] for m in mandis}
    acc = {m["market"]: [[] for _ in days] for m in mandis}
    totals = []
    for i, d in enumerate(days):
        recs = fetch_day(key, d)
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
           "fetched_at": datetime.now(IST).isoformat(timespec="minutes"), "source": "aws-lambda-ap-south-1"}
    text = json.dumps(out, ensure_ascii=False, indent=1)
    msg = f"Tomato prices for {day.isoformat()}"
    gh_put_file(repo, f"data/series-{day.isoformat()}.json", token, text, msg)
    gh_put_file(repo, "data/latest.json", token, text, msg)
    reported = sum(1 for v in series.values() if v.split()[-1] != "-")
    summary = f"{day}: {totals[-1]} tomato records that day; {reported} of {len(series)} mandis reported; saved to GitHub"
    print(summary)
    return {"ok": True, "summary": summary}
