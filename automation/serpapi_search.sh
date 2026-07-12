#!/bin/bash
#
# SerpAPI Google Jobs search helper
# Usage: ./automation/serpapi_search.sh "query string" [location]
#

set -euo pipefail

QUERY="${1:?Usage: serpapi_search.sh \"query\" [location]}"
LOCATION="${2:-United States}"
API_KEY="${SERPAPI_KEY:-YOUR_API_KEY_HERE}"

ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))")
ENCODED_LOCATION=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$LOCATION'))")

curl -s "https://serpapi.com/search?engine=google_jobs&q=${ENCODED_QUERY}&location=${ENCODED_LOCATION}&gl=us&hl=en&api_key=${API_KEY}"
