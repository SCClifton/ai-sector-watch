# Company Accuracy Audit: 2026-04-28

## Summary

- Companies reviewed: 15
- Verified: 15
- Pending review: 0
- Rejected: 0
- Findings: 80
- Proposed company updates: 15
- Firecrawl credits used: 120
- LLM calls: 15
- Enrichment enabled: True
- Dry run: False

## Method

Rows were read from live Supabase across all company statuses. When enrichment is enabled, the audit uses the existing Firecrawl multi-source path and Claude structured extraction. The JSON file is a proposed update set for review and is not applied by this script.

## Collaboration Opportunities

- Healthcare AI companies may need infrastructure partners for retrieval, observability, or secure deployment.
- AI infrastructure companies can support vertical companies with evaluation, search, data activation, and agent orchestration.

## Artifacts

- CSV findings: `2026-04-28-company-accuracy-batch-03.csv`
- Proposed updates: `2026-04-28-company-accuracy-batch-03.json`
