#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检索质量基准评测（改进点 4）：量化 MRR@10 / Recall@10，替代"体感变好了"式判断。

用法：
  python benchmark_eval.py                          # 全量评测，报告落 F:/rag/reports/
  python benchmark_eval.py --n 10                   # 只跑前 10 条（快速冒烟）
  python benchmark_eval.py --label baseline         # 给本次运行打标签（进文件名与报告）
  python benchmark_eval.py --diff old.json new.json # 对比两次运行（验证行为保持重构）

设计要点：
- 标注粒度 = source 文件级：对重切分/重索引免疫（chunk_id 会随 CHUNK_SIZE 漂移，不用）
- 复用 retriever.search() 真实全链路：混合召回 → 规则重排 → reranker → MMR
- 不污染运营信号：monkeypatch 掉 hit_stats 计数与缺口日志（评测查询是跑批，
  不是真实使用；混进 hit_counts.json 会干扰淘汰决策，混进 gap_log.jsonl 会误导补文档）
- 首轮 BM25 构建/懒加载开销用预热查询吸收，不计入延迟统计
"""

import argparse
import datetime
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:  # Windows 控制台中文输出防御
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
QUERIES_PATH = SCRIPT_DIR / "benchmark_queries.json"
DEFAULT_OUT_DIR = SCRIPT_DIR.parent.parent / "reports"


def load_queries(limit=None):
    data = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    qs = data["queries"]
    if limit:
        qs = qs[:limit]
    # 标注健全性检查：golden 文件名必须在向量库真实存在（防手滑标错）
    from models import get_vectorstore
    from config import DEFAULT_SEARCH_KB_IDS
    known = set()
    for kb in DEFAULT_SEARCH_KB_IDS:
        try:
            vs = get_vectorstore(kb)
            known.update({m.get("source") for m in vs.get()["metadatas"] if m})
        except Exception:
            pass
    bad = []
    for q in qs:
        for g in q["golden"]:
            if g not in known:
                bad.append((q["id"], g))
    if bad:
        print(f"⚠️ golden 标注引用了不存在的文件（先修标注再跑）: {bad}")
        sys.exit(2)
    return qs


def run_benchmark(queries, n_results, label):
    import retriever

    # ===== 关键：评测不污染运营信号 =====
    retriever.record_hits = lambda sources: None                    # hit_counts.json
    retriever.KnowledgeRetriever._log_gap = lambda self, *a, **k: None  # gap_log.jsonl

    reranker_active = retriever.get_reranker() is not None
    retriever_sha = hashlib.sha256((SCRIPT_DIR / "retriever.py").read_bytes()).hexdigest()[:8]

    print(f"reranker: {'✅ 生效（分数=相关性概率）' if reranker_active else '❌ 降级（分数=距离）'} | retriever.py sha256[:8] = {retriever_sha}")
    print(f"预热中（BM25 构建 + 首次模型调用，不计入统计）...")
    retriever.get_retriever().search("预热查询", n_results=1)

    results = []
    for i, item in enumerate(queries, 1):
        golden = set(item["golden"])
        t0 = time.perf_counter()
        _, top = retriever.get_retriever().search(item["query"], n_results=n_results)
        latency_ms = (time.perf_counter() - t0) * 1000

        top10 = [{"source": doc.metadata.get("source", ""),
                  "kb": kb,
                  "score": round(float(sc), 6),
                  "h2": doc.metadata.get("h2", "")}
                 for sc, doc, kb in top]
        top_sources = []
        for h in top10:
            if h["source"] not in top_sources:
                top_sources.append(h["source"])
        rank = next((idx + 1 for idx, s in enumerate(top_sources) if s in golden), None)
        got = set(top_sources) & golden

        rec = {
            "id": item["id"],
            "dimension": item["dimension"],
            "query": item["query"],
            "golden": item["golden"],
            "top10": top10,
            "top_sources": top_sources,
            "rank": rank,
            "rr": round(1.0 / rank, 4) if rank else 0.0,
            "recall": round(len(got) / len(golden), 4) if golden else 0.0,
            "latency_ms": round(latency_ms, 1),
            "top1_score": top10[0]["score"] if top10 else None,
        }
        results.append(rec)
        print(f"[#{i:02d}/{len(queries)}] {'rank=' + str(rank) if rank else 'MISS':>8}"
              f"  {latency_ms:7.1f}ms  {(rec['top1_score'] or 0):.4f}  {top_sources[0] if top_sources else '-'}")

    lat = [r["latency_ms"] for r in results]
    summary = {
        "n_queries": len(results),
        "mrr@10": round(statistics.mean(r["rr"] for r in results), 4),
        "hit_rate@10": round(statistics.mean(1 if r["rank"] else 0 for r in results), 4),
        "top1_accuracy": round(statistics.mean(1 if r["rank"] == 1 else 0 for r in results), 4),
        "recall@10": round(statistics.mean(r["recall"] for r in results), 4),
        "mean_latency_ms": round(statistics.mean(lat), 1),
        "median_latency_ms": round(statistics.median(lat), 1),
        "mean_top1_conf": round(statistics.mean(r["top1_score"] or 0 for r in results), 4),
        "by_dimension": {},
    }
    for dim in sorted({r["dimension"] for r in results}):
        sub = [r for r in results if r["dimension"] == dim]
        summary["by_dimension"][dim] = {
            "n": len(sub),
            "mrr@10": round(statistics.mean(r["rr"] for r in sub), 4),
            "recall@10": round(statistics.mean(r["recall"] for r in sub), 4),
            "hit_rate@10": round(statistics.mean(1 if r["rank"] else 0 for r in sub), 4),
        }

    meta = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "n_results": n_results,
        "reranker_active": reranker_active,
        "retriever_sha256_8": retriever_sha,
    }
    return {"meta": meta, "summary": summary, "results": results}


def write_reports(data, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"benchmark_{data['meta']['ts'].replace(':', '').replace('-', '')}_{data['meta']['label']}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    s = data["summary"]
    lines = [
        f"# 检索基准评测报告 — {data['meta']['label']}",
        "",
        f"- 时间：{data['meta']['ts']} | reranker：{'生效' if data['meta']['reranker_active'] else '降级'} | retriever.py sha256[:8]：{data['meta']['retriever_sha256_8']}",
        f"- 查询数：{s['n_queries']}（评测集 benchmark_queries.json v1，标注粒度=source）",
        "",
        "## 总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| MRR@10 | **{s['mrr@10']}** |",
        f"| HitRate@10（黄金进前10） | {s['hit_rate@10']} |",
        f"| Top1 准确率 | {s['top1_accuracy']} |",
        f"| Recall@10（多黄金平均召回） | {s['recall@10']} |",
        f"| 延迟 mean / median | {s['mean_latency_ms']}ms / {s['median_latency_ms']}ms |",
        f"| top1 置信度均值 | {s['mean_top1_conf']} |",
        "",
        "## 分维度",
        "",
        "| 维度 | 条数 | MRR@10 | Recall@10 | HitRate@10 |",
        "|---|---|---|---|---|",
    ]
    for dim, d in s["by_dimension"].items():
        lines.append(f"| {dim} | {d['n']} | {d['mrr@10']} | {d['recall@10']} | {d['hit_rate@10']} |")

    missed = [r for r in data["results"] if not r["rank"]]
    partial = [r for r in data["results"] if r["rank"] and r["recall"] < 1.0]
    lines += ["", f"## 未命中（黄金未进前10）：{len(missed)} 条", ""]
    if missed:
        lines += ["| id | 查询 | 黄金 | 实际 top3 |", "|---|---|---|---|"]
        for r in missed:
            lines.append(f"| {r['id']} | {r['query']} | {'<br>'.join(r['golden'])} | {'<br>'.join(r['top_sources'][:3])} |")
    lines += ["", f"## 部分命中（多黄金未召回全）：{len(partial)} 条", ""]
    if partial:
        lines += ["| id | 查询 | 召回/总数 | 缺失 |", "|---|---|---|---|"]
        for r in partial:
            missing = set(r["golden"]) - set(r["top_sources"])
            lines.append(f"| {r['id']} | {r['query']} | {round(r['recall']*len(r['golden']))}/{len(r['golden'])} | {'<br>'.join(sorted(missing))} |")
    lines += ["", "> 逐查询明细（top10 分数/延迟）见同名 JSON 文件。", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def diff_runs(old_path, new_path):
    old = json.loads(Path(old_path).read_text(encoding="utf-8"))
    new = json.loads(Path(new_path).read_text(encoding="utf-8"))
    old_by_id = {r["id"]: r for r in old["results"]}

    identical = reordered = 0
    reorder_list = []
    max_drift = 0.0
    for r_new in new["results"]:
        r_old = old_by_id.get(r_new["id"])
        if not r_old:
            continue
        if r_new["top_sources"] == r_old["top_sources"]:
            identical += 1
        else:
            reordered += 1
            reorder_list.append((r_new["id"], r_new["query"],
                                 r_old["top_sources"][:5], r_new["top_sources"][:5]))
        for h_old, h_new in zip(r_old["top10"], r_new["top10"]):
            if h_old["source"] == h_new["source"]:
                max_drift = max(max_drift, abs(h_old["score"] - h_new["score"]))

    n = identical + reordered
    print(f"对比 {n} 条查询：结果顺序完全一致 {identical}，有重排 {reordered}，分数最大漂移 {max_drift:.6f}")
    for qs_id, q, o5, n5 in reorder_list:
        print(f"  [#{qs_id}] {q}\n    旧: {o5}\n    新: {n5}")
    so, sn = old["summary"], new["summary"]
    print(f"MRR@10 {so['mrr@10']} → {sn['mrr@10']} | Recall@10 {so['recall@10']} → {sn['recall@10']}"
          f" | 延迟 {so['mean_latency_ms']}ms → {sn['mean_latency_ms']}ms")
    if reordered == 0:
        print("✅ 行为保持验证通过（逐查询结果顺序与旧版完全一致）")
    return 0 if reordered == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="只跑前 N 条（冒烟）")
    ap.add_argument("--label", default="run", help="运行标签，进报告文件名")
    ap.add_argument("--n-results", type=int, default=10, help="检索条数（评测@N）")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="报告输出目录")
    ap.add_argument("--diff", nargs=2, metavar=("OLD.json", "NEW.json"), help="对比两次运行")
    args = ap.parse_args()

    if args.diff:
        sys.exit(diff_runs(args.diff[0], args.diff[1]))

    queries = load_queries(args.n)
    data = run_benchmark(queries, args.n_results, args.label)
    json_path, md_path = write_reports(data, Path(args.out_dir))
    s = data["summary"]
    print(f"\nMRR@10={s['mrr@10']} HitRate@10={s['hit_rate@10']} Top1={s['top1_accuracy']}"
          f" Recall@10={s['recall@10']} 延迟mean={s['mean_latency_ms']}ms")
    print(f"报告：{md_path}\n明细：{json_path}")


if __name__ == "__main__":
    main()
