# Tomato mandi prices

Each morning an AWS Lambda function in the Mumbai region (`aws/lambda_function.py`) fetches the last 14 days of Agmarknet tomato prices (data.gov.in) for the mandis in `mandis.json` and saves them to `data/latest.json`. Claude reads that file to build the Daily Tomato Mandi Report.

- Schedule: 7:45 am IST daily, set on the Lambda function. data.gov.in refuses connections from GitHub's own servers, so the GitHub workflow is kept only for manual runs.
- The Lambda function needs DATA_GOV_IN_API_KEY, GITHUB_TOKEN and GITHUB_REPO set as environment variables.
- To add or drop a mandi, edit `mandis.json`.

## Report builder

`report/` holds everything that turns the prices into the daily report page (map, north-to-south table, mean/median, movers). See `report/RUNBOOK.md`.
