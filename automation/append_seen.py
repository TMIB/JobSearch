#!/usr/bin/env python3
"""Deterministically append each evaluated listing to leads/seen_listings.jsonl.

This used to be the evaluation agent's job ("Also update leads/seen_listings.jsonl"
in its prompt). On 2026-09-06 the agent tried to trim lines it had just appended
with a GNU-only `head -n -24`, which fails on BSD/macOS and emits nothing; the
following `mv` then overwrote the file with that empty output, destroying all
9,821 entries. With dedup history gone the next two runs pushed ~200 unfiltered
listings into evaluation and blew the eval budget, producing no report.

Handing an LLM a shell and asking it to edit an append-only ledger is the bug.
This script does the same job with no model in the loop: it only ever opens the
file in append mode, so no failure mode here can shorten it.

Reads/writes JSON only (no LLM) — run after evaluation, alongside reconcile_urls.py.
"""
import json
import os
import re
import sys

PROJECT_DIR = os.environ.get(
    "PROJECT_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
TMP_DIR = os.environ.get("TMP_DIR", os.path.join(PROJECT_DIR, "automation", "tmp"))
EVAL = os.path.join(TMP_DIR, "evaluated_leads.json")
SEEN = os.path.join(PROJECT_DIR, "leads", "seen_listings.jsonl")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def url_key(url):
    """Match the normalization synthesize_search.py uses when it loads this file."""
    return (url or "").strip().lower().rstrip("/")


def main():
    if not os.path.exists(EVAL):
        print("Seen append: evaluated_leads.json missing — skipped")
        return 0

    try:
        with open(EVAL) as f:
            ev = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Seen append: could not read evaluated_leads.json ({e}) — skipped")
        return 0

    leads = ev.get("leads") or []
    if not leads:
        print("Seen append: no leads in evaluated_leads.json — nothing to append")
        return 0

    # Load existing keys so a re-run (or a --skip-search recovery) doesn't
    # duplicate rows. A missing file is fine: we create it by appending.
    seen_urls = set()
    seen_ct = set()
    existing = 0
    if os.path.exists(SEEN):
        with open(SEEN, errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                existing += 1
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("url"):
                    seen_urls.add(url_key(e["url"]))
                co, ti = norm(e.get("company")), norm(e.get("title"))
                if co and ti:
                    seen_ct.add((co, ti))

    run_date = ev.get("run_date") or ""
    appended = skipped = 0
    rows = []
    for lead in leads:
        url = lead.get("application_url") or lead.get("url") or ""
        co, ti = norm(lead.get("company")), norm(lead.get("title"))
        uk = url_key(url)
        ctk = (co, ti)
        if (uk and uk in seen_urls) or (co and ti and ctk in seen_ct):
            skipped += 1
            continue
        if uk:
            seen_urls.add(uk)
        if co and ti:
            seen_ct.add(ctk)
        rows.append({
            "url": url,
            "company": lead.get("company") or "",
            "title": lead.get("title") or "",
            "date_seen": run_date,
            "score": lead.get("final_score"),
            "action": lead.get("action") or "",
            "folder": lead.get("folder") or "",
        })
        appended += 1

    if rows:
        # Append-only, then fsync: a crash mid-write can lose the tail but can
        # never truncate what was already on disk.
        with open(SEEN, "a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
            f.flush()
            os.fsync(f.fileno())

    print(f"Seen append: {appended} added, {skipped} already present "
          f"({existing} -> {existing + appended} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
