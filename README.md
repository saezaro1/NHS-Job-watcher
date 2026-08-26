# NHS Job Watcher (webpage version)

Checks a set of NHS job sources every hour for new FY1 / FY2 / Locally
Employed Doctor postings, and publishes the results to a simple webpage
you can bookmark and check. No email or password setup needed. Runs for
free on GitHub's own servers via GitHub Actions - nothing needs to stay
running on your computer or in your browser.

## Honest limitation before you start

This was built without the ability to actually test it against the live
websites (no internet access in the environment it was built in).
`jobclerk.com` (the two JobClerk sources) was tested earlier in a
separate conversation and its page structure is simple and reliable, so
those two should work as-is. The four individual trust career pages
(Shrewsbury and Telford, Derby and Burton, Mid and South Essex, East
Sussex) use a much looser, best-effort scraper, since every NHS trust
site is built differently and none of them were actually scraped and
verified here. **Expect to need to debug or tweak those four** - the
"Testing and debugging" section below shows you how.

## Setup

### 1. Create the repo
Create a new GitHub repository and add these files, keeping the folder
structure as-is:

```
your-repo/
├── job_watcher.py
├── requirements.txt
├── seen_jobs.json
├── index.html
├── README.md
└── .github/
    └── workflows/
        └── check_jobs.yml
```

This one can be **public** rather than private, since there's no email
address or password stored in it anymore - just be aware anything in a
public repo (including the job results once they start showing up) is
visible to anyone.

### 2. Let the workflow push updates
Go to your repo's **Settings → Actions → General**, scroll down to
**"Workflow permissions"**, and select **"Read and write permissions"**,
then save. Without this, the automated hourly commit will fail with a
permission error.

### 3. Turn on GitHub Pages
Go to **Settings → Pages**. Under "Build and deployment", set **Source**
to **"Deploy from a branch"**, then set **Branch** to **main** and the
folder to **/ (root)**, then save. GitHub will give you a URL, something
like `https://yourusername.github.io/your-repo-name/` - that's the page
to bookmark.

### 4. Test it
Go to the **Actions** tab, click **"NHS Job Watcher"** in the left
sidebar, then **"Run workflow"** to trigger it manually rather than
waiting for the hourly schedule.

### 5. Check the page
Give it a minute or two after the run finishes, then visit your GitHub
Pages URL from step 3. You should see either a list of current matching
postings, or "No matching postings found right now" if there genuinely
aren't any - both are working correctly. New postings you haven't seen
before are marked with a red NEW badge, tracked in your browser so it
remembers between visits.

## Testing and debugging

If a trust page keeps returning 0 links (check the "Run job watcher"
step's output in the Actions tab to see this), the most likely cause is
that the page loads its job listings with JavaScript after the initial
page load, which this scraper won't see. To check: open the URL in your
browser, right-click → "View Page Source" (not just "Inspect"), and
search for one of the job titles you can see on the page. If it's not in
the page source, that confirms it's JavaScript-rendered and this
scraper's approach won't catch it without a bigger change.

## Adjusting what counts as a match

Edit the `KEYWORDS` list near the top of `job_watcher.py`.

## Adjusting the schedule

The `cron: "0 * * * *"` line in `check_jobs.yml` means "every hour."
For every 3 hours instead: `cron: "0 */3 * * *"`.

## Turning it off

Delete the repository, or go to Settings → Actions → General and
disable Actions for the repo.
