# Nightscout Statistics

Refactored Nightscout/MongoDB analysis project.

## What changed
- Split the old monolithic script into modules.
- Moved MongoDB connection settings to environment variables.
- Added pandas-based cleaning and aggregation.
- Kept CLI interaction in `cli.py`.
- Added an optional Telegram bot entrypoint.

## Files
- `mdb-stat.py` - thin entrypoint for the CLI
- `cli.py` - interactive menu and orchestration
- `config.py` - environment-based config loader
- `db.py` - MongoDB access layer
- `analysis.py` - pandas data preparation and statistics
- `charts.py` - AGP and distribution charts
- `periods.py` - time-period query builders
- `telegram_bot.py` - optional Telegram bot interface

## Setup
1. Copy `.env.example` to `.env`
2. Set your MongoDB connection string in `MONGO_URL`
3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run CLI
```bash
python mdb-stat.py
```

## Run Telegram bot
Set `TELEGRAM_BOT_TOKEN` in `.env`, then:

```bash
python telegram_bot.py
```

## Notes
- The bot is optional; the CLI works without Telegram settings.
- `pandas` is used for cleaning, grouping, and summary calculations.

