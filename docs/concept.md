# Concept

## Purpose

1. **Contribute to informed, data-based decisions in Swiss popular votes.**
   For each announced federal vote, Stimmig shows what official data says
   about the factual claims in the voting booklet and the public debate.
2. **Demonstrate how to build trustworthy AI systems in the open.** The code,
   prompts, evals and their results are public. Anyone can check how a chart
   came about and how good the model really is.

## What Stimmig does

- Extracts every verifiable factual claim from a fixed set of sources per
  vote: the voting booklet (including the committees' arguments), the
  parliamentary debate, and a source list fixed before analysis starts.
- Classifies each claim as **fact**, **forecast** or **opinion**.
- For facts: finds a matching official dataset and shows it as a chart, next
  to the verbatim claim and a link to its source.
- For forecasts: lists them as "estimate by X" with their source. No chart,
  no model of our own.
- Opinions are not treated.

## What Stimmig does not do

- No forecasts, projections or model calculations of its own.
- No polls.
- No voting recommendation, no summary of party positions.
- No verdict of the form "true / false". The data is shown; voters judge.
- After the vote, at most the official results, without interpretation.

## Principles

| Principle | How it shows up in the system |
|---|---|
| **Symmetry** | All claims from all sources are extracted, not a selection. Both sides go through the same steps. |
| **Provenance** | Every claim carries its verbatim quote and source; every data point its publisher, URL, dataset id and retrieval date. |
| **The model never writes charts** | The LLM proposes claims and classifications. Charts are built by people with official data and rendered deterministically. |
| **Four-eyes principle** | Nothing is published without review by a second person (see roles in [architecture.md](architecture.md)). |
| **No AI at view time** | The public site only reads reviewed, published content. |
| **Measured quality** | Changes to prompts or models are judged by evals, not by impression. |

## Users and roles

| Role | Who | Does |
|---|---|---|
| `admin` | project owner | sets up votes and source documents, runs the extraction, manages users, publishes votes |
| `reviewer` | trained volunteer, ideally with a background in political science or data journalism | approves, corrects or rejects extracted claims; approves or rejects charts made by others |
| `visualizer` | person who works with data | builds charts for approved factual claims from official data |

A person can hold several roles. Nobody can approve their own chart.

## Scope of the first version

- Federal votes only, starting with the vote of 28 February 2027.
- Public site in German, built so French and Italian can follow.
- Extraction from text that an admin pastes or uploads per source document.
- Charts with inline data entered or imported by a visualizer. Automatic
  dataset suggestions come later.

## Open questions

- Should charts get a short neutral caption ("The data shows …") or only
  stand next to the claim?
- How to treat claims from media and social media beyond the fixed source
  list?
- How many reviewers are needed per vote, and how they are recruited.
