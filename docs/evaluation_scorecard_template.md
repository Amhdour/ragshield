# Evaluation Scorecard Template

## Run Metadata
- Date:
- Commit SHA:
- Dataset version:
- Model(s):
- Evaluator:

## Gate Thresholds
- Faithfulness threshold: `>= 0.70`
- Answer relevancy threshold: `>= 0.70`

## Aggregate Metrics
| Metric | Value | Threshold | Pass/Fail |
|---|---:|---:|---|
| faithfulness_mean |  | 0.70 |  |
| answer_relevancy_mean |  | 0.70 |  |

## Worst Cases (Top 3)
| Question | Mean Score | Failure Reason | Notes |
|---|---:|---|---|
|  |  |  |  |
|  |  |  |  |
|  |  |  |  |

## Security Regression Signals
- Prompt injection behavior stable? (Y/N + notes)
- Exfiltration refusal stable? (Y/N + notes)
- Citation integrity stable? (Y/N + notes)

## Decision
- Gate result: Pass / Fail
- Follow-up actions:
- Owner:
