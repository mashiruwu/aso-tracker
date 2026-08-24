# ASO Tracker

A small, local-first App Store Optimization tracker for monitoring keyword positions without a hosted backend or paid ASO API.

The project combines a React dashboard with independent Python scripts. The UI and terminal tools use the same SQLite database, so every collector and analysis command remains useful on its own.

## What it does

- Find App Store apps by name or exact ID.
- Track separate keyword lists for multiple apps and storefronts.
- Collect rank, difficulty, version and leading competitors.
- Compare keyword position history over 7, 15 or 30 days.
- Filter position history to the app's current version.
- Detect App Store version changes.
- Run collection manually, daily with the local server, or from an external scheduler.
- Keep all ranking data on your machine.

## Stack

- React and Vite for the dashboard.
- Python's standard HTTP server for the local API and static files.
- SQLite for apps, keywords, rankings and releases.
- Apple's public Search and Lookup APIs for App Store data.

No Python web framework is required.

## Quick start

Requirements:

- Python 3.9 or newer
- Node.js 20 or newer

Install and build:

```bash
git clone https://github.com/mashiruwu/aso-tracker.git
cd aso-tracker

python3 -m pip install -r requirements.txt

cd frontend
npm install
npm run build
cd ..
```

Start the dashboard:

```bash
python3 app.py
```

Open [http://127.0.0.1:8501](http://127.0.0.1:8501).

The database is created automatically on first launch.

## Typical workflow

1. Select **Add app**.
2. Choose a storefront and search by app name.
3. Select one or several apps and add them.
4. Select an app in the sidebar and add its keywords.
5. Run **Analyze now** for the first collection.
6. Open **Evolution** after later collections to compare positions.

Evolution supports:

- Last 7 days
- Last 15 days
- Last 30 days
- Current app version

Only collected App Store data is displayed. The project does not generate sample rankings.

## Daily collection

While `app.py` remains open, the collector runs once per local day after 06:00. Change the hour with:

```bash
ASO_DAILY_HOUR=9 python3 app.py
```

For reliable collection while the dashboard is closed, schedule the standalone collector:

```bash
cd /absolute/path/to/aso-tracker
python3 collector.py
```

Use cron, launchd, GitHub Actions on a persistent runner, or another scheduler appropriate for your environment.

## Command-line tools

The scripts are intentionally independent from the dashboard:

```bash
# Collect every active keyword stored in SQLite
python3 collector.py

# Search the App Store without saving data
python3 search.py "flashcards" us

# Check one keyword for the app in config.json
python3 rank.py "ai flashcards"

# Run the original config.json + keywords.txt bulk workflow
python3 check_rankings.py

# Calculate difficulty from the latest saved search snapshot
python3 difficulty.py "ai flashcards" us

# Print the rule-based ASO opportunity report
python3 analyze.py
```

For the original file-based commands, copy the examples:

```bash
cp config.example.json config.json
cp keywords.example.txt keywords.txt
```

Then update the App Store ID, country and keywords.

## Development

Start the Python server:

```bash
python3 app.py
```

In a second terminal:

```bash
cd frontend
npm run dev
```

The Vite development server runs at `http://127.0.0.1:5173` and proxies API calls to port `8501`.

After frontend changes, create the production bundle with:

```bash
cd frontend
npm run build
```

## Data and privacy

Runtime data is written locally:

```text
data/aso.db                SQLite ranking history
data/searches/*.json       Latest competitor snapshots
data/rankings.csv          Original file-based tracker history
```

These files, `config.json`, and `keywords.txt` are ignored by Git. App Store requests are sent directly to Apple's public APIs; the project does not include analytics or a hosted service.

## Project structure

```text
app.py                     Local API, static server and daily trigger
collector.py               SQLite-based multi-app collector
db.py                      Schema and additive migrations
frontend/                  React dashboard
search.py                  Raw App Store search command
rank.py                    Single-keyword rank command
check_rankings.py          Original file-based bulk tracker
difficulty.py              Keyword difficulty calculation
analyze.py                 Rule-based opportunity report
```

## Notes

- App Store search results can vary by country and change throughout the day.
- A missing position means the app was not found within the collected result limit.
- Difficulty is an internal heuristic, not an official Apple metric.
- The built-in daily trigger only runs while `app.py` is active.
