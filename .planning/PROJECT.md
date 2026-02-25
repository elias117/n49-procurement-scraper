# Procurement Intelligence Platform

## What This Is

A procurement intelligence platform that monitors 63 Canadian government procurement portals nightly, extracts structured listing data using AI-powered scraping (Browser Use + instructor), and serves results through a searchable web dashboard. Built for an internal BD team to find and evaluate relevant government contract opportunities faster than manually checking dozens of portals.

## Core Value

The BD team can search all 63 government procurement portals from one place, using both precise filters and natural language, and find relevant opportunities they would otherwise miss.

## Current State

**Shipped:** v1.0 (2026-02-24)
**Status:** Feature-complete, ready for production use

### What's Live
- Nightly scraping of 63 Canadian procurement portals (2 AM ET)
- AI-powered extraction with structured field validation
- Hybrid search (keyword + semantic + RRF) with 6 filter dimensions
- Next.js dashboard with auth, listing detail, scraper health monitoring
- Docker Compose on EC2 (ca-central-1) with Terraform, Nginx TLS
- Automated retention cleanup and Docker image pruning

### Known Tech Debt
- `reference_number` extracted but not persisted to database
- robots.txt compliance audit not yet performed

## Next Milestone Goals

Candidates for v2 (to be refined during `/gsd:new-milestone`):
- Email alerts / saved search notifications
- Saved search profiles
- Bookmark/flag listings
- Amendment history tracking
- Cross-portal deduplication
- CloudWatch monitoring and alerting
- reference_number persistence

## Context

- **Portal list:** All 63 portal URLs are mapped and known.
- **Data volume:** ~1,000-5,000 new/updated listings per night.
- **Domain:** procurement.eliastools.com
- **Adoption bar:** Listings populate nightly + search works = team starts using it daily.

## Constraints

- **Region:** AWS ca-central-1 (Canadian data sovereignty)
- **Stack:** Python scraper, TypeScript/Next.js frontend, PostgreSQL + pgvector, Docker Compose, Terraform
- **Hosting:** Single EC2 instance
- **Budget:** Single-instance, no Kubernetes, no multi-AZ

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Browser Use + instructor for scraping | AI-driven extraction handles diverse portal formats | Validated — 63 portals covered |
| pgvector for semantic search | Single data store for structured + vector data | Validated — hybrid search works well |
| Single EC2 + Docker Compose | Simple and cheap for internal tool | Validated — running in production |
| Nightly batch over real-time | Procurement listings don't change frequently enough | Validated — sufficient for team needs |
| Simple auth over full auth system | Small internal team, low security risk | Validated — Auth.js credentials working |

---
*Last updated: 2026-02-25 after v1.0 milestone completion*
