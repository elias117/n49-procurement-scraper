# Procurement Intelligence Platform

## What This Is

A procurement intelligence platform that monitors 63 Canadian government procurement portals nightly, extracts structured listing data using AI-powered scraping (Browser Use + LangExtract), and serves results through a searchable web dashboard. Built for an internal BD team to find and evaluate relevant government contract opportunities faster than manually checking dozens of portals.

## Core Value

The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Nightly scraping of 63 mapped Canadian government procurement portals
- [ ] AI-powered extraction of structured fields (title, description, dates, classification codes, dollar values, contacts, documents)
- [ ] PostgreSQL storage with pgvector for semantic search
- [ ] SQL-based filtering (by date, region, category, value, portal source)
- [ ] Natural language search across listing content
- [ ] Next.js web dashboard for searching and browsing listings
- [ ] Simple authentication (basic login for BD team)
- [ ] Docker Compose orchestration for entire stack
- [ ] AWS EC2 deployment in ca-central-1
- [ ] Terraform-managed infrastructure

### Out of Scope

- Email alerts / saved search notifications — deferred to v2
- OAuth / SSO / role-based access — simple auth sufficient for internal team
- Mobile app — web dashboard only
- Real-time scraping — nightly batch is sufficient
- Multi-tenant SaaS features — internal tool, single team

## Context

- **Portal list:** All 63 portal URLs are mapped and known. Portals vary in structure — some are modern APIs, most are traditional HTML pages requiring browser-based scraping.
- **Data volume:** Expecting ~1,000-5,000 new/updated listings per night across all portals.
- **Scraping approach:** Browser Use (AI-driven browser automation) + Playwright for rendering, LangExtract for structured field extraction from page content.
- **Search patterns:** Team uses both keyword matching ("IT consulting", "janitorial services") and natural language queries ("construction contracts expiring next month in Ontario"). Both must work well.
- **Listing fields:** Title, description, posting date, closing date, source portal, NAICS/UNSPSC codes, category, region/province, estimated contract value, budget range, contact info, linked documents/PDFs, amendment history.
- **Domain:** procurement.eliastools.com
- **Adoption bar:** Listings populate nightly + search works = team starts using it daily.

## Constraints

- **Region:** AWS infrastructure must be in ca-central-1 (Canadian data sovereignty)
- **Stack:** Python scraper pipeline (Browser Use, Playwright, LangExtract), TypeScript/Next.js frontend, PostgreSQL + pgvector, Docker Compose, Terraform
- **Hosting:** Single EC2 instance running Docker Compose
- **Budget:** Single-instance deployment — no Kubernetes, no multi-AZ for v1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Browser Use + LangExtract for scraping | AI-driven extraction handles diverse portal formats without per-site scrapers | — Pending |
| pgvector for semantic search | Enables natural language search without separate search service (Elasticsearch) | — Pending |
| Single EC2 + Docker Compose | Keeps deployment simple and cheap for internal tool | — Pending |
| Nightly batch over real-time | Procurement listings don't change frequently enough to justify real-time | — Pending |
| Simple auth over full auth system | Small internal team, low security risk, fast to implement | — Pending |

---
*Last updated: 2026-02-24 after initialization*
