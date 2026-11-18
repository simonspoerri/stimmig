# Evals

Evals measure how well the claim extraction works, on text labelled by hand.
They are how a change to a prompt or model is judged – not by impression.

```sh
uv run stimmig-evals                  # replay recorded answers (no API key) - as in CI
uv run stimmig-evals --live           # call the model, re-record, 3 runs per item
uv run stimmig-evals --live --split dev --runs 5 --no-gate   # while working on a prompt
```

## Layout

| Path | What |
|---|---|
| `datasets/*.json` | labelled items: a passage of source text and the claims a careful human finds in it, with their class |
| `recordings/*.json` | model answers keyed by a hash of the full request; each says where it came from (`provenance`) |
| `thresholds.toml` | limits per split; the run fails if the worst run misses one |
| `reports/latest.md`, `latest.json` | the report of the last full live run – commit it with the recordings |

Replay and partial runs write `latest.local.*`, which is not committed.

## Metrics

| Metric | Question it answers |
|---|---|
| recall | Of the claims a human found, how many did the model find? Missing claims are invisible later, so this matters most. |
| precision | Of the claims the model reported, how many are real? Extra ones cost reviewer time. |
| class accuracy | Of the matched claims, how many got the right class? |
| forecast/opinion as fact | How often a forecast or opinion was labelled fact. This would lead to a chart for something Stimmig must not chart, so the threshold is zero. |

Quotes count as the same claim when their words overlap by at least 60 %
(Jaccard), because a model may legitimately include or drop a subordinate
clause.

## Building a real dataset

1. Pick 2–3 past votes on different subjects (a fiscal bill, a social
   question, an environmental one). Voting booklets are linked from
   [swissvotes.ch](https://swissvotes.ch).
2. Cut the booklet into passages of about one paragraph; one passage is one
   item. Record the side and the document title.
3. **Label before you look at any model output** – otherwise you inherit the
   model's choices and the eval measures how much the model agrees with
   itself. The labelling guide is [docs/methodology.md](../../../docs/methodology.md).
   Where you hesitate, the methodology is unclear: write down the case and
   sharpen the rule.
4. If possible, have a second person label about 20 % independently. Their
   agreement with you is the ceiling of what the model can reach.
5. Assign about 70 % of items to `dev` and 30 % to `test`. Work on prompts
   only with `dev`; never read the errors of `test` items, or the prompt will
   quietly fit them.
6. Run `--live`, read the errors (the report lists them for `dev`), group
   them into kinds, fix the prompt or the methodology, repeat.

A start of about 40 passages with 150–300 claims shows large differences
reliably. Differences of a few percentage points need more data – and must be
larger than the spread between runs to mean anything.

## Next steps

- Export reviewer corrections from the database as new items, so the dataset
  grows where the model actually makes mistakes.
- Evals for the next pipeline steps once they exist (dataset suggestion,
  neutrality of chart descriptions, possibly with a model as judge).
