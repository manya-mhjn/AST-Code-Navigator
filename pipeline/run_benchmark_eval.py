"""
run_benchmark_eval.py — Automated Benchmark Testing & Evaluation Harness.

Reads questions from pipeline.benchmark_dataset, executes NextGenCodeNavigatorAgent,
evaluates generated answers against ground-truth solutions using an automated judge,
and outputs complete responses and metadata to both JSON and Markdown reports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from pipeline.agentic_nextgen import NextGenCodeNavigatorAgent
from pipeline.benchmark_dataset import (
    BENCHMARK_DATASET,
    get_benchmark_item,
    get_questions_by_category,
)
from pipeline.utils import get_llm

load_dotenv(override=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class JudgeEvaluationSchema(BaseModel):
    is_correct: bool = Field(
        ...,
        description="True if the agent's answer accurately captures the core technical facts, symbols, files, and conclusions in the ground truth solution.",
    )
    confidence_score: float = Field(
        default=1.0,
        description="Confidence score between 0.0 and 1.0.",
    )
    verdict_reason: str = Field(
        ...,
        description="Clear, concise explanation of why the answer was marked correct or incorrect.",
    )
    key_entities_matched: List[str] = Field(
        default_factory=list,
        description="List of specific functions, files, variables, or formulas correctly identified.",
    )
    missing_or_incorrect: List[str] = Field(
        default_factory=list,
        description="List of required entities, paths, or formulas that were missed or hallucinated.",
    )


def evaluate_with_judge(
    question: str,
    ground_truth: str,
    agent_answer: str,
    expected_tools: Optional[str] = None,
) -> JudgeEvaluationSchema:
    """Uses LLM judge to evaluate the agent answer against the ground truth solution."""
    prompt = (
        "You are an impartial, rigorous software architecture benchmark judge.\n"
        "Your task is to evaluate whether the Agent's generated answer accurately and factually answers the developer query according to the verified Ground Truth Solution.\n\n"
        f"Developer Query:\n{question}\n\n"
        f"Ground Truth Solution:\n{ground_truth}\n\n"
        f"Agent's Generated Answer:\n{agent_answer}\n\n"
        "EVALUATION CRITERIA:\n"
        "1. Correctness: Did the agent identify the correct function names, class names, file paths, line numbers, or formulas stated in the Ground Truth?\n"
        "2. Semantic Intent: If the query had typos or near-misses, did the agent correctly resolve the real symbol?\n"
        "3. Hallucination Check: Did the agent invent nonexistent functions or false conclusions?\n"
        "4. Calling sites & line numbers: If the agent accurately identifies the correct calling functions and files, mark `is_correct: true` (minor differences such as citing the caller function's start line vs the internal invocation line should not cause a failure if the calling functions and file paths are factually correct).\n\n"
        "Return ONLY a JSON object matching this schema:\n"
        "{\n"
        '  "is_correct": true | false,\n'
        '  "confidence_score": 0.95,\n'
        '  "verdict_reason": "Summary of evaluation verdict",\n'
        '  "key_entities_matched": ["symbol_a", "file_b"],\n'
        '  "missing_or_incorrect": []\n'
        "}\n"
    )

    try:
        llm = get_llm(temperature=0.0)
        res = llm.invoke(prompt)
        text = res.content if hasattr(res, "content") else str(res)
        clean = re.sub(r"^```(?:json)?\s*", "", text.strip())
        clean = re.sub(r"\s*```$", "", clean)
        m = re.search(r"(\{.*\})", clean, re.DOTALL)
        if m:
            return JudgeEvaluationSchema.model_validate_json(m.group(1))
    except Exception as e:
        print(f"   [!] Judge LLM call failed ({e}). Running deterministic keyword overlap.")

    # Deterministic fallback judge: entity extraction & match
    keywords = re.findall(r"`([a-zA-Z0-9_\.\:]+)`", ground_truth)
    if not keywords:
        keywords = re.findall(r"\b([a-zA-Z0-9_]{4,})\b", ground_truth)

    matched = [k for k in keywords if k.lower() in agent_answer.lower()]
    missing = [k for k in keywords if k.lower() not in agent_answer.lower()]
    match_ratio = len(matched) / max(1, len(keywords))

    is_correct = match_ratio >= 0.4 or len(matched) >= 2
    return JudgeEvaluationSchema(
        is_correct=is_correct,
        confidence_score=round(match_ratio, 2),
        verdict_reason=f"Heuristic match: found {len(matched)}/{len(keywords)} key entities from ground truth.",
        key_entities_matched=matched[:5],
        missing_or_incorrect=missing[:5],
    )


def run_benchmark(
    question_ids: Optional[List[str]] = None,
    category: Optional[str] = None,
    limit: Optional[int] = None,
    output_json_path: str = "benchmark_eval_results.json",
    output_md_path: str = "benchmark_eval_report.md",
    antigravity_artifact_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the benchmark evaluation harness across selected questions."""
    # 1. Resolve questions to test
    selected_items: List[Dict[str, Any]] = []

    if question_ids:
        for qid in question_ids:
            item = get_benchmark_item(qid)
            if item:
                selected_items.append(item)
            else:
                print(f"[!] Warning: Question ID '{qid}' not found in benchmark_dataset.")
    elif category:
        selected_items = get_questions_by_category(category)
    else:
        selected_items = list(BENCHMARK_DATASET.values())

    if limit and limit > 0:
        selected_items = selected_items[:limit]

    print("=" * 80)
    print(f"  CodeNavigator Benchmark Evaluation Harness")
    print(f"  Total Questions Queued: {len(selected_items)}")
    print(f"  Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    agent = NextGenCodeNavigatorAgent(repo_path=".")
    results: List[Dict[str, Any]] = []

    passed_count = 0
    failed_count = 0
    total_latency = 0.0

    for idx, item in enumerate(selected_items, start=1):
        qid = item["id"]
        qtext = item["question"]
        gt_answer = item["answer"]
        expected_tools = item.get("tool_chain", "")
        cat = item.get("category", "General")

        print(f"\n[{idx}/{len(selected_items)}] Evaluating {qid}: \"{qtext}\"")
        print(f"     Category: {cat}")
        print(f"     Expected Tool Chain: {expected_tools}")

        start_time = time.time()
        agent_state: Dict[str, Any] = {}
        error_msg: Optional[str] = None

        try:
            agent_state = agent.ask_detailed(qtext)
            agent_answer = agent_state.get("final_response", "")
        except Exception as e:
            error_msg = str(e)
            agent_answer = f"Agent crashed with exception: {error_msg}"
            print(f"     [!] Agent Execution Failed: {error_msg}")

        latency = round(time.time() - start_time, 2)
        total_latency += latency

        # Run Judge Evaluation
        print(f"     >> Judging response against Ground Truth...")
        judge_res = evaluate_with_judge(
            question=qtext,
            ground_truth=gt_answer,
            agent_answer=agent_answer,
            expected_tools=expected_tools,
        )

        status_str = "PASS" if judge_res.is_correct else "FAIL"
        if judge_res.is_correct:
            passed_count += 1
            print(f"     [+] Verdict: [PASS] (Confidence: {judge_res.confidence_score:.0%}) - {judge_res.verdict_reason}")
        else:
            failed_count += 1
            print(f"     [-] Verdict: [FAIL] (Confidence: {judge_res.confidence_score:.0%}) - {judge_res.verdict_reason}")

        # Extract tools called by code
        trace = agent_state.get("execution_trace", [])
        tools_called_by_code = [t.get("tool_name") for t in trace if isinstance(t, dict)]

        # Streamlined record strictly matching requested format
        record = {
            "question_id": qid,
            "question": qtext,
            "is_correct": judge_res.is_correct,
            "tools_called_by_code": tools_called_by_code,
            "correct_tools_expected": expected_tools,
            "agent_final_response": agent_answer,
            "ground_truth_answer": gt_answer,
            "verdict_reason": judge_res.verdict_reason,
            "latency_seconds": latency,
        }
        results.append(record)

        # Incrementally update JSON and Markdown reports immediately after each question
        current_accuracy = (passed_count / len(results) * 100) if results else 0.0
        current_avg_latency = (total_latency / len(results)) if results else 0.0
        live_summary = {
            "timestamp": datetime.now().isoformat(),
            "total_evaluated": len(results),
            "total_target": len(selected_items),
            "passed": passed_count,
            "failed": failed_count,
            "accuracy_percent": round(current_accuracy, 1),
            "average_latency_seconds": round(current_avg_latency, 2),
            "results": results,
        }

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(live_summary, f, indent=2, ensure_ascii=False)
        print(f"     [>] Progress updated in {output_json_path} ({len(results)}/{len(selected_items)})")

        live_md = generate_markdown_report(live_summary)
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(live_md)
        if antigravity_artifact_path:
            os.makedirs(os.path.dirname(antigravity_artifact_path), exist_ok=True)
            with open(antigravity_artifact_path, "w", encoding="utf-8") as f:
                f.write(live_md)

    summary = live_summary
    accuracy = current_accuracy
    avg_latency = current_avg_latency
    print(f"\n[+] Full JSON results saved to: {output_json_path}")
    print(f"[+] Markdown Evaluation Report saved to: {output_md_path}")
    if antigravity_artifact_path:
        print(f"[+] Antigravity artifact synchronized to: {antigravity_artifact_path}")

    # Print Terminal Summary
    print("\n" + "=" * 80)
    print(f"  BENCHMARK EVALUATION SUMMARY")
    print(f"  Total Questions:   {len(selected_items)}")
    print(f"  Passed:            {passed_count} ({accuracy:.1f}%)")
    print(f"  Failed:            {failed_count}")
    print(f"  Average Latency:   {avg_latency:.2f}s")
    print("=" * 80)

    return summary


def generate_markdown_report(summary: Dict[str, Any]) -> str:
    """Builds a GitHub-flavored Markdown evaluation report table."""
    total = summary["total_evaluated"]
    passed = summary["passed"]
    failed = summary["failed"]
    accuracy = summary["accuracy_percent"]
    avg_lat = summary["average_latency_seconds"]

    lines = [
        "# CodeNavigator Next-Gen Agent: Benchmark Evaluation Report",
        "",
        f"**Evaluation Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Repository:** `LLM-DND`  ",
        f"**Architecture:** 3-Call Consolidated Batch Evaluation (`agentic_nextgen.py`)  ",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| **Total Evaluated** | `{total}` |",
        f"| **Passed** | **`{passed}`** |",
        f"| **Failed** | `{failed}` |",
        f"| **Accuracy Rate** | **`{accuracy:.1f}%`** |",
        f"| **Average Latency** | `{avg_lat:.2f}s` |",
        "",
        "---",
        "",
        "## Benchmark Results Table",
        "",
        "| Question # | Status | Question | Tools Called by Code | Correct Tools Expected | Verdict Reason |",
        "|:---:|:---:|:---|:---|:---|:---|",
    ]

    for r in summary["results"]:
        badge = "🟢 PASS" if r["is_correct"] else "🔴 FAIL"
        qid = r["question_id"]
        qtext = r["question"].replace("|", "\\|")
        tools_called = ", ".join(r.get("tools_called_by_code", [])) or "None"
        tools_expected = r.get("correct_tools_expected", "").replace("|", "\\|")
        reason = r["verdict_reason"].replace("|", "\\|").replace("\n", " ")
        if len(reason) > 85:
            reason = reason[:85] + "..."

        lines.append(f"| **{qid}** | {badge} | {qtext} | `{tools_called}` | `{tools_expected}` | {reason} |")

    lines.extend([
        "",
        "---",
        "",
        "## Detailed Question Breakdown",
        "",
    ])

    for r in summary["results"]:
        status_label = "✅ PASSED" if r["is_correct"] else "❌ FAILED"
        lines.extend([
            f"### {r['question_id']}: {r['question']} ({status_label})",
            f"- **Tools Called by Code:** `{r.get('tools_called_by_code', [])}`",
            f"- **Correct Tools Expected:** `{r.get('correct_tools_expected', '')}`",
            f"- **Verdict Reason:** {r['verdict_reason']}",
            "",
            "#### Final Response from Agent (Your Code):",
            f"```markdown\n{r.get('agent_final_response', '')}\n```",
            "",
            "#### Correct Ground Truth Answer (From JSON):",
            f"```markdown\n{r.get('ground_truth_answer', '')}\n```",
            "",
            "---",
            "",
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeNavigator Benchmark Evaluation Harness CLI")
    parser.add_argument("pos_questions", nargs="*", default=[], help="Question IDs (e.g. Q01 Q02 Q42)")
    parser.add_argument("-q", "--questions", nargs="*", help="Specific Question IDs to evaluate (e.g. Q01 Q02 Q42)")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (e.g. 'Upstream Callers', 'Deliberate Typos')")
    parser.add_argument("--limit", type=int, default=None, help="Max number of questions to run")
    parser.add_argument("--all", action="store_true", help="Run all 200 questions in the benchmark suite")
    parser.add_argument("--out-json", type=str, default="benchmark_eval_results.json", help="Path for JSON output")
    parser.add_argument("--out-md", type=str, default="benchmark_eval_report.md", help="Path for Markdown report")

    args = parser.parse_args()

    default_antigravity_artifact = r"C:\Users\manmahaj2\.gemini\antigravity\brain\e0e6b63b-77f0-4bcb-97eb-1fe769668205\benchmark_eval_report.md"

    # Merge positional questions or --questions flag
    q_ids = args.questions or args.pos_questions or None
    limit = args.limit
    if not args.all and not q_ids and not args.category and not limit:
        print("[*] No specific arguments provided. Defaulting to first 3 sample benchmark questions (Q01, Q02, Q03).")
        q_ids = ["Q01", "Q02", "Q03"]

    run_benchmark(
        question_ids=q_ids,
        category=args.category,
        limit=limit,
        output_json_path=args.out_json,
        output_md_path=args.out_md,
        antigravity_artifact_path=default_antigravity_artifact,
    )
