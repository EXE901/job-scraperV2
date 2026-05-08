"""
Job Scraper — multi-source, self-healing job scraper.

Scrapes from multiple job sites in priority order.
Falls back automatically if a site is blocked or returns no results.
Uses requests + BeautifulSoup (no browser needed — faster, no driver issues).

Sources (tried in order):
    1. Jobicy        — public JSON API, most reliable, no blocking
    2. RemoteOK      — best for remote tech jobs, clean HTML
    3. We Work Remotely — broad remote roles, clean HTML

Usage:
    python scraper.py --keyword "python developer" --max 20
    python scraper.py --keyword "devops" --max 50 --output results.csv
    python scraper.py --keyword "backend" --sources jobicy remoteok
"""

import csv
import sys
import time
import argparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime


# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 15    # seconds before giving up on a request
POLITE_DELAY    = 2     # seconds between requests — be a polite scraper


# ── HTTP helper ────────────────────────────────────────────────────────────────

def fetch(url: str, retries: int = 3, as_json: bool = False):
    """
    Fetch a URL with retry logic and polite delay.

    Tries up to `retries` times with exponential backoff.
    Returns response object, parsed JSON dict, or None on failure.
    Caller decides what to do with None — never crashes here.
    """
    time.sleep(POLITE_DELAY)   # always wait before hitting a server

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                if as_json:
                    try:
                        return response.json()
                    except Exception:
                        print(f"    ⚠️  Failed to parse JSON from {url}")
                        return None
                return response

            if response.status_code == 429:
                # 429 = Too Many Requests — back off and retry
                wait = 5 * attempt
                print(f"    ⏳ Rate limited — waiting {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)
                continue

            if response.status_code in (403, 503):
                # site is actively blocking us — no point retrying
                print(f"    🚫 Blocked (HTTP {response.status_code}) — moving to next source")
                return None

            print(f"    ⚠️  HTTP {response.status_code} on attempt {attempt}/{retries}")

        except requests.ConnectionError:
            print(f"    ❌ Connection error (attempt {attempt}/{retries})")
        except requests.Timeout:
            print(f"    ❌ Timeout (attempt {attempt}/{retries})")
        except Exception as e:
            print(f"    ❌ Unexpected error: {e}")

        if attempt < retries:
            time.sleep(2 * attempt)   # exponential backoff

    print(f"    ❌ All {retries} attempts failed for: {url}")
    return None


# ── Source 1: Jobicy JSON API ──────────────────────────────────────────────────

def scrape_jobicy(keyword: str, max_jobs: int) -> list[dict]:
    """
    Scrape remote jobs from Jobicy's public JSON API.

    Most reliable source — returns structured JSON with no HTML parsing,
    no bot protection, and no Cloudflare. Best first choice.
    """
    url = (
        f"https://jobicy.com/api/v2/remote-jobs"
        f"?count={max_jobs}&tag={keyword.replace(' ', '+')}"
    )

    print(f"  🌐 Jobicy API → {url}")
    data = fetch(url, as_json=True)

    if data is None:
        return []

    raw_jobs = data.get("jobs", [])

    if not raw_jobs:
        print("  ⚠️  Jobicy: empty jobs list in response")
        return []

    jobs = []
    for item in raw_jobs:
        if len(jobs) >= max_jobs:
            break
        try:
            title    = item.get("jobTitle",    "N/A")
            company  = item.get("companyName", "N/A")
            location = item.get("jobGeo",      "Remote")
            sal_min  = item.get("annualSalaryMin", "")
            sal_max  = item.get("annualSalaryMax", "")
            salary   = f"${sal_min}–${sal_max}" if sal_min and sal_max else "Not listed"
            tags     = ", ".join(item.get("jobIndustry", []))
            job_url  = item.get("url", "N/A")

            if title == "N/A" or company == "N/A":
                continue

            jobs.append(_make_job(title, company, location, salary, tags, job_url))

        except Exception:
            continue   # skip malformed entries silently

    return jobs


# ── Source 2: RemoteOK ─────────────────────────────────────────────────────────

def scrape_remoteok(keyword: str, max_jobs: int) -> list[dict]:
    """
    Scrape remote tech jobs from remoteok.com.

    Clean HTML, no Cloudflare, great for backend / devops / python roles.
    Good fallback when Jobicy doesn't have enough results.
    """
    formatted = keyword.strip().lower().replace(" ", "-")
    url = f"https://remoteok.com/remote-{formatted}-jobs"

    print(f"  🌐 RemoteOK → {url}")
    response = fetch(url)

    if response is None:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr", {"data-id": True})

    if not rows:
        print("  ⚠️  RemoteOK: no job rows found — site may have changed structure")
        return []

    jobs = []
    for row in rows:
        if len(jobs) >= max_jobs:
            break
        try:
            title   = _text(row, "h2", itemprop="title")
            company = _text(row, "h3", itemprop="name")

            if title == "N/A" or company == "N/A":
                continue

            location = _text(row, "div", class_="location") or "Remote"
            salary   = _text(row, "div", class_="salary")
            tag_els  = row.find_all("div", class_="tag")
            tags     = ", ".join(t.text.strip() for t in tag_els) if tag_els else "N/A"
            job_id   = row.get("data-id", "")
            job_url  = f"https://remoteok.com/remote-jobs/{job_id}" if job_id else "N/A"

            jobs.append(_make_job(title, company, location, salary, tags, job_url))

        except Exception:
            continue

    return jobs


# ── Source 3: We Work Remotely ─────────────────────────────────────────────────

def scrape_weworkremotely(keyword: str, max_jobs: int) -> list[dict]:
    """
    Scrape remote jobs from weworkremotely.com.

    Broad range of remote roles, clean HTML structure.
    Used as last fallback when other sources are insufficient.
    """
    formatted = keyword.strip().lower().replace(" ", "+")
    url = f"https://weworkremotely.com/remote-jobs/search?term={formatted}"

    print(f"  🌐 WeWorkRemotely → {url}")
    response = fetch(url)

    if response is None:
        return []

    soup     = BeautifulSoup(response.text, "html.parser")
    listings = soup.find_all("li", class_=lambda c: c and "feature" not in c)

    if not listings:
        print("  ⚠️  WeWorkRemotely: no listings found")
        return []

    jobs = []
    for item in listings:
        if len(jobs) >= max_jobs:
            break
        try:
            title_tag   = item.find("span", class_="title")
            company_tag = item.find("span", class_="company")
            region_tag  = item.find("span", class_="region")
            link_tag    = item.find("a", href=True)

            title   = title_tag.text.strip()   if title_tag   else None
            company = company_tag.text.strip() if company_tag else None

            if not title or not company:
                continue

            location = region_tag.text.strip() if region_tag else "Remote"
            job_url  = (
                f"https://weworkremotely.com{link_tag['href']}"
                if link_tag else "N/A"
            )

            jobs.append(_make_job(title, company, location, "Not listed", "N/A", job_url))

        except Exception:
            continue

    return jobs


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _text(tag, element: str, **attrs) -> str:
    """Find a child element and return its stripped text, or 'N/A'."""
    found = tag.find(element, attrs)
    return found.text.strip() if found else "N/A"


def _make_job(title, company, location, salary, tags, url) -> dict:
    """Build a standardised job dict — same shape regardless of source."""
    return {
        "title":      title,
        "company":    company,
        "location":   location,
        "salary":     salary,
        "tags":       tags,
        "url":        url,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ── Orchestrator — self-healing multi-source logic ─────────────────────────────

# Registry — maps CLI name → scraper function
SOURCES = {
    "jobicy":     scrape_jobicy,
    "remoteok":   scrape_remoteok,
    "wwremotely": scrape_weworkremotely,
}

# Default priority order — most reliable first
DEFAULT_ORDER = ["jobicy", "remoteok", "wwremotely"]


def run_scraper(keyword: str, max_jobs: int, source_order: list[str]) -> list[dict]:
    """
    Try each source in order until max_jobs is reached.

    If a source fails or returns nothing → automatically falls back.
    Deduplicates results across sources by URL.
    Combines partial results — e.g. 10 from source 1, 10 more from source 2.
    """
    all_jobs  = []
    seen_urls = set()   # track URLs to avoid duplicates across sources

    for source_name in source_order:
        if len(all_jobs) >= max_jobs:
            break   # got enough — stop

        scrape_fn = SOURCES.get(source_name)
        if scrape_fn is None:
            print(f"  ⚠️  Unknown source '{source_name}' — skipping")
            continue

        remaining = max_jobs - len(all_jobs)
        print(f"\n{'─' * 50}")
        print(f"📡 Source: {source_name.upper()}  (need {remaining} more jobs)")
        print(f"{'─' * 50}")

        try:
            jobs = scrape_fn(keyword, remaining)
        except Exception as e:
            print(f"  ❌ {source_name} crashed unexpectedly: {e}")
            jobs = []

        if not jobs:
            print(f"  ↩️  No results from {source_name} — trying next source")
            continue

        # deduplicate by URL — don't count the same job twice
        new_jobs = [j for j in jobs if j["url"] not in seen_urls]
        seen_urls.update(j["url"] for j in new_jobs)
        all_jobs.extend(new_jobs)

        start_idx = len(all_jobs) - len(new_jobs) + 1
        for i, job in enumerate(new_jobs, start=start_idx):
            print(f"  ✅ [{i:02d}] {job['title']} — {job['company']}")

        print(f"  ℹ️  {source_name}: got {len(new_jobs)} jobs (total so far: {len(all_jobs)})")

    return all_jobs


# ── CSV export ─────────────────────────────────────────────────────────────────

def save_to_csv(jobs: list[dict], filename: str) -> None:
    """Save job list to a timestamped CSV file."""
    if not jobs:
        print("\n⚠️  No jobs to save.")
        return

    fieldnames = ["title", "company", "location", "salary", "tags", "url", "scraped_at"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()    # column headers row
        writer.writerows(jobs)  # one row per job

    print(f"\n💾 Saved {len(jobs)} jobs → '{filename}'")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Multi-source remote job scraper with automatic fallback",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--keyword", default="python developer",
        help="Job title or skill to search for\n(default: python developer)"
    )
    parser.add_argument(
        "--max", type=int, default=20,
        help="Max number of jobs to collect (default: 20)"
    )
    parser.add_argument(
        "--output", default="",
        help="Output CSV filename (default: auto-generated)"
    )
    parser.add_argument(
        "--sources", nargs="+",
        choices=list(SOURCES.keys()),
        default=DEFAULT_ORDER,
        help=(
            "Sources to try in order\n"
            f"Choices: {', '.join(SOURCES.keys())}\n"
            "Default: jobicy remoteok wwremotely\n"
            "Example: --sources remoteok jobicy"
        )
    )

    args = parser.parse_args()

    # auto-generate output filename if not specified
    if not args.output:
        timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_keyword = args.keyword.replace(" ", "_")
        args.output  = f"jobs_{safe_keyword}_{timestamp}.csv"

    # header
    print("\n" + "=" * 50)
    print("  🔍 Job Scraper — multi-source + auto fallback")
    print("=" * 50)
    print(f"  Keyword : {args.keyword}")
    print(f"  Max jobs: {args.max}")
    print(f"  Sources : {' → '.join(args.sources)}")
    print(f"  Output  : {args.output}")
    print("=" * 50)

    # run
    jobs = run_scraper(
        keyword=args.keyword,
        max_jobs=args.max,
        source_order=args.sources,
    )

    # save
    save_to_csv(jobs, args.output)

    # summary
    print("\n" + "=" * 50)
    print(f"  ✅ Done — {len(jobs)} jobs collected")
    if len(jobs) < args.max:
        print(f"  ⚠️  Got {len(jobs)}/{args.max} — try a broader keyword")
    print(f"  📁 File: {args.output}")
    print("=" * 50 + "\n")

    # exit 1 if nothing found — useful if this is part of a pipeline or script
    sys.exit(0 if jobs else 1)


if __name__ == "__main__":
    main()
