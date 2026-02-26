# Quick Task 1: Fix keyword matching false positives + exact search snippet

## Task 1: Fix matches_keywords word-boundary matching

**Files:** `scraper/pipeline/keywords.py`, `scraper/tests/test_keywords.py`
**Action:** Replace substring matching (`word in text`) with word-boundary matching using `re.findall(r'\w+', text)` to extract words as a set, then check membership. Update tests.
**Verify:** `cd scraper && python -m pytest tests/test_keywords.py -v`
**Done:** "services de traduction" no longer matches text containing "describe" or "department"

## Task 2: Fix exact search snippet to include title matches

**Files:** `api/search/hybrid.py`
**Action:** In `_build_exact_match_sql`, change snippet to use CASE on match_rank: when 0 (title match), run ts_headline on title; otherwise on description.
**Verify:** `cd api && python -m pytest tests/test_hybrid.py -v`
**Done:** Exact search snippets show title highlights when title is what matched
