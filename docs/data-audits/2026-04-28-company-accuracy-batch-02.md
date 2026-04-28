# Company Accuracy Audit: 2026-04-28

## Summary

- Companies reviewed: 15
- Verified: 14
- Pending review: 1
- Rejected: 0
- Findings: 75
- Proposed company updates: 14
- Firecrawl credits used: 112
- LLM calls: 14
- Enrichment enabled: True
- Dry run: False

## Method

Rows were read from live Supabase across all company statuses. When enrichment is enabled, the audit uses the existing Firecrawl multi-source path and Claude structured extraction. The JSON file is a proposed update set for review and is not applied by this script.

## Collaboration Opportunities

- Healthcare AI companies may need infrastructure partners for retrieval, observability, or secure deployment.
- AI infrastructure companies can support vertical companies with evaluation, search, data activation, and agent orchestration.

## Artifacts

- CSV findings: `2026-04-28-company-accuracy-batch-02.csv`
- Proposed updates: `2026-04-28-company-accuracy-batch-02.json`
