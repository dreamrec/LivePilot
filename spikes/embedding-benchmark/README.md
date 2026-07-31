# Embedding backend benchmark — CLAP vs MERT (2026-07-31)

Settles the question left open by the 2026-07-30 listening-engine work: **is a
license-clean embedding good enough to replace MERT for the taste head?**

Answer: **yes, and CLAP is actually the better fit for this job.**

## Why this harness exists

The original MERT benchmark from 2026-07-30 was scratch work and no longer
exists on disk — only its numbers survived in memory (SNR 21.7x, spread 0.34).
Comparing CLAP against remembered numbers from a metric nobody can inspect
would be meaningless, so this measures **both models identically**, same
captures, same machine, same metric. **These numbers are therefore NOT
comparable to the 2026-07-30 figures** — different metric definition. Only the
within-this-table comparison is meaningful.

## The metric

For each capture, cut N non-overlapping 4-second windows and embed each.

- `within_spread` — mean pairwise cosine distance among windows of the SAME
  capture. The measurement noise floor: how much the embedding moves just from
  looking at a different part of one take.
- `between_dist` — mean cosine distance between windows of DIFFERENT captures
  in the same family (different iterations of one idea).
- **SNR = between / within.** SNR near 1 means the model cannot tell iterations
  apart at all. Higher is better.

Embeddings L2-normalised before cosine. Fully deterministic — fixed windows, no
random crops, so re-runs reproduce exactly.

## Results (music families only)

| model | license | dim | ms/win | mean SNR | **min SNR** |
|---|---|---|---|---|---|
| **CLAP htsat-fused** | Apache-2.0 / CC0 | 512 | 59 | 2.96 | **2.71** |
| CLAP htsat-unfused | Apache-2.0 / CC0 | 512 | 29 | 2.63 | 2.19 |
| MERT-v1-95M | CC-BY-NC-4.0 | 768 | 63 | **3.71** | 1.07 |
| MERT-v1-330M | CC-BY-NC-4.0 | 1024 | 53 | 3.55 | 1.57 |

Per family:

| family | CLAP-fused | CLAP-unfused | MERT-95M | MERT-330M |
|---|---|---|---|---|
| `music_C` (4 iters) | **3.00** | 2.19 | **1.07** | 1.57 |
| `music_B` (2 iters) | 3.17 | 2.95 | 3.70 | 3.89 |
| `music_A` (3 iters) | 2.71 | 2.75 | 6.36 | 5.19 |

## The finding

**MERT wins the mean; CLAP wins the worst case — and the worst case is the one
that matters.**

`music_C` is four iterations of one idea: the subtlest
differences, and the most realistic "kept vs superseded" scenario. MERT-95M
scores **1.07** there — the between-iteration distance is only 7% above its own
within-take wobble, i.e. it essentially cannot separate them. MERT-330M is
better at 1.57 but still weakest of its set. CLAP-fused scores 3.00, its own
best family.

CLAP-fused is also far more consistent (2.71-3.17 across families) where MERT
swings 1.07-6.36. A taste head trained on keep/undone pairs has to work on the
*subtle* pairs — those are the ones a producer agonises over and where a taste
model earns its keep. A model that is brilliant on obvious differences and
blind on subtle ones is the wrong shape for the task, regardless of its mean.

So the licensing tension dissolves: the license-clean option is not a
compromise here.

## Caveats (read before over-trusting this)

- **Small sample**: 3 music families, 9 captures. Directional, not conclusive.
- **Short captures** (8-16 s) forced 4 s windows — shorter than either model's
  typical input (MERT ~5 s, CLAP ~10 s). Both are equally out of their comfort
  zone, so the comparison is fair, but absolute SNRs would likely rise with
  longer material.
- **Latency includes warm-up** and is single-window, unbatched. Treat as rough.
  (MERT-330M timing below 95M is a warm-up artefact, not a real inversion.)
- `synthetic_*` families are hardware smoke tones (sine/noise/pulse), excluded
  from the music aggregate — they say nothing about musical iteration.
- Family names are anonymised (`music_A/B/C`, `synthetic_N`). The source
  captures are session recordings whose filenames carry project themes, which
  do not belong in a public artifact; the numbers are unchanged. Re-running
  locally will show your own filenames.
- MERT requires `trust_remote_code=True`, which executes code from the model
  repo. Run in an isolated venv.

## Re-running

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install torch transformers soundfile numpy scipy nnAudio
python3 bench.py ~/Documents/LivePilot/captures \
  --backends clap:laion/clap-htsat-fused mert:m-a-p/MERT-v1-95M \
  --window 4 --max-windows 4
```

Worked on transformers 5.14.1 / torch 2.13.0 / M3 Max MPS — MERT loaded fine
despite its documented `transformers==4.38` pin.
