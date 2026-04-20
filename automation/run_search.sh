#!/bin/bash
#
# Job Search Pipeline Orchestrator
# Runs daily via launchd. Coordinates search, evaluation, and resume agents.
#
# Usage:
#   ./automation/run_search.sh                    # Full daily pipeline
#   ./automation/run_search.sh --search-only      # Search only, no eval or resume
#   ./automation/run_search.sh --skip-resume      # Search + eval, no resume generation
#   ./automation/run_search.sh --url <URL>        # Process a single listing URL (fetch → eval → resume)
#   ./automation/run_search.sh --url <URL> --skip-eval  # Fetch + resume, skip evaluation (assume it's a good match)
#

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
PROJECT_DIR="/Users/YOURNAME/code/jobs"
AUTOMATION_DIR="${PROJECT_DIR}/automation"
TMP_DIR="${AUTOMATION_DIR}/tmp"
LOG_DIR="${AUTOMATION_DIR}/logs"
LEADS_DIR="${PROJECT_DIR}/leads"

SEARCH_PROMPT="${AUTOMATION_DIR}/search_agent_prompt.md"
EVAL_PROMPT="${AUTOMATION_DIR}/eval_agent_prompt.md"
RESUME_PROMPT="${AUTOMATION_DIR}/resume_agent_prompt.md"
CONFIG_FILE="${PROJECT_DIR}/search_config.yaml"

CLAUDE_BIN="/usr/local/bin/claude"
SERPAPI_KEY="YOUR_SERPAPI_KEY_HERE"
RUN_DATE=$(date +%Y-%m-%d)
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/run_${RUN_TIMESTAMP}.log"

# Parse budget from config (default $20 during tuning period)
BUDGET_CAP=$(grep 'budget_cap_usd:' "$CONFIG_FILE" 2>/dev/null | awk '{print $2}' || echo "20")

# ── Flags ──────────────────────────────────────────────────────────────────────
SEARCH_ONLY=false
SKIP_RESUME=false
SKIP_EVAL=false
SINGLE_URL=""
for arg in "$@"; do
  case $arg in
    --search-only) SEARCH_ONLY=true ;;
    --skip-resume) SKIP_RESUME=true ;;
    --skip-eval) SKIP_EVAL=true ;;
    --url) ;; # handled below
    *) # capture the URL value after --url
      if [ "${prev_arg:-}" = "--url" ]; then
        SINGLE_URL="$arg"
      fi
      ;;
  esac
  prev_arg="$arg"
done
# Also handle --url=VALUE format
for arg in "$@"; do
  case $arg in
    --url=*) SINGLE_URL="${arg#--url=}" ;;
  esac
done

# ── Helper Functions ───────────────────────────────────────────────────────────

log() {
  echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify() {
  local title="$1"
  local message="$2"
  local sound="${3:-Glass}"
  osascript -e "display notification \"$message\" with title \"$title\" sound name \"$sound\"" 2>/dev/null || true
}

preflight_check() {
  local errors=0

  if [ ! -x "$CLAUDE_BIN" ]; then
    log "ERROR: claude binary not found at $CLAUDE_BIN"
    errors=$((errors + 1))
  fi

  for f in "$SEARCH_PROMPT" "$EVAL_PROMPT" "$RESUME_PROMPT" "$CONFIG_FILE"; do
    if [ ! -f "$f" ]; then
      log "ERROR: Required file missing: $f"
      errors=$((errors + 1))
    fi
  done

  if [ $errors -gt 0 ]; then
    notify "Job Search Error" "$errors preflight errors. Check $LOG_FILE" "Basso"
    exit 1
  fi
}

cleanup_old_logs() {
  find "$LOG_DIR" -name "run_*.log" -mtime +30 -delete 2>/dev/null || true
}

# ── Single URL Pipeline ────────────────────────────────────────────────────────

run_single_url() {
  local url="$1"

  log "═══════════════════════════════════════════════════"
  log "Single URL Pipeline — $RUN_DATE"
  log "URL: $url"
  log "═══════════════════════════════════════════════════"

  preflight_check

  rm -f "$TMP_DIR"/search_results.json "$TMP_DIR"/evaluated_leads.json "$TMP_DIR"/resume_report.json

  # ── Fetch the listing ────────────────────────────────────────────────────
  log ""
  log "Phase 1: FETCH — Scraping job listing..."
  log "──────────────────────────────────────────"

  "$CLAUDE_BIN" -p "Fetch this job listing URL and extract structured data. URL: $url

Today's date is $RUN_DATE. Use WebFetch to get the page content. Extract all available fields (title, company, location, compensation, requirements, responsibilities, about_company, application_url, date_posted, raw_text). Write the result to automation/tmp/search_results.json in this format:
{
  \"run_date\": \"$RUN_DATE\",
  \"queries_executed\": 0,
  \"results_found\": 1,
  \"results_fetched\": 1,
  \"fetch_failures\": 0,
  \"listings\": [{ ...extracted data... }]
}
Set the url field to: $url" \
    --append-system-prompt "$(cat "$SEARCH_PROMPT")" \
    --model sonnet \
    --allowed-tools "WebSearch WebFetch Read Write Bash Glob Grep" \
    --permission-mode bypassPermissions \
    --max-budget-usd 2 \
    --no-session-persistence \
    --add-dir "$PROJECT_DIR" \
    >> "$LOG_FILE" 2>&1

  if [ ! -f "$TMP_DIR/search_results.json" ]; then
    log "ERROR: Failed to fetch listing from $url"
    notify "Job Search Error" "Could not fetch listing from URL. Check log." "Basso"
    exit 1
  fi

  log "Listing fetched successfully."

  # ── Evaluate (unless --skip-eval) ────────────────────────────────────────
  if [ "$SKIP_EVAL" = true ]; then
    log ""
    log "Skipping evaluation (--skip-eval). Generating resume directly."

    # Create a passthrough evaluated_leads.json with action=generate_resume
    python3 << PYEOF
import json
with open("$TMP_DIR/search_results.json") as f:
    data = json.load(f)
leads = []
for listing in data.get("listings", []):
    listing["final_score"] = 1.0
    listing["scores"] = {}
    listing["reasoning"] = {"note": "Manual submission — evaluation skipped"}
    listing["action"] = "generate_resume"
    listing["dealbreaker"] = None
    listing["category"] = "qa_leadership"
    listing["best_template"] = "RemoteHunter"
    listing["narrative_angle"] = "To be determined during resume generation"
    leads.append(listing)
result = {
    "run_date": "$RUN_DATE",
    "total_evaluated": len(leads),
    "above_resume_threshold": len(leads),
    "above_report_threshold": len(leads),
    "dealbreaker_rejections": 0,
    "duplicates_skipped": 0,
    "leads": leads
}
with open("$TMP_DIR/evaluated_leads.json", "w") as f:
    json.dump(result, f, indent=2)
PYEOF
  else
    log ""
    log "Phase 2: EVALUATE — Scoring listing..."
    log "──────────────────────────────────────────"

    "$CLAUDE_BIN" -p "Execute the evaluation agent workflow. Today's date is $RUN_DATE. Read the evaluation agent prompt, config, search results, and feedback. Score the listing and write results to automation/tmp/evaluated_leads.json. Also update leads/seen_listings.jsonl." \
      --append-system-prompt "$(cat "$EVAL_PROMPT")" \
      --model sonnet \
      --allowed-tools "Read Write Bash Glob Grep" \
      --permission-mode bypassPermissions \
      --max-budget-usd 2 \
      --no-session-persistence \
      --add-dir "$PROJECT_DIR" \
      >> "$LOG_FILE" 2>&1

    if [ ! -f "$TMP_DIR/evaluated_leads.json" ]; then
      log "ERROR: Evaluation agent failed"
      notify "Job Search Error" "Evaluation failed. Check log." "Basso"
      exit 1
    fi

    local score
    score=$(python3 -c "import json; d=json.load(open('$TMP_DIR/evaluated_leads.json')); leads=d.get('leads',[]); print(f'{leads[0][\"final_score\"]:.2f}' if leads else '0')" 2>/dev/null || echo "?")
    log "Evaluation complete. Score: $score"
  fi

  # ── Generate Resume ──────────────────────────────────────────────────────
  local should_resume
  should_resume=$(python3 -c "import json; d=json.load(open('$TMP_DIR/evaluated_leads.json')); print('yes' if any(l.get('action')=='generate_resume' for l in d.get('leads',[])) else 'no')" 2>/dev/null || echo "no")

  if [ "$should_resume" = "yes" ]; then
    log ""
    log "Phase 3: RESUME — Generating tailored resume..."
    log "──────────────────────────────────────────"

    "$CLAUDE_BIN" -p "Execute the resume tailoring agent workflow. Today's date is $RUN_DATE. Read the resume agent prompt, evaluated leads, CLAUDE.md, experience inventory, resume feedback, and the appropriate HTML templates. For each lead with action 'generate_resume', create the folder, save the listing, write the fit analysis, and generate the tailored resume HTML. Write a summary to automation/tmp/resume_report.json." \
      --append-system-prompt "$(cat "$RESUME_PROMPT")" \
      --model opus \
      --allowed-tools "Read Write Bash Glob Grep" \
      --permission-mode bypassPermissions \
      --max-budget-usd 5 \
      --no-session-persistence \
      --add-dir "$PROJECT_DIR" \
      >> "$LOG_FILE" 2>&1

    if [ -f "$TMP_DIR/resume_report.json" ]; then
      local company
      company=$(python3 -c "import json; d=json.load(open('$TMP_DIR/resume_report.json')); lp=d.get('leads_processed',[]); print(lp[0]['company'] if lp else 'Unknown')" 2>/dev/null || echo "Unknown")
      log "Resume generated for $company."

      # Generate PDF
      log "Generating PDF..."
      generate_pdfs
      notify "Job Search: Resume Ready" "Resume + PDF generated for $company" "Glass"
    else
      log "WARNING: Resume agent did not produce resume_report.json"
      notify "Job Search" "Listing fetched but resume generation may have failed. Check log." "Pop"
    fi
  else
    local score
    score=$(python3 -c "import json; d=json.load(open('$TMP_DIR/evaluated_leads.json')); leads=d.get('leads',[]); print(f'{leads[0][\"final_score\"]:.2f}' if leads else '?')" 2>/dev/null || echo "?")
    log "Listing scored $score — below resume threshold. No resume generated."
    notify "Job Search" "Listing scored $score — below resume threshold ($(grep 'generate_resume:' "$CONFIG_FILE" | awk '{print $2}')). Check leads/new_leads_report.md" "Pop"
  fi

  # Generate report
  generate_report
  PROJECT_DIR="$PROJECT_DIR" python3 "${AUTOMATION_DIR}/generate_html_report.py" >> "$LOG_FILE" 2>&1

  log ""
  log "Single URL pipeline complete."
}

# ── Main Pipeline ──────────────────────────────────────────────────────────────

main() {
  mkdir -p "$TMP_DIR" "$LOG_DIR"

  # Route to single-URL mode if --url was provided
  if [ -n "$SINGLE_URL" ]; then
    run_single_url "$SINGLE_URL"
    cleanup_old_logs
    return
  fi

  log "═══════════════════════════════════════════════════"
  log "Job Search Pipeline — $RUN_DATE"
  log "═══════════════════════════════════════════════════"

  preflight_check

  # Clean up previous tmp files
  rm -f "$TMP_DIR"/search_results.json "$TMP_DIR"/evaluated_leads.json "$TMP_DIR"/resume_report.json

  # ── Phase 1: Search ────────────────────────────────────────────────────────
  log ""
  log "Phase 1: SEARCH — Finding job listings..."
  log "──────────────────────────────────────────"

  local search_budget=$(echo "$BUDGET_CAP * 0.25" | bc)

  SERPAPI_KEY="$SERPAPI_KEY" "$CLAUDE_BIN" -p "Execute the search agent workflow. Today's date is $RUN_DATE. Read the search agent prompt, config, queries, and seen listings, then search for job listings using SerpAPI (via ./automation/serpapi_search.sh) as the primary source and WebSearch as supplementary. Write results to automation/tmp/search_results.json." \
    --append-system-prompt "$(cat "$SEARCH_PROMPT")" \
    --model sonnet \
    --allowed-tools "WebSearch WebFetch Read Write Bash Glob Grep" \
    --permission-mode bypassPermissions \
    --max-budget-usd "$search_budget" \
    --no-session-persistence \
    --add-dir "$PROJECT_DIR" \
    >> "$LOG_FILE" 2>&1

  if [ ! -f "$TMP_DIR/search_results.json" ]; then
    log "ERROR: Search agent did not produce search_results.json"
    notify "Job Search Error" "Search agent failed. Check log." "Basso"
    exit 1
  fi

  local results_count
  results_count=$(python3 -c "import json; d=json.load(open('$TMP_DIR/search_results.json')); print(len(d.get('listings', [])))" 2>/dev/null || echo "0")
  log "Search found $results_count listings."

  if [ "$results_count" = "0" ]; then
    log "No listings found. Exiting."
    notify "Job Search" "No new listings found today." "Pop"
    cleanup_old_logs
    exit 0
  fi

  if [ "$SEARCH_ONLY" = true ]; then
    log "Search-only mode. Exiting."
    notify "Job Search" "Search complete: $results_count listings found. Review automation/tmp/search_results.json" "Glass"
    exit 0
  fi

  # ── Phase 2: Evaluate ──────────────────────────────────────────────────────
  log ""
  log "Phase 2: EVALUATE — Scoring listings..."
  log "──────────────────────────────────────────"

  local eval_budget=$(echo "$BUDGET_CAP * 0.25" | bc)

  "$CLAUDE_BIN" -p "Execute the evaluation agent workflow. Today's date is $RUN_DATE. Read the evaluation agent prompt, config, search results, feedback, and seen listings. Score each listing and write results to automation/tmp/evaluated_leads.json. Also update leads/seen_listings.jsonl." \
    --append-system-prompt "$(cat "$EVAL_PROMPT")" \
    --model sonnet \
    --allowed-tools "Read Write Bash Glob Grep" \
    --permission-mode bypassPermissions \
    --max-budget-usd "$eval_budget" \
    --no-session-persistence \
    --add-dir "$PROJECT_DIR" \
    >> "$LOG_FILE" 2>&1

  if [ ! -f "$TMP_DIR/evaluated_leads.json" ]; then
    log "ERROR: Evaluation agent did not produce evaluated_leads.json"
    notify "Job Search Error" "Evaluation agent failed. Check log." "Basso"
    exit 1
  fi

  local resume_count
  resume_count=$(python3 -c "import json; d=json.load(open('$TMP_DIR/evaluated_leads.json')); print(len([l for l in d.get('leads', []) if l.get('action') == 'generate_resume']))" 2>/dev/null || echo "0")
  local report_count
  report_count=$(python3 -c "import json; d=json.load(open('$TMP_DIR/evaluated_leads.json')); print(len([l for l in d.get('leads', []) if l.get('action') in ('generate_resume', 'report_only')]))" 2>/dev/null || echo "0")
  log "Evaluation complete: $resume_count above resume threshold, $report_count worth reporting."

  # ── Phase 3: Resume Generation ─────────────────────────────────────────────
  if [ "$resume_count" != "0" ] && [ "$SKIP_RESUME" = false ]; then
    log ""
    log "Phase 3: RESUME — Generating tailored resumes..."
    log "──────────────────────────────────────────"

    local resume_budget=$(echo "$BUDGET_CAP * 0.50" | bc)

    "$CLAUDE_BIN" -p "Execute the resume tailoring agent workflow. Today's date is $RUN_DATE. Read the resume agent prompt, evaluated leads, CLAUDE.md, and the appropriate HTML templates. For each lead with action 'generate_resume', create the folder, save the listing, write the fit analysis, and generate the tailored resume HTML. Write a summary to automation/tmp/resume_report.json." \
      --append-system-prompt "$(cat "$RESUME_PROMPT")" \
      --model opus \
      --allowed-tools "Read Write Bash Glob Grep" \
      --permission-mode bypassPermissions \
      --max-budget-usd "$resume_budget" \
      --no-session-persistence \
      --add-dir "$PROJECT_DIR" \
      >> "$LOG_FILE" 2>&1

    if [ -f "$TMP_DIR/resume_report.json" ]; then
      local resumes_generated
      resumes_generated=$(python3 -c "import json; d=json.load(open('$TMP_DIR/resume_report.json')); print(d.get('resumes_generated', 0))" 2>/dev/null || echo "0")
      log "Generated $resumes_generated tailored resumes."
    else
      log "WARNING: Resume agent did not produce resume_report.json"
    fi
  else
    if [ "$SKIP_RESUME" = true ]; then
      log "Skipping resume generation (--skip-resume flag)."
    else
      log "No leads above resume threshold. Skipping resume generation."
    fi
  fi

  # ── Phase 3b: PDF Generation ──────────────────────────────────────────────
  if [ "$resume_count" != "0" ] && [ "$SKIP_RESUME" = false ]; then
    log ""
    log "Phase 3b: PDF — Converting resumes to PDF..."
    log "──────────────────────────────────────────"
    generate_pdfs
  fi

  # ── Phase 4: Report Generation ─────────────────────────────────────────────
  log ""
  log "Phase 4: REPORT — Generating daily report..."
  log "──────────────────────────────────────────"

  generate_report

  # Generate HTML version of the report
  log "Generating HTML report..."
  PROJECT_DIR="$PROJECT_DIR" python3 "${AUTOMATION_DIR}/generate_html_report.py" >> "$LOG_FILE" 2>&1

  # ── Notification ────────────────────────────────────────────────────────────
  if [ "$resume_count" != "0" ]; then
    local companies
    companies=$(python3 -c "
import json
d = json.load(open('$TMP_DIR/evaluated_leads.json'))
names = [l['company'] for l in d.get('leads', []) if l.get('action') == 'generate_resume']
print(', '.join(names[:5]))
" 2>/dev/null || echo "check report")
    notify "Job Search: $resume_count New Leads" "$companies" "Glass"
  elif [ "$report_count" != "0" ]; then
    notify "Job Search" "$report_count listings worth reviewing (below resume threshold)" "Pop"
  else
    notify "Job Search" "No new matching listings today." "Pop"
  fi

  cleanup_old_logs
  log ""
  log "Pipeline complete."
}

# ── PDF Generator ────────────────────────────────────────────────────────────

CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

generate_pdfs() {
  if [ ! -x "$CHROME_BIN" ]; then
    log "WARNING: Chrome not found at $CHROME_BIN — skipping PDF generation"
    return
  fi

  local pdf_count=0

  if [ -f "$TMP_DIR/resume_report.json" ]; then
    # Get list of generated resume files from the report
    python3 -c "
import json, os
with open('$TMP_DIR/resume_report.json') as f:
    d = json.load(f)
for lead in d.get('leads_processed', []):
    folder = lead.get('folder', '')
    resume = lead.get('resume_file', '')
    if folder and resume:
        html_path = os.path.join('$PROJECT_DIR', folder, resume)
        if os.path.exists(html_path):
            print(html_path)
" 2>/dev/null | while read -r html_file; do
      local pdf_file
      pdf_file="$(dirname "$html_file")/YOUR NAME - Resume.pdf"

      # Skip if PDF already exists (don't overwrite manual prints)
      if [ -f "$pdf_file" ]; then
        log "  PDF already exists: $(basename "$(dirname "$html_file")")"
        continue
      fi

      "$CHROME_BIN" \
        --headless \
        --disable-gpu \
        --no-pdf-header-footer \
        --print-to-pdf="$pdf_file" \
        "$html_file" 2>/dev/null

      if [ -f "$pdf_file" ]; then
        pdf_count=$((pdf_count + 1))
      fi
    done
  else
    # Fallback: find any resume HTML without a corresponding PDF
    find "$LEADS_DIR" -name "resume_*.html" | while read -r html_file; do
      local pdf_file
      pdf_file="$(dirname "$html_file")/YOUR NAME - Resume.pdf"

      if [ -f "$pdf_file" ]; then
        continue
      fi

      "$CHROME_BIN" \
        --headless \
        --disable-gpu \
        --no-pdf-header-footer \
        --print-to-pdf="$pdf_file" \
        "$html_file" 2>/dev/null

      if [ -f "$pdf_file" ]; then
        pdf_count=$((pdf_count + 1))
      fi
    done
  fi

  log "Generated PDFs for new resumes."
}

# ── Report Generator ─────────────────────────────────────────────────────────

generate_report() {
  local report_file="${LEADS_DIR}/new_leads_report.md"

  python3 << 'PYEOF' > "$report_file"
import json
import os
from datetime import datetime

eval_file = os.environ.get("TMP_DIR", "automation/tmp") + "/evaluated_leads.json"
resume_file = os.environ.get("TMP_DIR", "automation/tmp") + "/resume_report.json"

try:
    with open(eval_file) as f:
        evals = json.load(f)
except:
    evals = {"leads": [], "total_evaluated": 0}

try:
    with open(resume_file) as f:
        resumes = json.load(f)
except:
    resumes = {"resumes_generated": 0, "leads_processed": []}

run_date = evals.get("run_date", datetime.now().strftime("%Y-%m-%d"))
leads = evals.get("leads", [])

resume_leads = [l for l in leads if l.get("action") == "generate_resume"]
report_leads = [l for l in leads if l.get("action") == "report_only"]
rejected = [l for l in leads if l.get("dealbreaker")]
ignored = [l for l in leads if l.get("action") == "ignore"]

print(f"# Daily Job Search Report — {run_date}\n")
print(f"## Run Summary")
print(f"- **Listings evaluated:** {evals.get('total_evaluated', len(leads))}")
print(f"- **Above resume threshold:** {len(resume_leads)}")
print(f"- **Worth reviewing:** {len(report_leads)}")
print(f"- **Dealbreaker rejections:** {len(rejected)}")
print(f"- **Resumes generated:** {resumes.get('resumes_generated', 0)}")
print(f"- **Duplicates skipped:** {evals.get('duplicates_skipped', 0)}")
print()

if resume_leads:
    print("## New Leads (Resumes Generated)\n")
    for l in sorted(resume_leads, key=lambda x: x.get("final_score", 0), reverse=True):
        score = l.get("final_score", 0)
        print(f"### {l.get('company', '?')} — {l.get('title', '?')} (Score: {score:.2f})")
        print(f"- **Location:** {l.get('location', 'Unknown')}")
        print(f"- **Compensation:** {l.get('compensation', 'Not listed')}")
        print(f"- **Category:** {l.get('category', 'Unknown')}")
        print(f"- **Application:** {l.get('application_url', l.get('url', 'N/A'))}")
        scores = l.get("scores", {})
        reasoning = l.get("reasoning", {})
        print(f"\n| Dimension | Score | Reasoning |")
        print(f"|-----------|-------|-----------|")
        for dim in ["level_match", "role_category", "location_fit", "coding_interview_risk", "narrative_fit", "company_maturity"]:
            s = scores.get(dim, 0)
            r = reasoning.get(dim, "")
            print(f"| {dim} | {s:.1f} | {r} |")
        angle = l.get("narrative_angle", "")
        if angle:
            print(f"\n**Narrative angle:** {angle}")
        print()

if report_leads:
    print("## Worth Reviewing (Below Resume Threshold)\n")
    for l in sorted(report_leads, key=lambda x: x.get("final_score", 0), reverse=True):
        score = l.get("final_score", 0)
        print(f"- **{l.get('company', '?')} — {l.get('title', '?')}** (Score: {score:.2f}) — {l.get('location', '?')} — {l.get('url', '')}")
        reasoning = l.get("reasoning", {})
        level_r = reasoning.get("level_match", "")
        if level_r:
            print(f"  - Level: {level_r}")
    print()

if rejected:
    print("## Dealbreaker Rejections\n")
    for l in rejected:
        db = l.get("dealbreaker", "unknown")
        print(f"- {l.get('company', '?')} — {l.get('title', '?')} — Dealbreaker: {db}")
    print()

print("---")
print(f"*Report generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
PYEOF

  log "Report written to $report_file"
}

# ── Entry Point ──────────────────────────────────────────────────────────────

export TMP_DIR
main "$@"
