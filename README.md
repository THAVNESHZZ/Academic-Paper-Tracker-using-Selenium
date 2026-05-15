# Academic Paper Tracker

Monitor **arXiv** and **Google Scholar** for new papers in your field, get
AI-written summaries via Claude, download PDFs, and receive email digests — all
from the command line.

---

## Quick-start

```bash
# 1. Clone / copy the project folder
cd academic_paper_tracker

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) set your Anthropic API key for AI summaries
export ANTHROPIC_API_KEY="sk-ant-..."

# 5. Run
python paper_tracker.py
```

---

## Configuration

Open **`paper_tracker.py`** and edit the `CONFIG` dictionary at the top:

| Key | Default | Description |
|---|---|---|
| `keywords` | `["machine learning", …]` | Terms used to filter papers |
| `arxiv_categories` | `["cs.LG", …]` | arXiv category codes |
| `max_results` | `20` | Results fetched per category before filtering |
| `days_back` | `7` | Only papers from the last N days are kept |
| `download_dir` | `"papers"` | Folder for downloaded PDFs |
| `database_file` | `"papers_database.json"` | Persistent paper store |
| `anthropic_api_key` | `None` | Set or leave as env var `ANTHROPIC_API_KEY` |

---

## Email alerts & scheduling

Open **`enhanced_paper_tracker.py`** and fill in `EMAIL_CONFIG`:

```python
EMAIL_CONFIG = {
    "enabled": True,
    "from_email": "you@gmail.com",
    "to_email": "you@gmail.com",
    "password": "YOUR_APP_PASSWORD",   # Gmail → Settings → App Passwords
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
}
```

Then run:

```bash
# One-shot with email
python enhanced_paper_tracker.py

# Daily at 09:00 — edit the script and uncomment schedule_daily_tracking()
python enhanced_paper_tracker.py
```

---

## What gets stored

```
academic_paper_tracker/
├── paper_tracker.py          ← core tracker
├── enhanced_paper_tracker.py ← email + scheduling layer
├── requirements.txt
├── papers_database.json      ← auto-created, persists all tracked papers
├── papers/                   ← auto-created, holds downloaded PDFs
│   └── 2401.12345v1.pdf
└── paper_report_YYYYMMDD_HHMMSS.txt  ← plain-text report per run
```

---

## AI summaries

Summaries are generated with **claude-haiku** (fast, low-cost).  
Set the env var `ANTHROPIC_API_KEY` or add the key directly to `CONFIG`.  
Each summary is cached in `papers_database.json` so you're never charged twice
for the same paper.

---

## Citation / keyword monitoring

```python
tracker.run(
    check_my_citations=["your name", "your paper title", "your method name"]
)
```

Papers whose title or abstract contain any of those strings are printed in a
separate "mentions" section.

---

## Google Scholar note

Scholar actively rate-limits scrapers.  The tracker uses a polite 4-second
delay between keyword searches and caps requests at 3 keywords per run.  If you
hit a CAPTCHA wall, wait a few hours before re-running Scholar queries; arXiv
will still work fine.
