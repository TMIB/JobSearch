# Agentic Job Search Pipeline

An AI-powered job search system that runs daily, finds relevant listings, evaluates them with reasoning (not keyword matching), generates tailored resumes, and notifies you when new leads are ready.

## What This Is

This is a starting point for building your own automated job search pipeline using [Claude Code](https://claude.ai/code). It's not a turnkey app you install and run — it's a set of agent prompts, config files, and scripts that you customize to your career profile, then use Claude Code interactively to tune and improve over time.

**The key idea:** Four specialized AI agents work together in a pipeline. Each has its own prompt file and feedback file. You review the output, tell Claude what it got wrong, and the system gets smarter with each run. After a few days of tuning, it produces leads and resumes that genuinely match what you're looking for.

**This tool is designed to be used with Claude Code in an interactive conversational manner.** You'll work with Claude to:
- Fill in your career profile and experience inventory
- Review generated resumes and flag issues ("don't lead with that bullet for AI roles," "that company is actually on-site, not remote")
- Add calibration examples when the scoring is off
- Generate cover letters for specific roles
- Process individual listings you find yourself (`--url` mode)

The automation handles the daily grind of searching and filtering. The interactive Claude sessions handle the judgment calls.

## How It Works

Four specialized agents, each with its own tunable prompt:

1. **Search Agent** (Sonnet) — Queries SerpAPI Google Jobs API, which aggregates listings from Indeed, Glassdoor, LinkedIn, Ladders, ZipRecruiter, and dozens more. Returns full job descriptions, salary data, and application links. Rotates through your search queries over a 4-5 day cycle.

2. **Evaluation Agent** (Sonnet) — Scores each listing on 6 weighted dimensions: level match, role category, location fit, coding interview risk, narrative fit, and company maturity. Uses AI reasoning to distinguish "Director of QA Engineering" from "QA Engineer," detect fake Director titles at tiny startups, and assess coding interview risk from company culture signals. Has a feedback file where your corrections accumulate, so it calibrates over time.

3. **Resume Tailoring Agent** (Opus) — Takes above-threshold leads and generates a customized HTML resume aligned to each listing's keywords and requirements. Uses an experience inventory that tracks what keywords are safe vs. what would overstate your experience. Builds a library of approved resumes and reuses them as starting points for similar future roles.

4. **Orchestrator** — Shell script that coordinates the pipeline, deduplicates against previous runs, converts resumes to PDF via headless Chrome, generates an HTML report with color-coded scores and clickable links, and sends a desktop notification.

## Getting Started

### Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed and authenticated
- [SerpAPI](https://serpapi.com) account (free tier: 250 searches/month, or $25/month for 1,000)
- Google Chrome (for headless PDF generation — auto-detected on macOS, Linux, and WSL)
- Python 3 (for report generation and JSON parsing)
- Bash (macOS/Linux natively, Windows via Git Bash or WSL)

### Step 1: Clone the project

```bash
git clone https://github.com/TMIB/JobSearch.git
cd JobSearch
```

All script paths are relative to the project root — no path configuration needed. Clone it wherever you like.

### Step 2: Add your SerpAPI key

Sign up at [serpapi.com](https://serpapi.com) (free tier, no credit card). Copy your API key from the dashboard and add it to:

- `automation/run_search.sh` — replace `YOUR_SERPAPI_KEY_HERE`
- `automation/serpapi_search.sh` — replace `YOUR_API_KEY_HERE`

### Step 3: Configure your career profile

This is the most important step. Open Claude Code in this project directory and work with Claude to fill in:

- **`CLAUDE.md`** — Your career background, target roles, confirmed experience details, and critical rules (what to never fabricate, what titles are accurate, etc.)
- **`career/career_strategy_guide.md`** — Your situation assessment, target role categories, external narrative, and constraints
- **`automation/experience_inventory.yaml`** — Your skills with safe/avoid keywords, certifications, industry preferences, and per-role-category guidance
- **`automation/eval_agent_prompt.md`** — The "Who [CANDIDATE] Is" section needs your profile

Tell Claude about your background and let it help you structure these files. The more honest and detailed you are here, the better the output.

### Step 4: Customize your search queries

Edit `queries.txt` with searches tailored to your target roles, industries, and locations. The search agent rotates through ~12 queries per day, so include enough to cover your target categories.

### Step 5: Create your first resume template

Create at least one hand-crafted HTML resume in a `leads/` subfolder. This becomes the template the resume agent uses as a starting point. Look at the HTML/CSS conventions in `CLAUDE.md` for the expected format (Georgia serif font, letter-size margins, break-inside:avoid, etc.).

Place your current resume PDF in the project root as a reference.

### Step 6: Test run

```bash
# Search only — verify SerpAPI works and listings come back
./automation/run_search.sh --search-only

# Full pipeline — search, evaluate, generate resumes + PDFs
./automation/run_search.sh

# Process a specific listing URL you found yourself
./automation/run_search.sh --url "https://example.com/job/12345"

# Skip evaluation for a URL (you already know it's a good fit)
./automation/run_search.sh --url "https://example.com/job/12345" --skip-eval
```

After the first run, open `leads/new_leads_report.html` in your browser and review the results with Claude. Flag what's wrong — this is where the tuning begins.

### Step 7: Schedule daily runs

**macOS (launchd):**
Edit `automation/com.jobsearch.plist` — replace `/path/to/your/project` with your actual project path (launchd requires absolute paths). Then:
```bash
cp automation/com.jobsearch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jobsearch.plist
```

**Linux (cron):**
```bash
crontab -e
# Add this line (adjust the path):
0 7 * * * /path/to/your/project/automation/run_search.sh >> /path/to/your/project/automation/logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
Create a scheduled task that runs daily and executes:
```
bash C:\path\to\your\project\automation\run_search.sh
```
Requires Git Bash or WSL.

Runs daily at 7 AM. Edit the plist to change the time. If your Mac is asleep, it fires when it wakes.

## Daily Workflow

1. Pipeline runs automatically, you get a macOS notification
2. Open `leads/new_leads_report.html` in your browser
3. Review leads — each card has score badges, apply links, and local file links to the listing, resume, and PDF
4. Open Claude Code and work through the results:
   - "This role is actually on-site in Ohio, not remote" → Claude logs it to eval feedback
   - "The resume for Acme Corp has a bad page break" → Claude fixes it and logs the pattern
   - "I applied for the Acme Corp role" → Claude tracks it in applications.yaml
   - "I need a cover letter for this one" → Claude generates it
5. Each correction makes the next run more accurate

## Tuning the System

The system improves through three feedback loops:

| Agent | Config | Feedback | What You Tune |
|-------|--------|----------|---------------|
| Search | `queries.txt` | — | Which queries, platforms |
| Evaluation | `search_config.yaml` | `automation/eval_feedback.yaml` | Scoring weights, thresholds, calibration examples |
| Resume | `automation/experience_inventory.yaml` | `automation/resume_feedback.yaml` | Keywords, emphasis, quality corrections |

**Common adjustments after the first few runs:**
- Too many false positives? Raise `generate_resume` threshold in `search_config.yaml`
- On-site roles scoring too high? The eval prompt has a location score cap — adjust it
- Wrong role types getting through? Add dealbreakers to `search_config.yaml`
- Resume quality issues? Add corrections to `resume_feedback.yaml` with severity levels
- Scoring a role type wrong? Add a calibration example to `eval_feedback.yaml`

## Lessons Learned

These tips come from real-world usage of this pipeline:

- **SerpAPI location data is unreliable.** "Remote (Anywhere)" sometimes means hybrid on-site. The eval agent should read the full description for on-site signals, not trust metadata.
- **Aggregator sites (Virtual Vocations, BeBee, talent.com) often have stale listings.** Flag them with higher stale risk.
- **"Director" at a 10-person startup with 3 IC reports is not a real Director.** Teach the eval agent to check team size, reporting structure, and company size.
- **Hourly rates at staffing firms signal contract roles, not FTE.** Convert to annual and compare to your floor.
- **Location-based pay bands matter.** Check your city's band, not the SF/NYC number.
- **The resume agent will create too many full job sections and break page layout.** Budget 4-5 full sections max, fold the rest into single-line entries in Additional Experience.
- **Never use internal tool names or codenames in external documents.**
- **The first run is the noisiest.** After 2-3 days of feedback, the quality improves dramatically.

## Cost

- **SerpAPI:** Free tier (250/month) or $25/month for 1,000 searches
- **Claude API:** ~$3-8/day depending on how many resumes are generated
  - Search (Sonnet): ~$0.30/run
  - Evaluation (Sonnet): ~$0.20/run
  - Resume (Opus): ~$1.50 per resume
- **Budget cap:** Configurable in `search_config.yaml` (recommend $20/run during initial tuning, lower to $5-10 after)

## File Structure

```
project/
├── README.md                              # This file
├── CLAUDE.md                              # Your career profile and rules (customize)
├── queries.txt                            # Search queries (customize)
├── search_config.yaml                     # Scoring config (mostly ready, tune over time)
├── career/
│   └── career_strategy_guide.md           # Career strategy (customize)
├── automation/
│   ├── search_agent_prompt.md             # Search agent instructions
│   ├── eval_agent_prompt.md               # Eval agent instructions (customize profile section)
│   ├── eval_feedback.yaml                 # Your eval corrections (grows over time)
│   ├── resume_agent_prompt.md             # Resume agent instructions (customize experience section)
│   ├── resume_feedback.yaml               # Your resume corrections (grows over time)
│   ├── experience_inventory.yaml          # Your skills/keywords reference (customize)
│   ├── serpapi_search.sh                  # SerpAPI helper (add API key)
│   ├── run_search.sh                      # Main orchestrator (update paths + API key)
│   ├── generate_html_report.py            # HTML report generator
│   ├── com.jobsearch.plist                # launchd schedule (update paths)
│   └── logs/                              # Run logs (auto-created)
└── leads/
    ├── applications.yaml                  # Application tracker
    ├── seen_listings.jsonl                # Dedup tracker (auto-created)
    ├── new_leads_report.html              # Daily HTML report (auto-created)
    └── {CompanyName}/                     # One folder per lead (auto-created)
        ├── {CompanyName}.txt              # Job listing text
        ├── fit_analysis.md                # Evaluation reasoning + resume strategy
        ├── resume_*.html                  # Tailored resume
        └── [Name] - Resume.pdf            # Auto-generated PDF
```

## Credits

Built with [Claude Code](https://claude.ai/code), April 2026.
