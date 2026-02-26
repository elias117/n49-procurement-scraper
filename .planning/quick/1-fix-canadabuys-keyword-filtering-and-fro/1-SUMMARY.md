# Quick Task 1: Summary

## Fix keyword matching false positives + exact search title snippets

**Commit:** c32090d

### Changes

**1. Word-boundary keyword matching** (`scraper/pipeline/keywords.py`)
- Replaced `all(word in text for word in words)` (substring matching) with `all(word in text_words for word in kw_words)` using `re.findall(r"\w+", ...)` to extract whole words
- Prevents false positives like "de" (from French keywords) matching inside "department" or "describe"
- Both text and keywords are split using the same `\w+` pattern, handling apostrophes (e.g. "d'interprétation") correctly

**2. Exact search title snippets** (`api/search/hybrid.py`)
- Changed snippet in `_build_exact_match_sql` from `COALESCE(f.description, f.title)` to `CASE WHEN m.match_rank = 0 THEN f.title ELSE COALESCE(f.description, f.title) END`
- When title matched (match_rank=0), snippet now highlights the title; otherwise highlights description

### Tests
- 46 keyword tests passing (3 new: whole-word rejection, false positive prevention, French apostrophe)
- 6 hybrid search tests passing
