# Daily Tomato Mandi Report: how to build it

Everything needed is in this public repository: https://github.com/kchawda128-ui/tomato-mandi-data

| File | What it is |
|---|---|
| `mandis.json` (repo root) | The 35 mandis: Agmarknet market name, Agmarknet state name, display name, state, district, lat/lon. Edit this to add or drop a mandi. |
| `report/fetch.js` | Browser script: pulls 14 days of tomato prices for those mandis from data.gov.in. |
| `report/prepare.py` | Fills the report date and mandi list into fetch.js → prints a ready-to-run script. |
| `report/build.py` | Turns the 14-day price series into the report page (HTML). |
| `report/template.html` | Page design used by build.py. |
| `report/states.json` | India state outlines for the map. |
| `report/sample-series-2026-10-16.json` | Example input, for a test build. |
| `data/latest.json` | Written each morning by the optional AWS Lambda fetcher (`aws/`), if it has been set up. |

## Steps (report date D = yesterday in Asia/Kolkata, yyyy-mm-dd)

1. Get the code: `git clone --depth 1 https://github.com/kchawda128-ui/tomato-mandi-data` (or download the files above).
2. Get the prices, first route that works:
   a. If `data/latest.json` exists and its `day` equals D, use its `series` object.
   b. Otherwise: `python3 report/prepare.py D > fetch_ready.js`, open
      https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi
      in the Claude desktop app's built-in browser, and run the whole of fetch_ready.js with the browser's
      JavaScript tool. It returns JSON {day, records_per_day, series}. If the last number in records_per_day
      is under 300, data.gov.in has not finished loading that day: wait 20 minutes, run it once more, then
      continue either way and say so.
   Cloud workspaces and GitHub's servers cannot reach data.gov.in (tested Oct 2026), so do not try curl/requests from them.
3. Save the `series` object exactly as returned to `series-D.json`.
4. `python3 report/build.py series-D.json D tomato-report.html` (add `--sample` only for a test build).
5. Publish tomato-report.html as the report page (same page every day).

## What the report shows

- Title "Tomato Mandi Report — <weekday, date>", prices in ₹ per quintal, source Agmarknet via data.gov.in.
- Headline strip: mandis reporting (x of 35), mean modal price, median modal price (each with ₹/kg), highest and lowest mandi.
- India map, one pin per mandi labelled "name price", coloured by modal price: green below ₹1,500; amber ₹1,500–2,499; orange ₹2,500–3,499; red ₹3,500 and above. A dashed pin with * means no report for D, last price shown.
- Biggest falls and biggest rises since each mandi's last report (up to 4 each).
- Data notes: mandis with no report for D; mandis repeating the same price 5+ reports in a row (likely not updated; left out of movers).
- Table grouped by state, states ordered north to south, each state header with the state mean where 2+ mandis reported. Columns: mandi (district), min, max, modal (₹/kg), change since last report (₹ and %), 7-day average, 14-day trend line, notes.
