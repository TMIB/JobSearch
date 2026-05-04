#!/usr/bin/env python3
"""
Helper to reliably extract leads from evaluated_leads.json regardless of
what field name the eval agent uses (leads, listings, results, etc.)
"""

import json
import sys
import os

def get_leads(filepath):
    """Extract the leads array from evaluated_leads.json, regardless of field name."""
    with open(filepath) as f:
        d = json.load(f)

    # Try known field names in order of preference
    for key in ['leads', 'listings', 'results', 'evaluated_leads', 'jobs', 'entries']:
        val = d.get(key)
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
            return val

    # Fallback: find any list of dicts that looks like leads
    for key, val in d.items():
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
            if any(k in val[0] for k in ['company', 'title', 'action', 'final_score', 'scores']):
                return val

    return []


if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.environ.get("TMP_DIR", "automation/tmp"), "evaluated_leads.json")

    leads = get_leads(filepath)
    action = sys.argv[2] if len(sys.argv) > 2 else None

    if action == 'resume_count':
        print(len([l for l in leads if l.get('action') == 'generate_resume']))
    elif action == 'report_count':
        print(len([l for l in leads if l.get('action') in ('generate_resume', 'report_only')]))
    elif action == 'companies':
        names = [l.get('company', '?') for l in leads if l.get('action') == 'generate_resume']
        print(', '.join(names[:5]))
    elif action == 'first_score':
        scores = [l.get('final_score', 0) for l in leads]
        print(f'{scores[0]:.2f}' if scores else '?')
    elif action == 'dump':
        print(json.dumps(leads, indent=2))
    else:
        print(json.dumps(leads))
