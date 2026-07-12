#!/usr/bin/env python3
"""
Pre-screens search results against seen_listings.jsonl and applications.yaml
to remove duplicates before the eval agent runs.

Matching strategy:
1. URL match (stripped of UTM parameters)
2. Company + similar title match (fuzzy)
3. Company match against applications.yaml (already applied or rejected)

Does NOT auto-reject different roles at the same company — only flags them
for the eval agent to note.
"""

import json
import os
import re
import sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

PROJECT_DIR = os.environ.get("PROJECT_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP_DIR = os.path.join(PROJECT_DIR, "automation", "tmp")
LEADS_DIR = os.path.join(PROJECT_DIR, "leads")
SEEN_FILE = os.path.join(LEADS_DIR, "seen_listings.jsonl")
APPS_FILE = os.path.join(LEADS_DIR, "applications.yaml")
SEARCH_RESULTS = os.path.join(TMP_DIR, "search_results.json")


def strip_utm(url):
    """Remove UTM and tracking parameters from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        # Remove common tracking params
        clean_params = {k: v for k, v in params.items()
                       if not k.startswith(('utm_', 'ref', 'source', 'medium', 'campaign'))}
        clean_query = urlencode(clean_params, doseq=True)
        return urlunparse(parsed._replace(query=clean_query)).rstrip('?')
    except:
        return url


def normalize_company(name):
    """Normalize company name for fuzzy matching."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [', inc', ' inc', ', llc', ' llc', ', ltd', ' ltd', ' corp',
                   ' corporation', ' company', ' co.', ' technologies', ' technology',
                   ' services', ' group', ' international', '®', '™', '.']:
        name = name.replace(suffix, '')
    # Remove punctuation and extra spaces
    name = re.sub(r'[^a-z0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_title(title):
    """Normalize job title for fuzzy matching."""
    if not title:
        return ""
    title = title.lower().strip()
    # Remove common prefixes/suffixes
    for noise in ['- remote', '(remote)', 'remote -', '- hybrid', '(hybrid)',
                  '- united states', '- us', '- usa', 'new ', ' any']:
        title = title.replace(noise, '')
    # Normalize common abbreviations
    title = title.replace('sr.', 'senior').replace('sr ', 'senior ')
    title = title.replace('dir.', 'director').replace('dir,', 'director,')
    title = title.replace('mgr', 'manager').replace('vp ', 'vice president ')
    title = re.sub(r'[^a-z0-9\s]', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def titles_match(title1, title2):
    """Check if two titles are similar enough to be the same role."""
    t1 = normalize_title(title1)
    t2 = normalize_title(title2)
    if not t1 or not t2:
        return False
    # Exact match after normalization
    if t1 == t2:
        return True
    # One contains the other
    if t1 in t2 or t2 in t1:
        return True
    # Word overlap — if 70%+ of words match
    words1 = set(t1.split())
    words2 = set(t2.split())
    if not words1 or not words2:
        return False
    overlap = len(words1 & words2)
    min_len = min(len(words1), len(words2))
    if min_len > 0 and overlap / min_len >= 0.7:
        return True
    return False


def load_seen_listings():
    """Load seen listings from JSONL file."""
    seen = []
    if not os.path.exists(SEEN_FILE):
        return seen
    with open(SEEN_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                seen.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return seen


def load_applications():
    """Load company names from applications.yaml (both applied and rejected)."""
    companies = {}  # normalized_name -> list of titles
    if not os.path.exists(APPS_FILE):
        return companies
    try:
        import yaml
        with open(APPS_FILE) as f:
            data = yaml.safe_load(f)
    except ImportError:
        # Fallback: parse YAML manually for company/title fields
        with open(APPS_FILE) as f:
            content = f.read()
        for match in re.finditer(r'company:\s*"([^"]+)"', content):
            name = normalize_company(match.group(1))
            # Find the next title line
            pos = match.end()
            title_match = re.search(r'title:\s*"([^"]*)"', content[pos:pos+200])
            title = title_match.group(1) if title_match else ""
            if name not in companies:
                companies[name] = []
            companies[name].append(title)
        return companies
    except:
        return companies

    for section in ['applications', 'rejected']:
        for entry in (data or {}).get(section, []) or []:
            if isinstance(entry, dict):
                name = normalize_company(entry.get('company', ''))
                title = entry.get('title', '')
                if name:
                    if name not in companies:
                        companies[name] = []
                    companies[name].append(title)
    return companies


def prescreen():
    """Main pre-screening logic."""
    if not os.path.exists(SEARCH_RESULTS):
        print("No search_results.json found")
        return

    with open(SEARCH_RESULTS) as f:
        data = json.load(f)

    listings = data.get('listings', [])
    if not listings:
        print("No listings to prescreen")
        return

    seen = load_seen_listings()
    apps = load_applications()

    # Build lookup structures
    seen_urls = set()
    seen_companies = {}  # normalized_company -> list of normalized titles

    for s in seen:
        url = strip_utm(s.get('url', ''))
        if url:
            seen_urls.add(url)
        company = normalize_company(s.get('company', ''))
        title = s.get('title', '')
        if company:
            if company not in seen_companies:
                seen_companies[company] = []
            seen_companies[company].append(title)

    kept = []
    removed = 0
    flagged = 0

    for listing in listings:
        url = strip_utm(listing.get('url', ''))
        company = normalize_company(listing.get('company', ''))
        title = listing.get('title', '')
        source = listing.get('source', '')

        # Check 1: URL match (after stripping UTM)
        if url and url in seen_urls:
            removed += 1
            continue

        # Check 2: Company + title match against seen listings
        is_dupe = False
        if company and company in seen_companies:
            for seen_title in seen_companies[company]:
                if titles_match(title, seen_title):
                    is_dupe = True
                    break

        if is_dupe:
            removed += 1
            continue

        # Check 3: Company + title match against applications
        if company and company in apps:
            for app_title in apps[company]:
                if titles_match(title, app_title):
                    is_dupe = True
                    break

        if is_dupe:
            removed += 1
            continue

        # Check 4: Same company exists but different title — flag it, don't remove
        if company and (company in seen_companies or company in apps):
            listing['_prescreen_note'] = f"Different role at previously seen company. Prior roles: {seen_companies.get(company, []) + apps.get(company, [])}"
            flagged += 1

        kept.append(listing)

    # Update search results
    data['listings'] = kept
    data['prescreen_removed'] = removed
    data['prescreen_flagged'] = flagged
    data['prescreen_original_count'] = len(listings)

    with open(SEARCH_RESULTS, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Prescreen: {len(listings)} listings → {len(kept)} kept, {removed} duplicates removed, {flagged} flagged (same company, different role)")


if __name__ == '__main__':
    prescreen()
