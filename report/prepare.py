"""Print the browser script for a report date: python3 prepare.py 2026-10-16 > fetch_ready.js"""
import json, sys
from pathlib import Path

HERE = Path(__file__).parent
day = sys.argv[1]
_MP = HERE / "mandis.json" if (HERE / "mandis.json").exists() else HERE.parent / "mandis.json"
mandis = json.loads(_MP.read_text())
pairs = [[m["state_agmarknet"], m["market"]] for m in mandis]
js = (HERE / "fetch.js").read_text().replace("__DAY__", day).replace("__MANDIS__", json.dumps(pairs, ensure_ascii=False))
print(js)
