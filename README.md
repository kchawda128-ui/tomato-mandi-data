# Tomato mandi prices

Each morning a GitHub Actions job fetches the last 14 days of Agmarknet tomato prices (data.gov.in) for the mandis in `mandis.json` and saves them to `data/latest.json`. Claude reads that file to build the Daily Tomato Mandi Report.

- Schedule: 7:45 am IST daily (`.github/workflows/fetch-prices.yml`). Run it by hand from the Actions tab with "Run workflow".
- Needs the repository secret `DATA_GOV_IN_API_KEY`.
- To add or drop a mandi, edit `mandis.json`.
