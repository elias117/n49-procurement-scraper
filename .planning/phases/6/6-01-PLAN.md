---
phase: 6-keyword-infrastructure
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scraper/pipeline/keywords.py
  - scraper/tests/test_keywords.py
autonomous: true
requirements:
  - KWRD-01
  - KWRD-02
  - KWRD-03
  - FILT-05

must_haves:
  truths:
    - "Keywords CSV is loaded, validated, and returns lowercased keyword strings"
    - "Keyword matching is case-insensitive substring on title and description"
    - "French keywords with accents match correctly"
    - "None title or description does not crash the matcher"
    - "Multi-word keywords match as full phrases"
    - "Deduplication removes duplicate source_listing_id entries, keeping first"
    - "Scraper refuses to start if keywords CSV is missing, empty, or malformed"
  artifacts:
    - path: "scraper/pipeline/keywords.py"
      provides: "load_keywords, matches_keywords, filter_listings, deduplicate_listings"
      exports: ["load_keywords", "matches_keywords", "filter_listings", "deduplicate_listings"]
    - path: "scraper/tests/test_keywords.py"
      provides: "Unit tests for all keyword functions"
      min_lines: 120
  key_links:
    - from: "scraper/pipeline/keywords.py"
      to: "keywords_library.csv"
      via: "csv.DictReader with utf-8-sig encoding"
      pattern: "csv\\.DictReader"
    - from: "scraper/pipeline/keywords.py"
      to: "scraper/models.py"
      via: "ListingRecord type used in filter_listings and deduplicate_listings"
      pattern: "listing\\.title|listing\\.description|listing\\.source_listing_id"
---

<objective>
Create the standalone keyword module (`scraper/pipeline/keywords.py`) with all four core functions and comprehensive unit tests.

Purpose: This module provides the reusable keyword infrastructure that Phase 6 plans 02 and 03 (and Phases 7/8) depend on. It is a pure-logic module with no database or orchestrator dependencies.

Output: `scraper/pipeline/keywords.py` with `load_keywords()`, `matches_keywords()`, `filter_listings()`, `deduplicate_listings()`, and `scraper/tests/test_keywords.py` with full coverage.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/6/6-CONTEXT.md
@.planning/phases/6/6-RESEARCH.md
@scraper/pipeline/orchestrator.py
@scraper/models.py
@scraper/tests/conftest.py
@scraper/tests/test_canadabuys.py
@keywords_library.csv
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create scraper/pipeline/keywords.py with all four functions</name>
  <files>scraper/pipeline/keywords.py</files>
  <action>
Create `scraper/pipeline/keywords.py` with these four functions:

1. **`load_keywords(csv_path: Path = KEYWORDS_CSV_PATH) -> list[str]`**
   - Default `KEYWORDS_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"` (resolves to repo root from `scraper/pipeline/keywords.py`)
   - Open with `encoding="utf-8-sig"` to handle BOM
   - Use `csv.DictReader` to parse
   - Validate: `REQUIRED_COLUMNS = {"Category", "Language", "Keyword"}` are present in fieldnames
   - Validate: at least one keyword loaded (non-zero count)
   - Raise `SystemExit` (not ValueError) if file missing, columns wrong, or zero keywords -- this is a fail-safe that terminates the scraper process
   - Return `list[str]` of lowercased keyword strings (strip whitespace before lowering)
   - Log: `"Loaded %d keywords from %s"` with count and filename

2. **`matches_keywords(title: str | None, description: str | None, keywords: list[str]) -> bool`**
   - Build searchable text: concatenate `title.lower()` and `description.lower()` with a space separator
   - Handle None for both title and description (skip if None)
   - If resulting text is empty after strip, return False
   - Return `any(kw in text for kw in keywords)` -- case-insensitive substring match per user decision

3. **`filter_listings(listings: list, keywords: list[str]) -> list`**
   - Filter using `matches_keywords(listing.title, listing.description, keywords)` for each listing
   - Log: `"Keyword filter: %d listings parsed, %d matched keywords"` with total and matched counts
   - Return filtered list

4. **`deduplicate_listings(listings: list) -> list`**
   - Track seen `source_listing_id` values in a `set`
   - Keep first occurrence, skip subsequent duplicates
   - Listings with None `source_listing_id` are always kept (never deduped)
   - Log only if duplicates found: `"Deduplication: removed %d duplicate listings"`
   - Return deduplicated list

Module-level: `import csv, logging; from pathlib import Path; logger = logging.getLogger("scraper.keywords")`

Do NOT import anything from `scraper.db` or `scraper.pipeline.orchestrator` -- this module must have zero coupling to the database or orchestrator.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -c "from scraper.pipeline.keywords import load_keywords, matches_keywords, filter_listings, deduplicate_listings; kw = load_keywords(); print(f'Loaded {len(kw)} keywords'); assert len(kw) >= 100; assert all(k == k.lower() for k in kw); print('OK')"</automated>
    <manual>Verify the module imports cleanly and loads keywords from the real CSV</manual>
  </verify>
  <done>
    - `load_keywords()` returns 120+ lowercased keyword strings from `keywords_library.csv`
    - `matches_keywords()` performs case-insensitive substring match on title/description
    - `filter_listings()` batch-filters ListingRecord objects with logging
    - `deduplicate_listings()` removes duplicate source_listing_id entries
    - No imports from `scraper.db` or `scraper.pipeline.orchestrator`
  </done>
</task>

<task type="auto">
  <name>Task 2: Create scraper/tests/test_keywords.py with comprehensive unit tests</name>
  <files>scraper/tests/test_keywords.py</files>
  <action>
Create `scraper/tests/test_keywords.py` following the patterns in `test_canadabuys.py` (class-based tests, fixtures, direct function calls).

**TestLoadKeywords class:**
- `test_loads_from_real_csv`: Load from actual `keywords_library.csv` (use `Path(__file__).resolve().parent.parent.parent / "keywords_library.csv"`), assert count >= 100
- `test_keywords_are_lowercased`: Load real CSV, assert `all(k == k.lower() for k in keywords)`
- `test_contains_english_and_french`: Load real CSV, spot-check: `"translation services" in keywords` and `"services de traduction" in keywords`
- `test_fails_on_missing_file(tmp_path)`: Call `load_keywords(tmp_path / "nonexistent.csv")`, assert `SystemExit` raised with `pytest.raises(SystemExit)`
- `test_fails_on_missing_columns(tmp_path)`: Write CSV with wrong columns (`Name,Value`), assert `SystemExit`
- `test_fails_on_empty_keywords(tmp_path)`: Write CSV with correct header but no data rows, assert `SystemExit`
- `test_strips_whitespace(tmp_path)`: Write CSV with `"  Translation Services  "`, verify returned keyword is `"translation services"`
- `test_skips_empty_keyword_rows(tmp_path)`: Write CSV with an empty Keyword field row, verify it's skipped

**TestMatchesKeywords class:**
- `test_matches_in_title`: `matches_keywords("Translation Services Needed", None, ["translation services"])` is True
- `test_matches_in_description`: `matches_keywords("RFP", "We need translation services", ["translation services"])` is True
- `test_case_insensitive`: `matches_keywords("TRANSLATION SERVICES", None, ["translation services"])` is True
- `test_partial_match`: `matches_keywords("Looking for a translator", None, ["translation"])` is True
- `test_french_accents`: `matches_keywords("Interpretation simultanee", None, ["interprétation simultanée"])` -- NOTE: this tests that accented keyword does NOT match non-accented text (substring mismatch). Also test: `matches_keywords("interprétation simultanée requise", None, ["interprétation simultanée"])` is True
- `test_multi_word_phrase`: `matches_keywords("We offer bilingual services for government", None, ["bilingual services"])` is True
- `test_no_match`: `matches_keywords("Office furniture procurement", "Desks and chairs", ["translation services"])` is False
- `test_none_title`: `matches_keywords(None, "translation services available", ["translation services"])` is True
- `test_none_description`: `matches_keywords("Translation needed", None, ["translation"])` is True
- `test_both_none`: `matches_keywords(None, None, ["translation"])` is False
- `test_empty_strings`: `matches_keywords("", "", ["translation"])` is False

**TestFilterListings class:**
- Create a fixture `sample_listings` that builds 4 `ListingRecord` objects: 2 with keyword-matching titles, 1 with keyword-matching description, 1 with no match. Use `source_portal=str(uuid.uuid4())` for the required field.
- `test_filters_to_matching_only`: Assert `filter_listings(sample_listings, keywords)` returns exactly 3 items
- `test_preserves_order`: Assert filtered list order matches original order of matching items

**TestDeduplicateListings class:**
- Create fixture with 3 listings: 2 sharing `source_listing_id="DUP-001"`, 1 with `source_listing_id="UNIQUE-001"`
- `test_removes_duplicates`: Assert result has 2 items
- `test_keeps_first_occurrence`: Assert the first item's title matches the first duplicate's title (not the second)
- `test_none_source_listing_id_kept`: Create 2 listings with `source_listing_id=None`, assert both are kept
- `test_no_duplicates_returns_all`: Pass list with all unique IDs, assert same length returned

All ListingRecord objects in tests need at minimum: `title="...", source_portal=str(uuid.uuid4())`. The `source_portal` field is required by the model.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q</automated>
    <manual>All tests pass, covering load, match, filter, and dedup functions</manual>
  </verify>
  <done>
    - All test classes pass: TestLoadKeywords, TestMatchesKeywords, TestFilterListings, TestDeduplicateListings
    - Tests cover: real CSV loading, fail-safe validation, case-insensitive matching, French accents, None handling, multi-word phrases, partial matches, deduplication
    - Full existing test suite still passes: `python -m pytest -x -q`
  </done>
</task>

</tasks>

<verification>
1. `cd /Users/clawbot/dev && python -m pytest scraper/tests/test_keywords.py -x -q` -- all keyword tests pass
2. `cd /Users/clawbot/dev && python -m pytest -x -q` -- full test suite passes (no regressions)
3. `cd /Users/clawbot/dev && python -c "from scraper.pipeline.keywords import load_keywords; kw = load_keywords(); print(f'{len(kw)} keywords loaded')"` -- prints keyword count >= 100
</verification>

<success_criteria>
- `scraper/pipeline/keywords.py` exists with 4 exported functions
- `scraper/tests/test_keywords.py` exists with 20+ tests across 4 test classes
- All tests pass
- `load_keywords()` loads real CSV and returns 120+ lowercased keywords
- `matches_keywords()` handles all edge cases (None, empty, accents, case, partial)
- No database or orchestrator imports in keywords module
</success_criteria>

<output>
After completion, create `.planning/phases/6/6-01-SUMMARY.md`
</output>
