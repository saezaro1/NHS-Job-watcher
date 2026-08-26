#!/usr/bin/env python3
"""
NHS Foundation/LED Job Watcher (webpage version)

Checks a set of sources for FY1 / FY2 / Locally Employed Doctor postings
and writes the results out to index.html, a simple page you can bookmark
and check whenever you like. No email setup needed.

Runs via GitHub Actions on a schedule (see .github/workflows/check_jobs.yml) -
there is nothing to keep running on your own computer.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timezone
from html import escape

# Titles that explicitly refer to a COMBINED FY1-FY2 style programme -
# e.g. "Locally Employed Doctor (FY1-FY2 equivalent)". This is the specific
# thing being looked for: a single rotational programme spanning both years,
# not a standalone FY1-only or FY2-only post.
COMBINED_PATTERNS = [
    "fy1-fy2", "fy1/fy2", "fy1 & fy2", "fy1&fy2", "fy1-2", "fy1/2",
    "fy1 and fy2", "fy1&2", "fy1 2 equivalent",
]

# Other strong signals of a structured, foundation-emulating LED programme,
# even when the title doesn't literally spell out "FY1" and "FY2" together -
# e.g. a trust's page describing its own rotational scheme in these terms.
PROGRAMME_KEYWORDS = [
    "locally employed doctor",
    "led foundation",
    "foundation equivalent",
    "foundation programme",
    "rotational foundation",
]


def matches_keywords(text):
    text_lower = text.lower()

    # Explicit combined-notation title (FY1-FY2, FY1/FY2, FY1-2, etc.)
    if any(pat in text_lower for pat in COMBINED_PATTERNS):
        return True

    # Both years mentioned somewhere in the title, even without a
    # hyphen/slash between them (e.g. "FY1 and FY2 rotational post").
    if "fy1" in text_lower and "fy2" in text_lower:
        return True

    # Other strong "structured programme" language, even without FY1/FY2
    # spelled out explicitly.
    if any(kw in text_lower for kw in PROGRAMME_KEYWORDS):
        return True

    # Deliberately NOT matching on a bare standalone "fy1" or "fy2" alone -
    # that would catch single-year, single-specialty posts too, which is
    # not what's being looked for here.
    return False

# jobclerk.com is the most reliable source here - it's a dedicated FY1/FY2
# job tracker and its page structure is simple and consistent, confirmed
# working for both the general FY1/FY2 hub pages and the one employer page
# (Chelsea and Westminster) actually fetched and checked earlier.
#
# The named trust pages are a mix of confidence levels - see the comment
# on each one. None of the "generic" ones were scraped and verified here,
# only found via search results describing what's on the page.
SOURCES = [
    {"name": "JobClerk - FY1 roles", "url": "https://www.jobclerk.com/jobs/fy1", "type": "jobclerk"},
    {"name": "JobClerk - FY2 roles", "url": "https://www.jobclerk.com/jobs/fy2", "type": "jobclerk"},

    # Confirmed structured FY1-FY2 rotational LED programmes
    {"name": "Shrewsbury and Telford", "url": "https://www.jobs.sath.nhs.uk/find-job/doctors", "type": "generic"},
    {"name": "Derby and Burton", "url": "https://www.uhdb.nhs.uk/current-jobs/", "type": "generic"},
    {"name": "Mid and South Essex", "url": "https://www.mse.nhs.uk/join-our-team/current-vacancies/", "type": "generic"},
    {"name": "East Sussex Healthcare", "url": "https://www.esht.nhs.uk/join-our-team/", "type": "generic"},

    # London North West University Healthcare (Northwick Park) - this exact
    # URL was actually fetched and returned real job listings earlier, so
    # reasonably confident in this one.
    {"name": "London North West Healthcare (Northwick Park)", "url": "https://www.nhsjobs.com/employerdetails/73/mir26/mar1/London_North_West_University_Healthcare_NHS_Trust", "type": "generic"},

    # University Hospitals Birmingham - confirmed they run a formal LED
    # programme with a dedicated handbook, but this specific jobs URL is
    # a guess based on the standard jobs.[trust].nhs.uk pattern, not
    # individually confirmed.
    {"name": "University Hospitals Birmingham", "url": "https://jobs.uhb.nhs.uk", "type": "generic"},

    # These five use jobclerk.com's employer-specific pages, same reliable
    # page structure as the FY1/FY2 hub above. Only the Chelsea and
    # Westminster URL was individually confirmed working - the other four
    # slugs are inferred from that pattern and may 404 if the exact naming
    # differs, in which case that source will just quietly return 0 results
    # rather than error out.
    {"name": "Chelsea and Westminster", "url": "https://www.jobclerk.com/employer/chelsea-and-westminster-hospital-nhs-foundation-trust/jobs", "type": "jobclerk"},
    {"name": "Manchester University NHS FT", "url": "https://www.jobclerk.com/employer/manchester-university-nhs-foundation-trust/jobs", "type": "jobclerk"},
    {"name": "Epsom and St Helier", "url": "https://www.jobclerk.com/employer/epsom-and-st-helier-university-hospitals-nhs-trust/jobs", "type": "jobclerk"},
    {"name": "North Bristol", "url": "https://www.jobclerk.com/employer/north-bristol-nhs-trust/jobs", "type": "jobclerk"},
    {"name": "Bedfordshire Hospitals (Luton and Dunstable)", "url": "https://www.jobclerk.com/employer/bedfordshire-hospitals-nhs-foundation-trust/jobs", "type": "jobclerk"},
]

STATE_FILE = "seen_jobs.json"
OUTPUT_FILE = "index.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; job-watcher/1.0)"}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def scrape_jobclerk(url):
    jobs = []
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if "/job/" in href and text:
                full_url = href if href.startswith("http") else f"https://www.jobclerk.com{href}"
                jobs.append({"title": text, "url": full_url})
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return jobs


def scrape_generic(url):
    """
    Best-effort scraper for individual trust career pages. See README for
    what to do if a source keeps coming back empty.
    """
    jobs = []
    try:
        resp = requests.get(url, timeout=20, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if text and 8 < len(text) < 120:
                full_url = a["href"] if a["href"].startswith("http") else url
                jobs.append({"title": text, "url": full_url})
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return jobs


def build_html(current_jobs, last_checked):
    """
    Builds a simple static page listing current matches. Uses the browser's
    own localStorage (not any Claude/artifact storage - this is a plain
    static HTML file, so ordinary browser localStorage works fine here) to
    remember what you've already seen on THIS device, so items you haven't
    looked at yet are visually marked NEW each time you open the page.
    """
    rows = []
    for job in current_jobs:
        rows.append(f"""
        <div class="job" data-key="{escape(job['title'])}|{escape(job['source'])}">
          <span class="new-badge">NEW</span>
          <a href="{escape(job['url'])}" target="_blank" rel="noopener">{escape(job['title'])}</a>
          <div class="source">{escape(job['source'])}</div>
        </div>""")

    jobs_html = "\n".join(rows) if rows else "<p>No matching postings found right now.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NHS Job Watcher</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 16px; color: #1a1a1a; }}
  h1 {{ font-size: 1.4em; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 24px; }}
  .job {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; position: relative; }}
  .job a {{ font-weight: 600; text-decoration: none; color: #1554d8; }}
  .job a:hover {{ text-decoration: underline; }}
  .source {{ color: #666; font-size: 0.85em; margin-top: 4px; }}
  .new-badge {{ display: none; position: absolute; top: 10px; right: 12px; background: #d92b2b; color: white; font-size: 0.7em; font-weight: 700; padding: 2px 8px; border-radius: 10px; }}
  .job.is-new .new-badge {{ display: inline-block; }}
  .refresh-note {{ margin-top: 24px; font-size: 0.85em; color: #888; }}
</style>
</head>
<body>
<h1>NHS Foundation / LED Job Watcher</h1>
<div class="meta">Last checked: {last_checked} UTC &middot; Checks run automatically every hour.</div>
<div id="jobs">
{jobs_html}
</div>
<p class="refresh-note">This page updates itself automatically. Refresh anytime to get the latest check - you don't need to keep this tab open for the checking to happen, that runs on GitHub's servers regardless.</p>

<script>
// Marks jobs as NEW if you haven't seen them on this device before, using
// this browser's own localStorage. This is plain browser storage on a
// static webpage - separate from anything else.
(function() {{
  const seenKey = 'nhs_job_watcher_seen';
  let seen = JSON.parse(localStorage.getItem(seenKey) || '[]');
  const seenSet = new Set(seen);
  const jobEls = document.querySelectorAll('.job');
  let newCount = 0;
  jobEls.forEach(function(el) {{
    const key = el.getAttribute('data-key');
    if (!seenSet.has(key)) {{
      el.classList.add('is-new');
      newCount++;
    }}
  }});
  // Mark everything currently shown as seen for next time.
  const allKeys = Array.from(jobEls).map(function(el) {{ return el.getAttribute('data-key'); }});
  localStorage.setItem(seenKey, JSON.stringify(allKeys));

  if (newCount > 0) {{
    document.title = '(' + newCount + ' new) NHS Job Watcher';
  }}
}})();
</script>
</body>
</html>"""


def main():
    state = load_state()
    all_current = []

    for source in SOURCES:
        if source["type"] == "jobclerk":
            jobs = scrape_jobclerk(source["url"])
        else:
            jobs = scrape_generic(source["url"])

        print(f"{source['name']}: fetched {len(jobs)} link(s)")

        for job in jobs:
            if matches_keywords(job["title"]):
                job["source"] = source["name"]
                all_current.append(job)

    last_checked = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    html = build_html(all_current, last_checked)

    with open(OUTPUT_FILE, "w") as f:
        f.write(html)

    print(f"Wrote {OUTPUT_FILE} with {len(all_current)} matching job(s).")

    state["last_checked"] = last_checked
    state["job_count"] = len(all_current)
    save_state(state)


if __name__ == "__main__":
    main()
