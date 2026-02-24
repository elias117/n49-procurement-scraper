---
phase: 2-scraper-pipeline
plan: 02
type: execute
wave: 2
depends_on: ["2-01"]
files_modified:
  - scraper/pipeline/validation.py
  - scraper/pipeline/canadabuys.py
  - scraper/pipeline/embeddings.py
  - scraper/tests/test_validation.py
  - scraper/tests/test_canadabuys.py
  - scraper/tests/test_embeddings.py
autonomous: true
requirements:
  - SCRP-04
  - SCRP-05

must_haves:
  truths:
    - "Post-extraction validation nullifies implausible values rather than rejecting entire listings"
    - "Closing dates before posting dates are set to null"
    - "Contract values outside 0-10B range are set to null"
    - "Minimum viable listing (title + source_url + source_portal) always passes validation"
    - "CanadaBuys CSV is downloaded via httpx, parsed with csv.DictReader, and mapped to ListingRecord objects"
    - "CanadaBuys uses utf-8-sig encoding to handle BOM"
    - "Embeddings are generated from title + description text using text-embedding-3-small"
    - "Embedding batch processing respects the 250K token limit and 2048 items per request"
    - "Completeness score is computed correctly (0.0-1.0) based on populated fields"
  artifacts:
    - path: "scraper/pipeline/validation.py"
      provides: "Post-extraction validation and completeness scoring"
      exports: ["validate_listing", "compute_completeness_score"]
    - path: "scraper/pipeline/canadabuys.py"
      provides: "CanadaBuys CSV download and parsing"
      exports: ["canadabuys_ingest"]
    - path: "scraper/pipeline/embeddings.py"
      provides: "OpenAI embedding generation with batching"
      exports: ["generate_embeddings"]
    - path: "scraper/tests/test_validation.py"
      provides: "Validation rule tests"
    - path: "scraper/tests/test_canadabuys.py"
      provides: "CanadaBuys CSV parsing tests"
    - path: "scraper/tests/test_embeddings.py"
      provides: "Embedding generation tests (mocked)"
  key_links:
    - from: "scraper/pipeline/validation.py"
      to: "scraper/models.py"
      via: "validate_listing accepts and returns ListingRecord"
      pattern: "ListingRecord"
    - from: "scraper/pipeline/canadabuys.py"
      to: "scraper/models.py"
      via: "Maps CSV rows to ListingRecord"
      pattern: "ListingRecord"
    - from: "scraper/pipeline/embeddings.py"
      to: "scraper/config.py"
      via: "Uses OPENAI_EMBEDDING_MODEL and batch limits from config"
      pattern: "config\\.OPENAI_EMBEDDING_MODEL"
---

<objective>
Build the validation layer, CanadaBuys CSV ingestion (the zero-cost path), and embedding generation module.

Purpose: Validation (SCRP-04) ensures no hallucinated data enters the database -- blank is always better than wrong. CanadaBuys is the highest-value portal (federal procurement, structured CSV, zero LLM cost). Embeddings (SCRP-05) are the final step before DB insert for all paths.

Output: Three independent pipeline modules with full test coverage. CanadaBuys can be run end-to-end once the orchestrator exists (Plan 04).
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/2/2-CONTEXT.md
@.planning/phases/2/2-RESEARCH.md
@.planning/phases/2/2-01-SUMMARY.md
@scraper/models.py
@scraper/config.py
@scraper/db.py
@scraper/tests/conftest.py
@db/migrations/001_initial_schema.sql
</context>

<tasks>

<task type="auto">
  <name>Task 1: Post-extraction validation and completeness scoring</name>
  <files>
    scraper/pipeline/validation.py
    scraper/tests/test_validation.py
  </files>
  <action>
    **Create `scraper/pipeline/validation.py`:**

    `validate_listing(listing: ListingRecord) -> ListingRecord`:
    - Accept a ListingRecord, apply validation rules, return a cleaned ListingRecord.
    - NEVER reject an entire listing. Instead, null out individual invalid fields. Per user decision: "blank is always better than a wrong guess."
    - Validation rules:
      1. **Minimum viable check**: If title is missing/empty, raise ValueError (this IS a rejection -- no title means no listing).
      2. **Closing date sanity**: If closing_date is present and posting_date is present and closing_date < posting_date, set closing_date = None. Log warning.
      3. **Date format**: If posting_date or closing_date cannot be parsed as ISO datetime, set to None. Log warning.
      4. **Value range**: If value_min or value_max is not None and (< 0 or > 10,000,000,000), set to None. Log warning.
      5. **Value ordering**: If value_max is not None and value_min is not None and value_max < value_min, set both to None. Log warning.
      6. **Status normalization**: If status not in ('open', 'closed', 'cancelled', 'awarded'), default to 'open'.
      7. **Classification code validation**: For each code in classification_codes, verify it has 'system' and 'code' keys. Remove entries missing these. Do NOT validate code values against known lists (the user said never guess -- if the source says it, keep it).
      8. **URL format**: If source_url is present but doesn't start with http:// or https://, set to None.
    - Return the cleaned ListingRecord.

    `compute_completeness_score(listing: ListingRecord) -> float`:
    - Score 0.0-1.0 based on how many of these 9 fields are non-null: title, description, posting_date, closing_date, classification_codes (non-empty list), value_min, contact_info (non-null), province, source_url.
    - Return round(filled / 9, 2).

    `validate_and_score(listing: ListingRecord) -> ListingRecord`:
    - Convenience function: validate, compute completeness, set listing.completeness_score, return.

    **Create `scraper/tests/test_validation.py`:**
    - `test_valid_listing_passes_unchanged()` — Full listing passes with no modifications.
    - `test_missing_title_raises()` — ValueError when title is empty/None.
    - `test_closing_before_posting_nullified()` — closing_date set to None when before posting_date.
    - `test_negative_value_nullified()` — value_min = -100 becomes None.
    - `test_huge_value_nullified()` — value_max = 20_000_000_000 becomes None.
    - `test_value_max_less_than_min_both_nullified()` — Both set to None.
    - `test_invalid_status_defaults_to_open()` — status="draft" becomes "open".
    - `test_invalid_url_nullified()` — source_url="not-a-url" becomes None.
    - `test_classification_codes_missing_keys_removed()` — Entry without 'system' key removed.
    - `test_completeness_score_full()` — All 9 fields present = 1.0.
    - `test_completeness_score_minimal()` — Only title + source_url = ~0.22.
    - `test_completeness_score_empty_codes_not_counted()` — Empty classification_codes list scores as missing.
    - `test_validate_and_score_sets_score()` — Verify completeness_score is set on returned listing.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_validation.py -x -q 2>&1</automated>
  </verify>
  <done>
    - validate_listing nullifies bad fields without rejecting listings (except missing title)
    - compute_completeness_score returns 0.0-1.0 based on 9 scored fields
    - 13 validation tests pass covering all rules
  </done>
</task>

<task type="auto">
  <name>Task 2: CanadaBuys CSV ingestion handler</name>
  <files>
    scraper/pipeline/canadabuys.py
    scraper/tests/test_canadabuys.py
  </files>
  <action>
    **Create `scraper/pipeline/canadabuys.py`:**

    Per user decision: "CanadaBuys: use API/open data not browser scraping" and "Pull everything from CanadaBuys (no API-level filtering)."

    `CANADABUYS_CSV_URL = "https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv"`

    Include the `CANADABUYS_FIELD_MAP` dict from the research (maps our field names to CSV column names). Also include `PROCUREMENT_CATEGORIES` dict.

    `async def canadabuys_ingest(portal: PortalRecord) -> list[ListingRecord]`:
    1. Download CSV using `httpx.AsyncClient` with timeout=120s.
    2. Decode with `utf-8-sig` encoding to handle BOM (per pitfall #5 from research).
    3. Parse with `csv.DictReader`.
    4. For each row, map fields:
       - `title`: Use English title, fall back to French if English is empty.
       - `description`: English description, fall back to French.
       - `source_listing_id`: referenceNumber field (REQUIRED -- skip row if missing).
       - `posting_date`: Parse from publicationDate field, ISO format.
       - `closing_date`: Parse from tenderClosingDate field, ISO format.
       - `status`: Map tenderStatus to our enum (Open->open, Closed->closed, etc.). Default to 'open'.
       - `classification_codes`: Build JSONB array from GSIN and UNSPSC fields. Format: `[{"system": "GSIN", "code": "N1234", "description": "..."}]`. Only include if the code field is non-empty.
       - `contact_info`: Build JSONB from contact name, email, phone fields. Format: `{"name": "...", "email": "...", "phone": "..."}`. Only include non-empty values.
       - `source_url`: English notice URL, fall back to French.
       - `province`: From regionsOfOpportunity field.
       - `raw_location`: From regionsOfDelivery field.
       - `language`: Detect from which title field was used (en/fr/both).
       - `documents`: Empty list (CSV doesn't include document links).
       - `source_portal`: portal.id
    5. Create ListingRecord for each row.
    6. Return list of ListingRecord. Log count.
    7. Handle httpx.HTTPError gracefully -- re-raise with descriptive message.

    Helper functions:
    - `_parse_date(date_str: str) -> Optional[str]`: Parse various date formats to ISO. Return None on failure.
    - `_map_status(status_str: str) -> str`: Map CanadaBuys status values to our enum.
    - `_build_classification_codes(row: dict) -> list[dict]`: Extract GSIN and UNSPSC codes.
    - `_build_contact_info(row: dict) -> Optional[dict]`: Build contact JSONB.

    **Create `scraper/tests/test_canadabuys.py`:**

    Create a fixture `sample_csv_content` that returns a string of valid CanadaBuys CSV data (header + 3 rows) using the exact column names from the field map. Include realistic Canadian procurement data.

    - `test_parse_csv_returns_listings()` — Parse sample CSV, verify 3 ListingRecord objects returned.
    - `test_title_english_preferred()` — Row with both English and French titles uses English.
    - `test_title_falls_back_to_french()` — Row with empty English title uses French.
    - `test_missing_reference_number_skipped()` — Row without referenceNumber is skipped.
    - `test_classification_codes_built_from_gsin()` — Row with GSIN code produces correct JSONB.
    - `test_contact_info_built()` — Row with contact fields produces correct JSONB.
    - `test_date_parsing()` — Various date formats correctly parsed to ISO.
    - `test_status_mapping()` — CanadaBuys statuses map to our enum.
    - `test_empty_optional_fields_are_none()` — Missing CSV fields result in None, not empty strings.
    - `test_utf8_bom_handled()` — CSV with BOM prefix parses correctly.

    To test without HTTP calls: extract the CSV parsing logic into a separate `_parse_csv(csv_text: str, portal: PortalRecord) -> list[ListingRecord]` function that `canadabuys_ingest` calls after downloading. Test `_parse_csv` directly with the fixture data.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_canadabuys.py -x -q 2>&1</automated>
  </verify>
  <done>
    - canadabuys_ingest downloads CSV via httpx and returns list[ListingRecord]
    - CSV parsing handles utf-8-sig encoding (BOM)
    - Field mapping covers all CanadaBuys columns (title, dates, codes, contact, URLs, geography)
    - English preferred with French fallback for bilingual fields
    - Rows missing referenceNumber are skipped
    - 10 tests pass covering parsing, field mapping, and edge cases
  </done>
</task>

<task type="auto">
  <name>Task 3: Embedding generation with batch processing</name>
  <files>
    scraper/pipeline/embeddings.py
    scraper/tests/test_embeddings.py
  </files>
  <action>
    **Create `scraper/pipeline/embeddings.py`:**

    Per user decision: text-embedding-3-small is the locked embedding model. Per research: batch to stay under 250K token limit and 2048 items per request.

    `generate_embeddings(listings: list[ListingRecord]) -> list[ListingRecord]`:
    1. For each listing, build embedding text: `f"{listing.title}\n\n{listing.description or ''}"`. Strip to remove trailing whitespace if description is None.
    2. Use tiktoken with `cl100k_base` encoding to count tokens.
    3. Truncate any text exceeding 8000 tokens (leave margin below 8192 limit per config).
    4. Batch texts into groups respecting two limits:
       - Max 250,000 tokens summed across all inputs in one request (EMBEDDING_BATCH_TOKEN_LIMIT from config)
       - Max 2048 inputs per request (EMBEDDING_BATCH_SIZE_LIMIT from config)
    5. For each batch, call `openai.OpenAI().embeddings.create(model=config.OPENAI_EMBEDDING_MODEL, input=batch_texts)`.
    6. Use tenacity retry decorator: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=30), retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)))`.
    7. Assign embedding vectors back to the corresponding ListingRecord objects. Set `listing.embedding = response.data[i].embedding` and `listing.embedding_model = config.OPENAI_EMBEDDING_MODEL`.
    8. Return the updated listings.
    9. Log: number of listings embedded, number of API calls made, total tokens processed.

    **Important:** Embeddings are generated AFTER validation. Per research anti-pattern: "Do not waste embedding tokens on invalid listings."

    `_prepare_embedding_text(listing: ListingRecord) -> str`:
    - Combine title + description. Handle None description.
    - Return prepared text.

    `_count_tokens(text: str) -> int`:
    - Use tiktoken cl100k_base encoding.
    - Return token count.

    **Create `scraper/tests/test_embeddings.py`:**

    Mock the OpenAI client to return predictable embedding vectors (1536 floats, all 0.01).

    - `test_generate_embeddings_calls_openai()` — Verify openai.embeddings.create called with model="text-embedding-3-small".
    - `test_embedding_text_combines_title_and_description()` — Verify _prepare_embedding_text returns "Title\n\nDescription".
    - `test_embedding_text_handles_none_description()` — Verify just title returned when description is None.
    - `test_embeddings_set_on_listings()` — After generate_embeddings, each listing has a 1536-dim vector and embedding_model set.
    - `test_batch_splitting_respects_token_limit()` — Create 10 listings with 30K tokens each, verify multiple API calls made (300K > 250K limit).
    - `test_long_text_truncated()` — Create listing with >8000 tokens, verify truncation before API call.
    - `test_empty_list_returns_empty()` — generate_embeddings([]) returns [].
    - `test_embedding_model_set_correctly()` — Each listing.embedding_model == "text-embedding-3-small".

    Mock strategy: Use `unittest.mock.patch("scraper.pipeline.embeddings.OpenAI")` to mock the client. The mock should return a response object with `.data` containing objects with `.embedding` attribute.
  </action>
  <verify>
    <automated>cd /Users/clawbot/dev && OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/test_embeddings.py -x -q 2>&1</automated>
  </verify>
  <done>
    - generate_embeddings processes listings in batches respecting token and size limits
    - Each listing gets a 1536-dim embedding vector and embedding_model="text-embedding-3-small"
    - Text is truncated at 8000 tokens before API call
    - Tenacity retry handles rate limits and connection errors
    - 8 tests pass with mocked OpenAI client
  </done>
</task>

</tasks>

<verification>
Run full test suite including Plan 01 tests:
```bash
cd /Users/clawbot/dev
OPENAI_API_KEY=test-key DATABASE_URL=postgresql://fake:fake@localhost:5432/fake python -m pytest scraper/tests/ -x -q
```
All tests pass (Plan 01 + Plan 02 tests). No import errors across modules.
</verification>

<success_criteria>
1. `from scraper.pipeline.validation import validate_listing, compute_completeness_score` succeeds
2. `from scraper.pipeline.canadabuys import canadabuys_ingest` succeeds
3. `from scraper.pipeline.embeddings import generate_embeddings` succeeds
4. `pytest scraper/tests/test_validation.py` passes 13+ tests
5. `pytest scraper/tests/test_canadabuys.py` passes 10+ tests
6. `pytest scraper/tests/test_embeddings.py` passes 8+ tests
7. Validation never rejects a listing (except missing title) -- only nullifies bad fields
8. CanadaBuys parsing uses utf-8-sig and csv.DictReader
9. Embedding batching respects 250K token limit
</success_criteria>

<output>
After completion, create `.planning/phases/2/2-02-SUMMARY.md`
</output>
