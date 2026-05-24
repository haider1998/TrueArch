# TrueArch — Telemetry Policy

> **Version:** 1.0
> **Status:** Design-complete. Must be reviewed by legal counsel before any telemetry ships.
> **Scope:** Covers all TrueArch products: MCP server, CLI, web UI, REST API.
> **Decision logs:** DL-021 through DL-025

---

## Principles

1. **Collect the minimum necessary.** If a signal doesn't improve a recommendation, don't collect it.
2. **Opt-in by default for identifiable data.** Aggregate signals are opt-out. Individual project signals are opt-in.
3. **Users can see exactly what we collect.** `truearch config --show-telemetry` prints every field we store.
4. **Users can delete their data.** A single command removes all associated telemetry records.
5. **We never sell data.** Period. This is in the ToS and the investor agreements.

---

## What We Collect (and Why)

### Tier 1 — Aggregate Signals (opt-out, anonymized)

Collected from all users unless explicitly disabled. Contains no identifiable information.

| Signal | What | Why | Retention |
|---|---|---|---|
| Framework query event | `{framework_id, timestamp_week}` | Understand which frameworks are being evaluated | 12 months |
| Recommendation accepted | `{genome_short, recommendation_rank, accepted: bool}` | Improve recommendation ranking | 12 months |
| Score disagreement event | `{framework_id, dimension, direction: "too_high"/"too_low"}` | Improve scoring accuracy | 24 months |
| Error event | `{tool_name, error_type, timestamp_day}` | Improve reliability | 6 months |

**Genome stored in telemetry:** Short form only (7 dimensions, e.g. `MA-STAT-HOR-HIPAA-PY-MCP-REDIS`). Never the full genome.

**What is NOT in Tier 1:**
- Project names, company names, user names
- Repository URLs or identifiers
- Code content of any kind
- IP addresses (hashed only, then discarded after session)
- Email addresses

---

### Tier 2 — Outcome Telemetry (explicit opt-in only)

This is the intelligence-compounding layer — the Decision Lineage outcome records. Never collected automatically.

| Signal | What | Why | Retention |
|---|---|---|---|
| Architecture outcome | Structured outcome record: `{genome, frameworks_used, outcome_rating, production_issues, regret_score}` | Power Future Risk Prediction and confidence scoring | Indefinite (this is the core data moat) |
| ADR submission | Full ADR content (anonymized per policy below) | Build the lineage database | Indefinite |

**Opt-in mechanism:**
```
# In MCP server config
truearch config --enable-outcome-telemetry

# Or per-recommendation in the MCP response
"submit_outcome_url": "https://api.truearch.ai/lineage/{id}/outcome"
```

Users who opt in see a confirmation screen listing every field that will be shared.

---

### Tier 3 — Never Collected

These signals are explicitly excluded, regardless of opt-in status:

- Source code, configuration files, environment variables
- Database schemas or query patterns
- Business logic or proprietary workflows
- Employee names, roles, or organizational charts
- Financial information of any kind
- Passwords, API keys, secrets (enforced at SDK level — these are scrubbed before any data leaves the process)

---

## Anonymization Policy

### Short-Form Anonymization (Tier 1)

Applied before any Tier 1 data is transmitted:

```python
# Pseudocode — exact implementation in src/telemetry/anonymize.py
def anonymize_tier1_event(event: dict) -> dict:
    return {
        # Coarsen timestamps to week granularity
        "week": event["timestamp"].strftime("%Y-W%W"),

        # Keep framework ID (this is public data — "LangGraph" is not sensitive)
        "framework_id": event["framework_id"],

        # Genome: short form only, never full
        "genome_short": event.get("genome_short"),

        # Booleans / enums only — no free-text
        "accepted": event.get("accepted"),
        "direction": event.get("direction"),

        # Session ID: one-way hash, rotated every 24 hours
        # Cannot be reversed to identify a user or machine
        "session_hash": hmac_sha256(session_id, daily_salt),
    }
```

**Session hash rotation:** The daily salt changes every 24 hours. Session hashes from different days cannot be linked even with access to the salt history.

**No persistent user IDs in Tier 1.** Every Tier 1 event is effectively anonymous within 24 hours.

---

### Full Anonymization (Tier 2 — Outcome Records)

When a user submits an outcome record, the following transformations are applied:

| Field | Transformation |
|---|---|
| Company name | Removed; replaced with industry + size bucket (e.g. "FinTech, 50-500 employees") |
| Project name | Removed |
| Repository URL | Removed |
| Team names / engineer names | Removed |
| Specific version numbers (patch) | Coarsened to minor version (e.g. `1.2.3` → `1.2.x`) |
| Compliance requirements | Kept (D4 genome dimension — not personally identifiable) |
| Outcome narrative (free text) | User-controlled; must explicitly choose to include |
| Genome | Kept in full (this is the core analytical unit) |

**User sees exactly what will be shared** before submission. No hidden fields.

---

## Consent Flow

### MCP Server (first run)

```
TrueArch collects anonymous usage signals to improve recommendations.
No code, project names, or identifying information is collected.

  [1] Enable anonymous signals (recommended)
  [2] Disable all telemetry
  [3] See exactly what would be collected

Your choice (1):
```

### Web UI (first login)

Standard GDPR-compliant cookie consent banner + a "What we collect" link that shows the exact Tier 1 field list.

### Outcome Telemetry (explicit opt-in)

```
You're about to submit an outcome record for:
Genome: MA-STAT-HOR-HIPAA-PY-MCP-REDIS

The following anonymized data will be shared:
  ✓ Genome: MA-STAT-HOR-HIPAA-PY-MCP-REDIS
  ✓ Frameworks used: LangGraph 1.2.0, Redis 8.6.3
  ✓ Outcome rating: 8/10
  ✓ Production issues: [your description, if provided]
  ✗ Company name: REMOVED
  ✗ Project name: REMOVED
  ✗ Repository URL: REMOVED

[Submit] [Cancel] [Edit]
```

---

## GDPR Compliance

| Requirement | Implementation |
|---|---|
| Lawful basis | Legitimate interest (Tier 1 aggregate signals) / Explicit consent (Tier 2 outcomes) |
| Right to access | `truearch telemetry --export` exports all associated records |
| Right to erasure | `truearch telemetry --delete` removes all associated Tier 1 session hashes; Tier 2 records are anonymized so no personal data to delete |
| Data residency | Tier 1: processed in EU-West by default; Tier 2: user-selectable region |
| DPA | Data Processing Agreement available for enterprise customers |
| DPO | Appoint a DPO before EU launch (required if processing at scale) |

---

## Data Architecture

```
User Device (Phase 1: Local SQLite `telemetry.db`)
    │
    ├── Tier 1 events  →  anonymize()  →  queue  →  HTTPS  →  TrueArch ingest API
    │                                                              │
    │                                                         Aggregate DB
    │                                                    (no user-identifiable data)
    │
    └── Tier 2 (opt-in) →  user reviews  →  anonymize()  →  HTTPS  →  TrueArch lineage DB
                                                                          (outcome records)
```

**Ingest API:** TLS 1.3 minimum. Events batched and sent every 15 minutes (not real-time to prevent traffic analysis).

**Storage:** Tier 1 in a separate database from Tier 2. Different encryption keys. Different access controls. Engineers working on scoring never have access to raw Tier 1 data — only aggregated views.

---

## Opt-Out Mechanisms

| Product | How to opt out |
|---|---|
| MCP Server | `truearch config --disable-telemetry` |
| CLI | `TRUEARCH_NO_TELEMETRY=1` environment variable |
| Web UI | Account Settings → Privacy → Disable Usage Analytics |
| API | Set `X-TrueArch-No-Telemetry: 1` header on all requests |

When opted out:
- No Tier 1 events are transmitted
- Tier 2 remains available (it's always opt-in; opting out of Tier 1 doesn't disable Tier 2)
- The product functions identically — no degraded experience

---

## Decision Logs

### DL-021 — Opt-out for Tier 1, explicit opt-in for Tier 2
- **Decision:** Aggregate signals are opt-out; outcome records are always explicit opt-in
- **Rationale:** Tier 1 is anonymized and generates value for the whole community (better recommendations). Tier 2 contains architectural data that could be competitively sensitive — must be user's active choice
- **Date:** 2026-05-16

### DL-022 — 24-hour session hash rotation
- **Decision:** Session hashes rotate every 24 hours using a daily salt
- **Rationale:** Prevents linking behavior across days. Even a full database breach cannot reconstruct user behavior across sessions.
- **Date:** 2026-05-16

### DL-023 — Timestamp coarsening to week granularity
- **Decision:** All Tier 1 timestamps stored as week (e.g., "2026-W20"), not day or hour
- **Rationale:** Day-level timestamps could enable timing attacks to identify individuals in small teams. Week granularity preserves trend data while preventing this.
- **Date:** 2026-05-16

### DL-024 — Genome stored in telemetry (Tier 1)
- **Decision:** Short-form Genome (7 dimensions) is included in aggregate telemetry
- **Rationale:** The Genome describes the architectural context, not the user. "MA-STAT-HOR-HIPAA-PY-MCP-REDIS" describes a system type, not a person. This is the core signal needed to improve recommendations by architecture type.
- **Alternatives rejected:** Excluding Genome entirely — would make aggregate telemetry useless for recommendation improvement
- **Date:** 2026-05-16

### DL-025 — No persistent user IDs in Tier 1
- **Decision:** Tier 1 uses only daily-rotating session hashes, never persistent user IDs
- **Rationale:** Persistent user IDs create a liability (linkable across time). Rotating hashes provide enough signal to detect unusual behavior (e.g., scoring bugs) without enabling user tracking.
- **Date:** 2026-05-16

---

*Last updated: 2026-05-16 v1.0 | Must be reviewed by legal before any telemetry ships to production.*
