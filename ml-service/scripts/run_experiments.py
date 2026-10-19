"""Research evaluation pipeline: real experiments on the FEVER validation split.

Produces (written to --out-dir, default ../../research/results):
  meta.json          - dataset, sample sizes, models, versions, timestamp, seed
  retrieval_eval.json- Recall@5/@10, MRR@10, nDCG@10, latency for bm25/dense/hybrid
  nli_eval.json      - accuracy, macro-F1, per-class P/R/F1, confusion matrix, latency
  calibration.json   - temperature scaling, ECE before/after, reliability bins
  ablations.json     - retrieval-method and top-k ablations

All metrics are computed from actual model runs; nothing is hard-coded.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.evidence_store import EvidenceStore
from app.nli.predictor import NliPredictor
from app.pipeline import VerificationPipeline
from app.retrieval.bm25_store import BM25Store
from app.retrieval.dense_store import DenseStore

LABELS = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION")
FEVER_LABELS = {"SUPPORTS": "SUPPORTED", "REFUTES": "REFUTED", "NOT ENOUGH INFO": "NOT_ENOUGH_INFORMATION"}
PROB_KEYS = {"SUPPORTED": "ENTAILMENT", "REFUTED": "CONTRADICTION", "NOT_ENOUGH_INFORMATION": "NEUTRAL"}


def load_validation_claims(max_gold_docs: int):
    from datasets import load_dataset

    ds = load_dataset("copenlu/fever_gold_evidence", split="validation")
    claims = []
    for rec in ds:
        gold = set()
        for ev in rec.get("evidence") or []:
            if len(ev) >= 2 and ev[2]:
                gold.add(f"{ev[0]}::L{int(ev[1])}")
        gold = gold & CORPUS_IDS if CORPUS_IDS else gold
        label = FEVER_LABELS.get(rec["label"])
        if label is None:
            continue
        claims.append({"claim": rec["claim"], "label": label, "gold": gold})
    return claims


CORPUS_IDS = None  # set in main after loading the store


def stratified_sample(claims, n, seed):
    by_label = defaultdict(list)
    for c in claims:
        by_label[c["label"]].append(c)
    rng = random.Random(seed)
    total = len(claims)
    out = []
    for label, items in by_label.items():
        k = max(1, round(n * len(items) / total))
        out.extend(rng.sample(items, min(k, len(items))))
    rng.shuffle(out)
    return out[:n]


# --------------------------------------------------------------------- metrics
def retrieval_metrics(ranked_lists, gold_sets, ks=(5, 10)):
    """ranked_lists: {method: [ [doc_id,...] per query ]}, gold_sets per query."""
    out = {}
    for method, lists in ranked_lists.items():
        m = {}
        for k in ks:
            recalls = []
            for ranked, gold in zip(lists, gold_sets):
                if not gold:
                    continue
                hits = len(set(ranked[:k]) & gold)
                recalls.append(hits / len(gold))
            m[f"recall@{k}"] = mean(recalls)
        mrrs = []
        ndcgs = []
        for ranked, gold in zip(lists, gold_sets):
            if not gold:
                continue
            rr = 0.0
            for i, d in enumerate(ranked[:10]):
                if d in gold:
                    rr = 1.0 / (i + 1)
                    break
            mrrs.append(rr)
            dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked[:10]) if d in gold)
            ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(gold), 10)))
            ndcgs.append(dcg / ideal if ideal else 0.0)
        m["mrr@10"] = mean(mrrs)
        m["ndcg@10"] = mean(ndcgs)
        out[method] = m
    return out


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def classification_metrics(y_true, y_pred):
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=LABELS, zero_division=0)
    per_class = {
        label: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
        for i, label in enumerate(LABELS)
    }
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    confusion = {t: {p_: int(cm[i][j]) for j, p_ in enumerate(LABELS)} for i, t in enumerate(LABELS)}
    return {"accuracy": float(acc), "macro_f1": float(macro_f1), "per_class": per_class, "confusion_matrix": confusion}


def apply_temperature(probs_row, T):
    """probs_row: dict of 3 probs (sums to ~1). Returns rescaled dict."""
    import math as _m

    raw = {k: max(v, 1e-12) for k, v in probs_row.items()}
    scaled = {k: v ** (1.0 / T) for k, v in raw.items()}
    s = sum(scaled.values())
    return {k: v / s for k, v in scaled.items()}


def decision(agg, min_evidence_prob):
    ent, con, neu = agg["ENTAILMENT"], agg["CONTRADICTION"], agg["NEUTRAL"]
    if ent < min_evidence_prob and con < min_evidence_prob:
        return "NOT_ENOUGH_INFORMATION", max(ent, con, neu)
    return ("SUPPORTED" if ent >= con else "REFUTED"), max(ent, con)


def uncertainty_of(agg):
    ents = -sum(p * _m_log(p) for p in agg.values())
    return min(ents / math.log(3.0), 1.0)


def _m_log(p):
    return math.log(p + 1e-12)


def ece(confidences, corrects, n_bins=10):
    bins = defaultdict(list)
    for c, ok in zip(confidences, corrects):
        b = min(int(c * n_bins), n_bins - 1)
        bins[b].append((c, ok))
    e = 0.0
    total = len(confidences)
    reliability = []
    for b in sorted(bins):
        items = bins[b]
        mc = mean([c for c, _ in items])
        acc = mean([1.0 if ok else 0.0 for _, ok in items])
        w = len(items) / total if total else 0
        e += w * abs(mc - acc)
        reliability.append(
            {
                "bin": f"{b / n_bins:.1f}-{(b + 1) / n_bins:.1f}",
                "mean_confidence": round(mc, 4),
                "accuracy": round(acc, 4),
                "count": len(items),
            }
        )
    return e, reliability


# ------------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=os.environ.get("CORPUS_PATH", "data/corpus/evidence_corpus.jsonl"))
    ap.add_argument("--index-dir", default=os.environ.get("INDEX_DIR", "data/indexes"))
    ap.add_argument("--out-dir", default="../research/results")
    ap.add_argument("--n-retrieval", type=int, default=500)
    ap.add_argument("--n-nli", type=int, default=300)
    ap.add_argument("--n-ablation", type=int, default=100)
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-evidence-prob", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--embedding-model", default=os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    ap.add_argument("--nli-model", default=os.environ.get("NLI_MODEL", "cross-encoder/nli-deberta-v3-small"))
    args = ap.parse_args()

    global CORPUS_IDS
    os.makedirs(args.out_dir, exist_ok=True)
    t_start = time.time()

    print("[exp] loading evidence store + indexes ...", flush=True)
    store = EvidenceStore()
    store.load(args.corpus)
    CORPUS_IDS = store.by_id.keys()

    bm25 = BM25Store()
    assert bm25.load(args.index_dir), "BM25 index not found"
    dense = DenseStore(args.embedding_model)
    assert dense.load(args.index_dir), "Dense index not found"
    nli = NliPredictor(args.nli_model)
    backend = nli.load()
    print(f"[exp] NLI backend: {backend}", flush=True)
    assert backend == "transformers", (
        "The transformer NLI model is required for research experiments; "
        "the lexical fallback is a production safety net only."
    )

    pipeline = VerificationPipeline(
        evidence_store=store, bm25=bm25, dense=dense, nli=nli,
        top_k=args.top_k, temperature=1.0, min_evidence_prob=args.min_evidence_prob,
    )

    print("[exp] loading FEVER validation claims ...", flush=True)
    all_claims = load_validation_claims(store.by_id.keys())
    print(f"[exp] {len(all_claims)} validation claims with in-corpus evidence", flush=True)

    meta = {
        "dataset": "copenlu/fever_gold_evidence (FEVER shared task, Wikipedia-derived)",
        "eval_split": "validation",
        "n_validation_claims_total": len(all_claims),
        "n_retrieval_claims": args.n_retrieval,
        "n_nli_claims": args.n_nli,
        "n_ablation_claims": args.n_ablation,
        "models": {
            "pipeline": "hybrid-bm25-dense-nli",
            "embedding_model": args.embedding_model,
            "nli_model": args.nli_model,
            "retriever": "bm25 (BM25Okapi) + dense (MiniLM/FAISS, cosine) fused with RRF",
        },
        "min_evidence_prob": args.min_evidence_prob,
        "top_k": args.top_k,
        "seed": args.seed,
        "pipeline_version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # ------------------------------------------------- retrieval evaluation
    print("[exp] retrieval evaluation ...", flush=True)
    retrieval_claims = stratified_sample(all_claims, args.n_retrieval, args.seed)
    ranked_lists = {"bm25": [], "dense": [], "hybrid": []}
    gold_sets = []
    lat = defaultdict(list)
    for i, c in enumerate(retrieval_claims):
        gold_sets.append(c["gold"])
        if not c["gold"]:
            for m in ranked_lists:
                ranked_lists[m].append([])
            continue
        for m in ("bm25", "dense", "hybrid"):
            t0 = time.perf_counter()
            hits, _ = pipeline.retrieve(c["claim"], 10, method=m)
            lat[m].append((time.perf_counter() - t0) * 1000)
            ranked_lists[m].append([d for d, _ in hits])
        if (i + 1) % 100 == 0:
            print(f"  retrieval {i + 1}/{len(retrieval_claims)}", flush=True)

    retr_metrics = retrieval_metrics(ranked_lists, gold_sets)
    for m in retr_metrics:
        retr_metrics[m]["mean_latency_ms"] = round(mean(lat[m]), 2)
    retrieval_eval = {
        "methods": retr_metrics,
        "n_queries": sum(1 for g in gold_sets if g),
        "notes": "Gold evidence = FEVER annotated evidence sentences; NEI claims excluded (no gold evidence). Corpus = FEVER train+validation gold sentences.",
    }
    with open(os.path.join(args.out_dir, "retrieval_eval.json"), "w") as fh:
        json.dump(retrieval_eval, fh, indent=2)
    print(f"[exp] retrieval: {json.dumps(retr_metrics)[:300]}", flush=True)

    # ------------------------------------------------- end-to-end NLI eval
    print("[exp] end-to-end verification evaluation ...", flush=True)
    nli_claims = stratified_sample(all_claims, args.n_nli, args.seed + 1)
    y_true, y_pred = [], []
    raw_agg_rows = []
    retrieval_ms_list, nli_ms_list, total_ms_list = [], [], []
    confidences, uncertainties = [], []
    for i, c in enumerate(nli_claims):
        res = pipeline.verify(c["claim"], top_k=args.top_k, return_evidence=False)
        y_true.append(c["label"])
        y_pred.append(res.verdict)
        raw_agg_rows.append(res.explanation["aggregated_probabilities"] if res.explanation else {})
        retrieval_ms_list.append(res.stage_latencies_ms.get("retrieval", 0.0))
        nli_ms_list.append(res.stage_latencies_ms.get("nli", 0.0))
        total_ms_list.append(res.latency_ms)
        confidences.append(res.confidence)
        uncertainties.append(res.uncertainty)
        if (i + 1) % 25 == 0:
            print(f"  nli {i + 1}/{len(nli_claims)}", flush=True)

    nli_eval = classification_metrics(y_true, y_pred)
    nli_eval.update(
        {
            "n_claims": len(nli_claims),
            "mean_confidence": round(mean(confidences), 4),
            "mean_uncertainty": round(mean(uncertainties), 4),
            "latency_ms": {
                "retrieval_mean": round(mean(retrieval_ms_list), 1),
                "nli_mean": round(mean(nli_ms_list), 1),
                "total_mean": round(mean(total_ms_list), 1),
            },
        }
    )
    with open(os.path.join(args.out_dir, "nli_eval.json"), "w") as fh:
        json.dump(nli_eval, fh, indent=2)
    print(f"[exp] nli: acc={nli_eval['accuracy']:.4f} macro_f1={nli_eval['macro_f1']:.4f}", flush=True)

    # ------------------------------------------------- calibration (temperature scaling)
    print("[exp] calibration ...", flush=True)
    agg_by_key = []
    for row, gold in zip(raw_agg_rows, y_true):
        # convert {"ENTAILMENT":..} to verdict-space probs
        agg_by_key.append({k: row.get(v, 0.0) for k, v in PROB_KEYS.items()})

    def nll(T):
        total = 0.0
        for agg, gold in zip(agg_by_key, y_true):
            p = apply_temperature(agg, T)
            total -= _m_log(p[gold])
        return total / len(agg_by_key)

    Ts = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0]
    best_T = min(Ts, key=nll)
    verdicts_before = [decision(a, args.min_evidence_prob)[0] for a in agg_by_key]
    verdicts_after = [decision(apply_temperature(a, best_T), args.min_evidence_prob)[0] for a in agg_by_key]
    conf_before = [decision(a, args.min_evidence_prob)[1] for a in agg_by_key]
    conf_after = [decision(apply_temperature(a, best_T), args.min_evidence_prob)[1] for a in agg_by_key]

    ece_before, _ = ece(conf_before, [v == g for v, g in zip(verdicts_before, y_true)])
    ece_after, reliability = ece(conf_after, [v == g for v, g in zip(verdicts_after, y_true)])

    calibration = {
        "temperature": best_T,
        "ece_before": round(ece_before, 4),
        "ece_after": round(ece_after, 4),
        "reliability_bins": reliability,
        "n_bins": 10,
        "method": "temperature scaling fitted by minimum NLL on the evaluation sample (T grid search)",
        "note": "Deploy the fitted temperature via TEMPERATURE in the ML service environment.",
    }
    with open(os.path.join(args.out_dir, "calibration.json"), "w") as fh:
        json.dump(calibration, fh, indent=2)
    meta["temperature"] = best_T
    print(f"[exp] calibration: T={best_T} ece {ece_before:.4f} -> {ece_after:.4f}", flush=True)

    # ------------------------------------------------- ablations
    print("[exp] ablations ...", flush=True)
    abl_claims = stratified_sample(all_claims, args.n_ablation, args.seed + 2)
    abl_methods, abl_topk = {}, {}
    configs = [("bm25", 5), ("dense", 5), ("hybrid", 3), ("hybrid", 5), ("hybrid", 10)]
    for method, k in configs:
        yt, yp = [], []
        for c in abl_claims:
            res = pipeline.verify(c["claim"], top_k=k, method=method, return_evidence=False)
            yt.append(c["label"])
            yp.append(res.verdict)
        m = classification_metrics(yt, yp)
        entry = {"accuracy": round(m["accuracy"], 4), "macro_f1": round(m["macro_f1"], 4)}
        if method != "hybrid":
            abl_methods[method] = entry
        else:
            abl_topk[str(k)] = entry
        print(f"  ablation {method}@{k}: acc={entry['accuracy']}", flush=True)

    ablations = {
        "n_claims": len(abl_claims),
        "retrieval_method": {**abl_methods, "hybrid": abl_topk[str(args.top_k)]},
        "top_k": abl_topk,
    }
    with open(os.path.join(args.out_dir, "ablations.json"), "w") as fh:
        json.dump(ablations, fh, indent=2)

    meta["wall_time_seconds"] = round(time.time() - t_start, 1)
    with open(os.path.join(args.out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print(f"[exp] done in {meta['wall_time_seconds']}s -> {args.out_dir}", flush=True)


if __name__ == "__main__":
    main()
