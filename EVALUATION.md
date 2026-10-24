# Evaluation

## Observed checks on October 24, 2026

Backend: 55 tests passed in 11.39 seconds, with one Starlette/httpx deprecation warning. Frontend projection: six tests passed. Vite production build passed in 26.31 seconds. These 61 automated checks are not 61 live model trials. Provider tests use mocked responses; no fresh paid live-model evaluation was performed for this submission package.

## Representative expected and actual outcomes

1. Missing research service: expected an explicit missing-supplier indication; frontend test passed.
2. Edited allocations: expected recalculation and over-budget detection; frontend test passed.
3. Unsafe supplier URL: expected removal; frontend test passed.
4. Recognized research schedule: expected extracted timeline; frontend test passed.
5. No usable schedule: expected a labeled fallback template; frontend test passed.
6. Invalid saved numeric edits: expected finite, usable totals; frontend test passed.

## Manual example from development

The user supplied an Accra birthday run with 40 guests, indoor requirements and a USD 5,000 budget. It returned a cited shortlist and suggested schedule. This demonstrates an observed location-specific research response, not verified venue availability, supplier suitability or quote accuracy. Earlier Boston-only catalog runs returned zero Accra options; separating live search from rehearsal addressed that mode mismatch.

## Failures that shaped the design

Earlier runs showed inconsistent budget narration, generic validation/provider failures, raw report formatting, misleading decision counters and a blank Overview after live research. Current code preserves structured saved requirements, renders research, distinguishes research completion and projects a provisional dashboard. Provider outages and malformed responses can still block a run. Heuristic extraction and quote verification remain open issues.

## Next evaluation

Run and record fresh live trials across several locations and event types. Human reviewers should score citation support, supplier relevance, coverage of required services, indoor/capacity evidence, response time and cost. Record failures as well as successes. Compare against manual search using the same briefs. No such comparative performance claims are made here.