# Stock Prices — GitHub Actions + Telegram

Runs the stock report daily and checks price alarms every 15 minutes.
No server, no card. Works free on a **public** repository.

## Setup

1. Create a new **public** GitHub repository.
2. Push the contents of this folder to the repo root:
   ```
   git init && git add . && git commit -m "stocks"
   git remote add origin git@github.com:YOU/stocks.git
   git push -u origin main
   ```
3. Create a Telegram bot via [@BotFather](https://t.me/BotFather), get the token.
   Get your chat id via [@userinfobot](https://t.me/userinfobot).
4. Repo → Settings → Secrets and variables → Actions → New repository secret:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Edit `targets.yaml` with your alarm prices (examples are commented out).
6. Actions tab → Stock prices → Run workflow (mode `report`) to test.

## What runs

| Schedule (UTC) | Mode | What |
|---|---|---|
| `0 13 * * *` | report | Full watchlist, sent to Telegram, saved to `reports/` |
| `*/15 * * * *` | alerts | Checks `targets.yaml`, sends 🚨 message on crossing |
| manual | report | Run from Actions tab |

Alarm logic: fires once when price crosses the limit, rearms when price
moves back, fires again on re-cross. State in `state.json` (committed back).

## Caveats

- Cron on scheduled workflows disables after 60 days without commits —
  the daily report commit keeps it alive.
- **Private repo on a free account**: scheduled workflows are restricted.
  Public repo avoids this.
- Prices are last daily close from Yahoo (not live intraday). Delay of a
  few minutes on GitHub cron is normal.
- Alarm check every 15 min; set `0 13 * * *` winter time is UTC+1 (14:00 local).
