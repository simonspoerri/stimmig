# Methodology

These rules are Stimmig's promise of neutrality. They apply to every vote in
the same way and only change with a public commit that explains why. The
public site shows a German version
([apps/web/src/content/methodik.md](../apps/web/src/content/methodik.md));
keep both in sync.

## 1. Which claims are included

Sources, in this order:

1. **Voting booklet** (explanations of the Federal Council), including the
   arguments of the initiative or referendum committee.
2. **Parliamentary debate** on the bill (Official Bulletin).
3. **A fixed list of public sources**, decided per vote before analysis
   starts and recorded with the vote (for example the official committees'
   websites).

From these sources, **all** verifiable claims are extracted, not a
selection. A factual claim that cannot be shown with official data is listed
as "not visualized", with the reason. This rules out bias through selection.

## 2. Classification

Each claim gets exactly one class:

| Class | Definition | Treatment |
|---|---|---|
| `fact` | A claim about a past or present, measurable state of affairs | shown with official data as a chart |
| `forecast` | A claim about future developments, costs or effects, including estimates and if-then statements | no chart, no model; listed as "estimate by X" with its source |
| `opinion` | A value judgement, demand or interpretation without a measurable core | not treated |

Mixed sentences are split into their parts. When in doubt, the more
cautious class applies: `forecast` before `fact`, `opinion` before
`forecast`.

## 3. What Stimmig does not do

- No forecasts, projections or model calculations.
- No polls.
- No voting recommendation and no summary of party positions.
- After the vote, at most the official results, without interpretation.

## 4. Data sources

Charts only use data from official sources (for example the Federal
Statistical Office, opendata.swiss, the Federal Tax Administration, SECO,
the Federal Social Insurance Office, cantonal statistical offices). Every
data point carries its publisher, URL, table or dataset id and retrieval
date.

## 5. Visual neutrality

- No party or yes/no colours (no red/green).
- Value axes start at zero where that is meaningful; exceptions are noted.
- The same time window for claims from both sides about the same subject.
- Every chart stands next to the verbatim claim.

## 6. Process and approval

1. The language model extracts claims and classifies them. Every claim must
   appear verbatim in the source text, otherwise it is discarded
   automatically.
2. A reviewer approves, corrects or rejects each claim.
3. A visualizer builds a chart for each approved fact from official data.
   The data is entered from the source, never written by the model.
4. A second person (a reviewer who did not build the chart) approves or
   rejects the chart.
5. Only approved content of a published vote appears on the public site.

How often reviewers had to correct the model is measured in the evals.
