# Data Generation

This dataset is synthetic throughout.

It was generated from a defined GLYPH trace structure using Python builder scripts.

## What It Is

- A rigid trace language was defined first.
- Builder scripts then generated traces that follow that structure.
- The scripts expand across task families, tool schemas, prompt variants, and response variants.

So this is **not**:
- scraped conversational data
- raw human chat logs
- a dataset collected from natural human interactions

It is synthetic data generated from a fixed structural specification.

## Files

- `build_gold50.py`
  - builds the small seed set
- `build_gold300.py`
  - expands the dataset into a broader gold set
- `build_gold2500.py`
  - expands further into the final training file used for `GLYPH_SFT_OFFICIAL_V1`

Datasets:
- `gold_glyph_50.jsonl`
- `gold_glyph_300.jsonl`
- `gold_glyph_2500.jsonl`

## How Generation Worked

The builders do not simply duplicate traces.

They generate traces by reusing a rigid underlying format while varying things like:
- system prompt wording
- user task wording
- tool schemas
- trace family shape
- todo structure
- references and ids
- final responses

That means the traces are distinct, but they are still produced mechanically from a controlled structure rather than from open-ended sampling.

## Why This Approach Was Used

The goal was to teach a model a narrow, reliable trace dialect.

For that objective, this kind of synthetic data is useful because it gives:
- high structural consistency
- low format entropy
- strong pressure on the exact protocol

The tradeoff is that semantic diversity is lower than it would be with thousands of fully unconstrained traces.

## Directory Structure

The directory structure was flattened later.

Originally, these files lived under a nested `synthetic_data/glyph_gold50/` path.
They now live directly under `synthetic_data/`.

That does **not** change the dataset content itself.
It only changes where the files live in the repo.
