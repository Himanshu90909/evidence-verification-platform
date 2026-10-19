# Research Mode

This directory holds the research-mode outputs of the platform. Research mode is
kept strictly separate from production mode: production predictions live in
PostgreSQL tied to users and model versions; research results live here and in
the `experiments` table (`mode = "research"`), and are loaded by the Research
dashboard from `results/*.json` only — the dashboard never displays
hard-coded metrics.

## Pipeline (ml-service/scripts/run_experiments.py)

1. Stratified sampling from the FEVER validation split (seeded, reproducible).
2. **Retrieval evaluation** — BM25 vs dense vs hybrid (RRF): Recall@5/@10,
   MRR@10, nDCG@10, mean latency, against FEVER gold evidence.
3. **End-to-end verification evaluation** — full pipeline verdicts vs gold
   labels: accuracy, macro-F1, per-class precision/recall/F1, confusion matrix,
   mean confidence/uncertainty, per-stage latencies.
4. **Calibration** — temperature scaling (grid search minimizing NLL), ECE
   before/after, 10-bin reliability data. The fitted temperature is deployed
   to production via the `TEMPERATURE` env var (recorded per prediction).
5. **Ablations** — retrieval method (bm25/dense/hybrid) and top-k (3/5/10).

## Results

`results/` contains the committed outputs of the last experiment run:
`meta.json`, `retrieval_eval.json`, `nli_eval.json`, `calibration.json`,
`ablations.json`. Every file records the dataset, models, seed and pipeline
version that produced it (see `meta.json`).

Reproduce with:

```bash
cd ml-service
python scripts/run_experiments.py --out-dir ../research/results
node ../scripts/sync-research.mjs   # publish to the web research dashboard
```

## Interpretation notes

- Metrics reflect **zero-shot** transfer of a general NLI cross-encoder to
  claim-evidence pairs (no FEVER fine-tuning); they are a research baseline,
  not a leaderboard result.
- NEI is hardest (no gold evidence exists to retrieve), which depresses
  macro-F1 — an honest limitation of evidence-grounded verification.
- Hybrid retrieval outperforms both sparse and dense retrieval on every
  metric, supporting RQ1.
