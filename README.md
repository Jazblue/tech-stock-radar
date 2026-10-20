# UK Tech Stock Radar

A small UK-listed technology and technology-adjacent share-price dashboard. Python fetches market data, calculates daily movements, and optionally asks a local Ollama Granite model to write a short factual summary. The static site is published with GitHub Pages.

## What it tracks

The initial watchlist covers UK-listed software, IT services, hardware, semiconductors, communications, instrumentation and selected technology/engineering companies. Symbols are Yahoo Finance symbols; `.L` denotes London listings. Check the watchlist and data-provider availability before relying on it.

## Important data notes

- This is an educational monitoring dashboard, not investment advice.
- Prices are fetched from Yahoo Finance through the unofficial `yfinance` Python package. Availability, delay, accuracy and permitted use are subject to the provider's terms.
- UK prices reported in pence are converted to pounds for display.
- The daily update should run after the London market close on weekdays.
- Granite only writes a short summary of collected data. Python calculates all price movements. If Ollama is unavailable, collection can still complete and the summary will explain that it was unavailable.
- Do not treat this as a real-time trading feed.

## Run on Windows

1. Install Python 3.11+ and Git. Make sure Ollama is running and the model is available locally:
   ```bat
   ollama pull granite4:3b
   ``
2. Clone the repository:
   ```bat
   git clone https://github.com/Jazblue/tech-stock-radar.git
   cd tech-stock-radar
   ``
3. Install dependencies:
   ```bat
   python -m pip install -r requirements.txt
   ``
4. Run a manual update:
   ```bat
   python scripts/update_prices.py
   ``
5. Inspect `data/latest.json` and the dashboard locally by opening `index.html` in a browser.
6. Publish the updated data:
   ```bat
   git add data/latest.json data/history.json
   git commit -m "Update UK tech share prices"
   git push
   ``

GitHub Pages serves the site from the repository root. Once Pages is enabled, a push to `main` publishes the latest dashboard and data.

## Local automation

After the manual run and push work, create a Windows Task Scheduler task or a Hermes cron job to run after the London market closes on weekdays. The update process must run on your PC because Granite is local. The script does not automatically push to GitHub; this is intentional until Git credentials and automation are configured safely.

## Project layout

- `index.html`, `styles.css`, `app.js`: static dashboard
- `config/stocks.json`: initial watchlist
- `scripts/update_prices.py`: price collection, daily calculations, history and local Granite summary
- `data/latest.json`: latest dashboard data
- `data/history.json`: snapshots collected by each successful run
