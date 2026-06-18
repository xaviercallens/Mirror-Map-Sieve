#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
HorizonMath v12 GPU Job Monitor
================================
Polls Cloud Run Job execution status, GPU metrics, costs and logs
every 5 minutes. Prints a rich live dashboard to the terminal.

Usage:
  python scripts/monitor_gpu_job.py --execution <EXECUTION_NAME>
  python scripts/monitor_gpu_job.py --auto   # auto-detect latest execution

Environment:
  GCP_PROJECT   : GCP project ID (default: gen-lang-client-0625573011)
  GCS_BUCKET    : Results bucket  (default: gs://symbrain-v12-results)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# H100 hourly rate per node (USD)
H100_HOURLY_RATE = 4.76
GCS_BUCKET = os.environ.get("GCS_BUCKET", "gs://symbrain-v12-results")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "gen-lang-client-0625573011")
JOB_NAME = "horizonmath-v12-top10"
REGION = "us-central1"
BUDGET_USD = 200.0

SOLVABILITY_LABELS = {1: "Class 1 (Olympiad)", 2: "Class 2 (Hard)", 3: "Class 3 (Frontier)"}

TOP10_PROBLEMS = [
    {"id": "w5_watson_integral",       "solvability": 3, "tier": "4x H100"},
    {"id": "w6_watson_integral",       "solvability": 3, "tier": "4x H100"},
    {"id": "bessel_moment_c5_0",       "solvability": 3, "tier": "4x H100"},
    {"id": "bessel_moment_c5_1",       "solvability": 3, "tier": "4x H100"},
    {"id": "box_integral_b5_neg2",     "solvability": 3, "tier": "4x H100"},
    {"id": "feigenbaum_delta",         "solvability": 3, "tier": "4x H100"},
    {"id": "anderson_lyapunov_exponent","solvability": 3, "tier": "4x H100"},
    {"id": "autocorr_signed_upper",    "solvability": 2, "tier": "1x H100"},
    {"id": "elliptic_k_moment_4",      "solvability": 2, "tier": "1x H100"},
    {"id": "calabi_yau_c5",            "solvability": 2, "tier": "1x H100"},
]


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_job_executions() -> list[dict]:
    """List all executions for the HorizonMath job."""
    res = run(["gcloud", "run", "jobs", "executions", "list",
               "--job", JOB_NAME, "--region", REGION, "--format=json"])
    if res.returncode != 0:
        return []
    try:
        return json.loads(res.stdout) if res.stdout.strip() else []
    except json.JSONDecodeError:
        return []


def get_execution_status(execution_name: str) -> dict:
    """Get detailed status of a specific execution."""
    res = run(["gcloud", "run", "jobs", "executions", "describe",
               execution_name, "--region", REGION, "--format=json"])
    if res.returncode != 0:
        return {}
    try:
        return json.loads(res.stdout) if res.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def get_recent_logs(execution_name: str, lines: int = 50) -> list[str]:
    """Pull recent Cloud Logging entries for the job execution."""
    filter_str = (
        f'resource.type="cloud_run_job" '
        f'resource.labels.job_name="{JOB_NAME}" '
        f'resource.labels.execution_name="{execution_name}"'
    )
    res = run([
        "gcloud", "logging", "read", filter_str,
        "--project", GCP_PROJECT,
        "--limit", str(lines),
        "--format=json",
        "--freshness=30m",
    ])
    if res.returncode != 0 or not res.stdout.strip():
        return []
    try:
        entries = json.loads(res.stdout)
        return [e.get("textPayload", e.get("jsonPayload", {}).get("message", ""))
                for e in entries if e.get("textPayload") or e.get("jsonPayload")]
    except json.JSONDecodeError:
        return []


def list_gcs_results() -> list[str]:
    """List completed result files in GCS."""
    res = run(["gsutil", "ls", f"{GCS_BUCKET}/horizonmath-v12/"])
    if res.returncode != 0:
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip().endswith(".json")]


def estimate_cost(start_time_str: str, nodes_class3: int = 4, nodes_class2: int = 1) -> dict:
    """Estimate accumulated GPU cost based on elapsed time."""
    if not start_time_str:
        return {"estimated_usd": 0.0, "elapsed_minutes": 0.0}
    try:
        start = datetime.datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds() / 3600
        # 7 Class 3 problems (4x H100) + 3 Class 2 (1x H100), run in parallel (10 tasks)
        # In parallel mode, cost = max(class3_cost, class2_cost) — tasks run simultaneously
        cost_class3 = nodes_class3 * H100_HOURLY_RATE * elapsed
        cost_class2 = nodes_class2 * H100_HOURLY_RATE * elapsed
        total = cost_class3  # Class 3 tasks dominate (more GPUs, longer tasks)
        return {
            "estimated_usd": round(total, 4),
            "elapsed_hours": round(elapsed, 3),
            "elapsed_minutes": round(elapsed * 60, 1),
            "hourly_rate_usd": round(nodes_class3 * H100_HOURLY_RATE, 2),
            "budget_remaining_usd": round(BUDGET_USD - total, 2),
            "budget_pct_used": round(total / BUDGET_USD * 100, 1),
        }
    except Exception:
        return {"estimated_usd": 0.0, "elapsed_minutes": 0.0}


def parse_task_results_from_logs(logs: list[str]) -> list[dict]:
    """Extract TASK_COMPLETE events from log lines."""
    completed = []
    for line in logs:
        try:
            if isinstance(line, dict):
                if line.get("event") == "TASK_COMPLETE":
                    completed.append(line)
            elif isinstance(line, str) and "TASK_COMPLETE" in line:
                data = json.loads(line)
                if data.get("event") == "TASK_COMPLETE":
                    completed.append(data)
        except Exception:
            pass
    return completed


def print_dashboard(
    execution_name: str,
    status: dict,
    logs: list[str],
    gcs_results: list[str],
    poll_count: int,
    start_time: str,
) -> None:
    """Print rich terminal dashboard."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Parse execution status
    conditions = status.get("status", {}).get("conditions", [{}])
    exec_status = conditions[0].get("type", "Unknown") if conditions else "Unknown"
    succeeded = status.get("status", {}).get("succeededCount", 0)
    failed = status.get("status", {}).get("failedCount", 0)
    running = status.get("status", {}).get("runningCount", 0)

    cost_info = estimate_cost(start_time)
    completed_tasks = parse_task_results_from_logs(logs)

    # Build status matrix for all 10 problems
    completed_ids = {t.get("problem_id") for t in completed_tasks}
    gcs_ids = {Path(g).stem.split("_", 2)[-1] for g in gcs_results}

    header = "=" * 78
    print(f"\n{header}")
    print(f"  🏺 SYMBRAIN v12 — HorizonMath GPU Execution Monitor  [Poll #{poll_count}]")
    print(f"  📅 {now}  |  Execution: {execution_name}")
    print(header)

    print(f"\n  📊 JOB STATUS")
    print(f"  ├─ Cloud Run Status : {exec_status}")
    print(f"  ├─ Tasks Succeeded  : {succeeded} / 10")
    print(f"  ├─ Tasks Running    : {running}")
    print(f"  └─ Tasks Failed     : {failed}")

    print(f"\n  💰 COST TRACKING")
    print(f"  ├─ Elapsed Time     : {cost_info.get('elapsed_minutes', 0):.1f} min")
    print(f"  ├─ Estimated Cost   : ${cost_info.get('estimated_usd', 0):.4f}")
    print(f"  ├─ Hourly Rate      : ${cost_info.get('hourly_rate_usd', H100_HOURLY_RATE * 4):.2f}/hr")
    print(f"  ├─ Budget Used      : {cost_info.get('budget_pct_used', 0):.1f}% of ${BUDGET_USD:.0f}")
    remaining = cost_info.get("budget_remaining_usd", BUDGET_USD)
    status_color = "✅" if remaining > 50 else ("⚠️" if remaining > 10 else "🚨")
    print(f"  └─ Budget Remaining : {status_color} ${remaining:.2f}")

    print(f"\n  🧮 PROBLEM STATUS")
    print(f"  {'#':<3} {'Problem ID':<35} {'Class':<10} {'Tier':<10} {'Status'}")
    print(f"  {'-'*3} {'-'*35} {'-'*10} {'-'*10} {'-'*12}")
    for i, prob in enumerate(TOP10_PROBLEMS):
        pid = prob["id"]
        cls = f"Cl {prob['solvability']}"
        tier = prob["tier"]
        if pid in completed_ids or pid in gcs_ids:
            # Find the task result
            task_res = next((t for t in completed_tasks if t.get("problem_id") == pid), {})
            conf = task_res.get("galois_confidence", "?")
            num_status = task_res.get("numeric_status", "?")
            status_str = f"✅ DONE  (conf={conf}, num={num_status})"
        elif i < succeeded:
            status_str = "✅ DONE"
        elif i < succeeded + running:
            status_str = "🔄 RUNNING"
        elif failed > 0 and i >= 10 - failed:
            status_str = "❌ FAILED"
        else:
            status_str = "⏳ QUEUED"
        print(f"  {i+1:<3} {pid:<35} {cls:<10} {tier:<10} {status_str}")

    print(f"\n  📋 RECENT LOGS (last 5 lines)")
    visible_logs = [l for l in logs if l and len(str(l)) > 5][-5:]
    for entry in visible_logs:
        preview = str(entry)[:120].replace("\n", " ")
        print(f"  │ {preview}")

    print(f"\n  📦 GCS Results ({len(gcs_results)} files uploaded)")
    for g in gcs_results[-3:]:
        print(f"  └─ {g}")

    budget_alert = cost_info.get("estimated_usd", 0) > BUDGET_USD * 0.8
    if budget_alert:
        print(f"\n  ⚠️  WARNING: Approaching budget limit! ${cost_info.get('estimated_usd', 0):.2f} / ${BUDGET_USD}")

    print(f"\n{header}")
    print(f"  Next poll in 5 minutes. Press Ctrl+C to stop monitoring.")
    print(f"{header}\n")


def monitor(execution_name: str | None, poll_interval_seconds: int = 300) -> None:
    """Main monitoring loop — polls every 5 minutes."""
    print(f"\n🚀 Starting HorizonMath v12 GPU Job Monitor")
    print(f"   Project: {GCP_PROJECT} | Region: {REGION} | Job: {JOB_NAME}")

    poll_count = 0
    start_time = None

    while True:
        poll_count += 1

        # Auto-detect latest execution if not specified
        if not execution_name:
            executions = get_job_executions()
            if executions:
                execution_name = executions[0].get("metadata", {}).get("name", "")
                print(f"   Auto-detected execution: {execution_name}")
            else:
                print(f"   ⏳ No executions found for job '{JOB_NAME}'. Waiting...")
                time.sleep(60)
                continue

        # Fetch status
        status = get_execution_status(execution_name)
        if not start_time:
            start_time = status.get("metadata", {}).get("creationTimestamp", "")

        # Fetch logs
        logs = get_recent_logs(execution_name)

        # Fetch GCS results
        gcs_results = list_gcs_results()

        # Render dashboard
        print_dashboard(execution_name, status, logs, gcs_results, poll_count, start_time)

        # Check completion
        conditions = status.get("status", {}).get("conditions", [{}])
        exec_status = conditions[0].get("type", "") if conditions else ""
        succeeded = status.get("status", {}).get("succeededCount", 0)
        failed_count = status.get("status", {}).get("failedCount", 0)

        if exec_status == "Complete" or succeeded + failed_count >= 10:
            cost_info = estimate_cost(start_time)
            print(f"\n{'='*78}")
            print(f"  🏁 EXECUTION COMPLETE!")
            print(f"  ✅ Succeeded: {succeeded}/10  ❌ Failed: {failed_count}/10")
            print(f"  💰 Total Cost: ${cost_info.get('estimated_usd', 0):.4f}")
            print(f"  📦 GCS Results: {len(gcs_results)} files in {GCS_BUCKET}")
            print(f"{'='*78}\n")
            break

        time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor HorizonMath v12 GPU Job")
    parser.add_argument("--execution", default=None,
                        help="Cloud Run execution name (auto-detect if not set)")
    parser.add_argument("--interval", type=int, default=300,
                        help="Poll interval in seconds (default: 300 = 5 min)")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-detect latest execution")
    args = parser.parse_args()

    execution = args.execution if not args.auto else None
    monitor(execution, args.interval)


if __name__ == "__main__":
    main()
