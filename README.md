# 🔍 Job Scraper

A self-healing, multi-source remote job scraper built with Python. Searches across multiple job boards in priority order and automatically falls back to the next source if one is blocked or returns no results. No browser or WebDriver required.

---

## ✨ Features

- **Multi-source** — scrapes Jobicy, RemoteOK, and WeWorkRemotely
- **Auto fallback** — if one source fails or is blocked, moves to the next automatically
- **Deduplication** — never adds the same job twice across sources
- **Partial combining** — gets 10 from source 1, then 10 more from source 2 if needed
- **Retry logic** — exponential backoff on failures, handles rate limiting (429)
- **CSV export** — timestamped output file ready to open in Excel or Google Sheets
- **No browser needed** — uses `requests` + `BeautifulSoup`, no ChromeDriver issues

---

## 📸 Example Output

```
==================================================
  🔍 Job Scraper — multi-source + auto fallback
==================================================
  Keyword : backend developer
  Max jobs: 20
  Sources : jobicy → remoteok → wwremotely
  Output  : jobs_backend_developer_20240115_143022.csv
==================================================

──────────────────────────────────────────────────
📡 Source: JOBICY  (need 20 more jobs)
──────────────────────────────────────────────────
  ✅ [01] Backend Engineer — Stripe (Remote)
  ✅ [02] Python Developer — GitLab (Worldwide)
  ✅ [03] Senior Backend Dev — Shopify (Remote)
  ...
  ℹ️  jobicy: got 15 jobs (total so far: 15)

──────────────────────────────────────────────────
📡 Source: REMOTEOK  (need 5 more jobs)
──────────────────────────────────────────────────
  ✅ [16] Node.js Developer — StartupXYZ (Remote)
  ...
  ℹ️  remoteok: got 5 jobs (total so far: 20)

💾 Saved 20 jobs → 'jobs_backend_developer_20240115_143022.csv'

==================================================
  ✅ Done — 20 jobs collected
  📁 File: jobs_backend_developer_20240115_143022.csv
==================================================
```

---

## 🛠️ Tech Stack

- **Python 3.8+**
- **requests** — HTTP requests with retry logic
- **beautifulsoup4** — HTML parsing
- **csv** — built-in CSV export

---

## ⚙️ Installation

**1. Clone the repo**
```bash
git clone https://github.com/YOUR_USERNAME/job-scraper.git
cd job-scraper
```

**2. Create a virtual environment**
```bash
python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

---

## 🚀 Usage

**Basic — defaults to "python developer", 20 jobs**
```bash
python scraper.py
```

**Custom keyword**
```bash
python scraper.py --keyword "backend developer"
python scraper.py --keyword "devops engineer"
python scraper.py --keyword "data scientist"
```

**More jobs**
```bash
python scraper.py --keyword "python" --max 50
```

**Custom output filename**
```bash
python scraper.py --keyword "fullstack" --output my_results.csv
```

**Choose which sources to use and in what order**
```bash
python scraper.py --keyword "backend" --sources remoteok jobicy
python scraper.py --keyword "python" --sources jobicy
```

**All options**
```bash
python scraper.py --keyword "software engineer" --max 30 --output results.csv --sources jobicy remoteok wwremotely
```

---

## 📁 Project Structure

```
job-scraper/
├── scraper.py          # main scraper — all logic lives here
├── requirements.txt    # pip dependencies
├── .gitignore          # ignores venv and CSV output files
└── README.md           # this file
```

---

## 🏗️ Architecture

```
CLI args
   ↓
run_scraper()           ← orchestrator — tries sources in order
   ↓
for each source:
   fetch()              ← HTTP helper with retry + backoff
   scrape_*()           ← source-specific parser
   deduplicate          ← skip URLs already collected
   combine results
   ↓
save_to_csv()           ← write timestamped CSV file
```

**Sources tried in default order:**

| Priority | Source | Type | Notes |
|---|---|---|---|
| 1 | Jobicy | JSON API | Most reliable — structured data, no blocking |
| 2 | RemoteOK | HTML scraper | Great for tech roles, clean HTML |
| 3 | WeWorkRemotely | HTML scraper | Broad remote roles, last fallback |

---

## ⚠️ Notes

- Results are excluded from git via `.gitignore` — CSV files stay local
- A 2-second polite delay is added between requests
- Rate limiting (HTTP 429) is handled with automatic backoff
- For educational purposes — respect each site's Terms of Service

---

## 📄 License

MIT
