# Phase 1 Context: Infrastructure

**Phase Goal:** The EC2 instance is live, all services run in Docker Compose, PostgreSQL has the complete schema with all indexes and constraints, and TLS is terminated — ready to receive data.

**Requirements:** INFR-01, INFR-02, INFR-03, INFR-04

---

## 1. Listing Schema Field Definitions

### Classification Codes
- A listing can have multiple codes from the same system (e.g., two NAICS codes)
- Store as JSONB array, not a single value
- Support NAICS, UNSPSC, and GSIN code systems

### Region/Province
- Province-level is sufficient for filtering
- Capture the raw location string as-is from the portal (e.g., "Ottawa, ON") in a separate field
- Parse up to province for the filter dimension without losing original detail

### Contract Values
- Two fields: `value_min` and `value_max`
- Exact amounts: same value in both fields
- Ranges: different values
- Unknown/TBD: both null

### Document Links
- JSONB array of document objects on the listing
- Each object: name, type (RFP, amendment, addendum), date if available, URL
- BD team needs to identify document type without clicking every link

### Amendment History
- Store latest version only — no diff tracking in v1
- `amended_date` field plus `revision` counter (integer, incremented on changes)
- Amendment PDFs captured naturally via the document links array
- Upsert updates listing in place on re-scrape

### Contact Information
- JSONB field on the listing to handle variable structure (one or multiple contacts)
- No need to search/filter by contact in v1

### Listing Status
- Explicit status field: open, closed, cancelled, awarded
- Keep all listings indefinitely — historical data has value
- Default search filter shows open/future only, but closed listings remain queryable

### Language
- Single field — capture whatever language the portal provides
- No bilingual column split (title_en/title_fr)
- Semantic search via embeddings handles cross-language similarity

---

## 2. AWS and DNS Readiness

### Starting State
- AWS account exists with IAM user configured via `aws configure`
- No existing VPC, subnets, or EC2 in ca-central-1 — Terraform creates everything from scratch
- May need to create a dedicated IAM user for Terraform

### Domain and TLS
- `eliastools.com` is already in Route 53
- Terraform adds `procurement.eliastools.com` A record
- TLS via Let's Encrypt on EC2 (not ACM)

### Terraform State
- **Local state only** — no S3 backend or DynamoDB locking
- Overrides roadmap success criteria which mentioned S3 remote state
- Single-developer workflow doesn't need remote state for v1

### Database
- PostgreSQL in Docker Compose on EC2 — NOT RDS
- Matches roadmap: simpler, cheaper, single-instance deployment

### EC2 Configuration
- Terraform creates key pair for SSH access
- Port 22 (SSH): open
- Port 443 (HTTPS): open
- Port 80 (HTTP): open (redirects to HTTPS)
- Remote database access needed — secure method (SSH tunnel or IP-restricted 5432) to be determined by planner
- Instance type: researcher to recommend based on workload (PostgreSQL + pgvector, Python scraper, Next.js, Nginx running concurrently; ~1K-5K listings/night; small user team). Some overhead is acceptable.

---

## 3. Portal Seed Data

### Portal Table Schema
- `name` — official portal name (e.g., "CanadaBuys", "MERX", "BC Bid")
- `url` — single entry URL per portal
- `level` — federal / provincial / municipal
- `province` — nullable (null for federal portals)
- `language` — en / fr / both
- `requires_login` — boolean
- `enabled` — boolean (active/inactive flag)

### Seeding Strategy
- Seed all 63 portals in Phase 1 via migration
- Source: `municipalities.xlsx` contains names and URLs
- Enrichment needed: level, province, language, requires_login must be added (can be inferred from portal)
- Portals with `requires_login = true` get `enabled = false` — defer gated portals, ship open ones first

### Portal URL Model
- One URL per portal record
- Sub-portals (e.g., MERX General, MERX Calgary) are already separate entries with distinct URLs
- Browser Use handles navigation from the entry URL

---

## Deferred Ideas

*(Captured during discussion — not in Phase 1 scope)*

- Full amendment diff tracking (v2+ if needed)
- Search/filter by contact information
- Bilingual column split (title_en/title_fr)
- Login-required portal authentication

---

## Roadmap Overrides

| Roadmap Statement | Override | Rationale |
|---|---|---|
| "remote state stored in S3" (Success Criteria #3) | Local Terraform state | Single-developer workflow; S3 backend adds complexity with no v1 benefit |

---

*Created: 2026-02-24 via phase discussion*
