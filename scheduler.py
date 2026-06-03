"""
scheduler.py
Automatically runs scraper.py twice daily for 7 days.
Start it once and leave it running.
Run with: python3 scheduler.py
"""

import schedule
import time
import subprocess
from datetime import datetime, date, timedelta

# ══════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════

SCRAPE_TIMES = ["08:00", "18:00"]   # morning + evening
TOTAL_DAYS   = 7
START_DATE   = date.today()
END_DATE     = START_DATE + timedelta(days=TOTAL_DAYS)

# ══════════════════════════════════════════════════════
#  Logging helper
# ══════════════════════════════════════════════════════

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open("scheduler.log", "a") as f:
        f.write(line + "\n")

# ══════════════════════════════════════════════════════
#  Job — runs scraper.py
# ══════════════════════════════════════════════════════

run_count = [0]

def scrape_job():
    if date.today() >= END_DATE:
        log("7-day window complete. Stopping scheduler.")
        return

    log(f"▶ Starting scrape job #{run_count[0] + 1}")
    try:
        result = subprocess.run(
            ["python3", "scraper.py"],
            capture_output=True,
            text=True,
            timeout=600        # 10 min max per run
        )
        run_count[0] += 1
        log(f"✓ Job complete. Output:\n{result.stdout[-500:]}")
        if result.returncode != 0:
            log(f"⚠ Errors: {result.stderr[-300:]}")
    except subprocess.TimeoutExpired:
        log("✗ Job timed out after 10 minutes")
    except Exception as e:
        log(f"✗ Job failed: {e}")

# ══════════════════════════════════════════════════════
#  Schedule setup
# ══════════════════════════════════════════════════════

for t in SCRAPE_TIMES:
    schedule.every().day.at(t).do(scrape_job)
    log(f"📅 Scheduled daily scrape at {t}")

log(f"🚀 Scheduler started!")
log(f"   Start date : {START_DATE}")
log(f"   End date   : {END_DATE}")
log(f"   Scrape times: {SCRAPE_TIMES}")
log(f"   Press Ctrl+C to stop early\n")

# ══════════════════════════════════════════════════════
#  Run one scrape immediately at start
# ══════════════════════════════════════════════════════

log("Running first scrape now...")
scrape_job()

# ══════════════════════════════════════════════════════
#  Main loop
# ══════════════════════════════════════════════════════

while date.today() < END_DATE:
    schedule.run_pending()
    time.sleep(60)

log(f"🏁 All done! Total scrape runs: {run_count[0]}")
log(f"   Open dashboard: streamlit run dashboard.py")
