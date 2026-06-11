#!/usr/bin/env python3
"""Deterministically restore each evaluated lead's apply URL from search_results.json.

The evaluation agent is an LLM, and when it rewrites listings into
evaluated_leads.json it sometimes corrupts `application_url` — notably mangling
the trailing numeric job ID in LinkedIn URLs and reusing a single ID across many
distinct listings (the descriptive slug stays right, so the wrong link looks
legitimate). The canonical URLs captured at search time are trustworthy, so we
overwrite the eval output's URLs from search_results.json, matched by normalized
company + title. Any lead that can't be matched is flagged
`application_url_unverified: true` so the report can warn instead of linking to
the wrong job.

Reads/writes JSON only (no LLM) — run after evaluation, before resume + report.
"""
import json
import os
import re

TMP_DIR = os.environ.get("TMP_DIR", "automation/tmp")
SEARCH = os.path.join(TMP_DIR, "search_results.json")
EVAL = os.path.join(TMP_DIR, "evaluated_leads.json")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def key(company, title):
    return norm(company) + "|" + norm(title)


def canonical_url(listing):
    return listing.get("application_url") or listing.get("url") or ""


def slug_key(url):
    """A stable key from a job URL that ignores the (corruptible) trailing numeric
    ID and query string. The eval agent preserves the descriptive slug and only
    mangles the trailing ID, so two URLs for the same posting share this key."""
    if not url:
        return ""
    u = url.split("?", 1)[0].rstrip("/").lower()
    u = re.sub(r"-\d{6,}$", "", u)  # drop trailing LinkedIn-style numeric id
    return u


def main():
    if not (os.path.exists(SEARCH) and os.path.exists(EVAL)):
        print("URL reconcile: search_results.json or evaluated_leads.json missing — skipped")
        return

    with open(SEARCH) as f:
        search = json.load(f)
    with open(EVAL) as f:
        ev = json.load(f)

    # Canonical URL lookups (first listing wins on collision):
    #   1. by normalized company+title, 2. by URL slug (id-stripped).
    by_name = {}
    by_slug = {}
    for l in search.get("listings", []):
        by_name.setdefault(key(l.get("company"), l.get("title")), l)
        sk = slug_key(canonical_url(l))
        if sk:
            by_slug.setdefault(sk, l)

    restored = already_ok = flagged = 0
    for lead in ev.get("leads", []):
        src = by_name.get(key(lead.get("company"), lead.get("title")))
        if not src:
            src = by_slug.get(slug_key(lead.get("application_url") or lead.get("url")))
        if src:
            canon = canonical_url(src)
            current = lead.get("application_url") or lead.get("url") or ""
            if canon and canon != current:
                lead["application_url"] = canon
                if lead.get("url"):
                    lead["url"] = src.get("url") or canon
                restored += 1
            else:
                already_ok += 1
            lead.pop("application_url_unverified", None)
        else:
            lead["application_url_unverified"] = True
            flagged += 1

    with open(EVAL, "w") as f:
        json.dump(ev, f, indent=2)

    print(f"URL reconcile: {restored} restored, {already_ok} already correct, "
          f"{flagged} unmatched (flagged application_url_unverified)")


if __name__ == "__main__":
    main()
