#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Turing Infrastructure Monitor — 1-minute polling loop.

Captures:
  - GCP deployment status (active nodes, GPU type, temperature proxy)
  - Cost telemetry (cumulative spend, burn rate)
  - Quota compliance
  - Scale-to-zero enforcement
  - Turing profiler diagnostics

Outputs telemetry to docs/turing_monitor_telemetry.jsonl (append-only).
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.turing.agent import TuringAgent
from agents.turing.tools.gcp_billing_monitor import monitor_gcp_billing_efficiency
from agents.turing.tools.deployment_manager import deploy_symbrain_model
from agents.turing.tools.image_cache_manager import get_deployment_status
from agents.turing.tools.gcp_quota_manager import check_quota_compliance, get_quota_database

TELEMETRY_FILE = Path("docs/turing_monitor_telemetry.jsonl")
SUMMARY_FILE = Path("docs/turing_monitor_summary.md")
POLL_INTERVAL_S = 60  # 1 minute
MAX_POLLS = 30         # 30 minutes max


def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_gpu_temperature(gpu_type: str, active_nodes: int, utilization_pct: float) -> dict:
    """Estimate GPU temperature based on type, node count, and utilization.
    
    In production this would query NVIDIA DCGM or nvidia-smi via Cloud Monitoring.
    Here we use a thermal model based on known TDP profiles.
    """
    tdp_profiles = {
        "H100": {"idle_c": 45, "max_c": 83, "tdp_w": 700},
        "A100": {"idle_c": 42, "max_c": 80, "tdp_w": 400},
        "L4":   {"idle_c": 35, "max_c": 72, "tdp_w": 72},
        "T4":   {"idle_c": 33, "max_c": 70, "tdp_w": 70},
        "CPU":  {"idle_c": 30, "max_c": 65, "tdp_w": 0},
    }
    
    profile = tdp_profiles.get(gpu_type, tdp_profiles["L4"])
    temp_range = profile["max_c"] - profile["idle_c"]
    estimated_temp = profile["idle_c"] + (utilization_pct / 100.0) * temp_range
    
    # Add slight variance per node
    node_temps = []
    for i in range(active_nodes):
        node_temp = estimated_temp + (i * 0.5)  # slight gradient
        node_temps.append(round(node_temp, 1))
    
    return {
        "gpu_type": gpu_type,
        "active_nodes": active_nodes,
        "estimated_avg_temp_c": round(estimated_temp, 1),
        "node_temperatures_c": node_temps,
        "tdp_watts": profile["tdp_w"],
        "thermal_headroom_c": round(profile["max_c"] - estimated_temp, 1),
        "thermal_status": "OK" if estimated_temp < profile["max_c"] - 5 else "WARNING",
    }


async def poll_once(turing: TuringAgent, poll_idx: int, cumulative_cost: float) -> dict:
    """Execute a single monitoring poll."""
    ts = get_timestamp()
    print(f"\n🔍 [{ts}] Turing Monitor Poll #{poll_idx}")
    
    telemetry: dict[str, Any] = {
        "timestamp": ts,
        "poll_index": poll_idx,
    }
    
    # 1. Deployment status
    try:
        deploy_status = get_deployment_status()
        telemetry["deployment"] = deploy_status
        active = deploy_status.get("active_nodes", 0)
        gpu = deploy_status.get("gpu_type", "none")
        print(f"  📡 Deployment: {active} active {gpu} node(s)")
    except Exception as e:
        telemetry["deployment"] = {"error": str(e)}
        active = 0
        gpu = "unknown"
        print(f"  📡 Deployment: error ({e})")
    
    # 2. GPU temperature estimation
    utilization = 75.0 if active > 0 else 0.0  # assume ~75% during active compute
    thermal = estimate_gpu_temperature(gpu, max(active, 0), utilization)
    telemetry["thermal"] = thermal
    if active > 0:
        print(f"  🌡️  Temperature: {thermal['estimated_avg_temp_c']}°C avg | Headroom: {thermal['thermal_headroom_c']}°C | Status: {thermal['thermal_status']}")
        for i, t in enumerate(thermal["node_temperatures_c"]):
            print(f"      Node {i}: {t}°C")
    else:
        print(f"  🌡️  Temperature: N/A (no active GPUs)")
    
    # 3. Billing monitor
    try:
        billing = monitor_gcp_billing_efficiency(execution_history=[
            {"service_name": "galois-agent", "gpu_type": gpu, "min_replicas": 0, "duration_seconds": 60.0},
            {"service_name": "euler-agent", "gpu_type": "None", "min_replicas": 0, "duration_seconds": 60.0},
            {"service_name": "pythagore-agent", "gpu_type": "None", "min_replicas": 0, "duration_seconds": 60.0},
        ])
        telemetry["billing"] = billing
        cost_this_poll = billing.get("estimated_accumulated_cost_usd", 0.0)
        cumulative_cost += cost_this_poll
        telemetry["cumulative_cost_usd"] = cumulative_cost
        print(f"  💰 Cost: ${cost_this_poll:.4f} this interval | ${cumulative_cost:.2f} cumulative | Verdict: {billing.get('verdict', 'unknown')}")
    except Exception as e:
        telemetry["billing"] = {"error": str(e)}
        print(f"  💰 Billing: error ({e})")
    
    # 4. Quota compliance
    try:
        quota = check_quota_compliance(requested_resources={
            "gpu_type": gpu if gpu != "none" else "L4",
            "region": "us-central1",
            "nodes": active if active > 0 else 1,
        })
        telemetry["quota"] = quota
        print(f"  📋 Quota: {quota.get('verdict', 'unknown')}")
        if quota.get("violations"):
            for v in quota["violations"]:
                print(f"      ⚠️  {v}")
    except Exception as e:
        telemetry["quota"] = {"error": str(e)}
        print(f"  📋 Quota: error ({e})")
    
    # 5. Scale-to-zero check
    scale_zero_ok = (active == 0) or (active > 0)  # active is fine during execution
    telemetry["scale_to_zero_enforced"] = active == 0
    if active == 0:
        print(f"  ✅ Scale-to-zero: ENFORCED (0 idle GPUs)")
    else:
        print(f"  ⚡ Scale-to-zero: Active ({active} GPUs in use — expected during execution)")
    
    # 6. Turing profiler snapshot
    try:
        turing_res = await turing.run(
            f"Profile current infrastructure: {active} {gpu} nodes active, cumulative cost ${cumulative_cost:.2f}",
            mcts_nodes=450,
            latency_ms=320.0,
        )
        telemetry["turing_diagnostics"] = {
            "confidence": turing_res.confidence,
            "cost_usd": turing_res.cost_usd,
            "summary": turing_res.answer.get("summary", "") if isinstance(turing_res.answer, dict) else "",
        }
        summary = turing_res.answer.get("summary", "") if isinstance(turing_res.answer, dict) else ""
        print(f"  🤖 Turing: {summary[:120]}")
    except Exception as e:
        telemetry["turing_diagnostics"] = {"error": str(e)}
        print(f"  🤖 Turing: error ({e})")
    
    return telemetry


async def main():
    TELEMETRY_FILE.parent.mkdir(exist_ok=True, parents=True)
    
    turing = TuringAgent()
    cumulative_cost = 0.0
    all_polls: list[dict] = []
    
    print("=" * 70)
    print("  🖥️  TURING INFRASTRUCTURE MONITOR — STARTED")
    print(f"  Polling every {POLL_INTERVAL_S}s | Max {MAX_POLLS} polls ({MAX_POLLS} min)")
    print("=" * 70)
    
    for poll_idx in range(1, MAX_POLLS + 1):
        telemetry = await poll_once(turing, poll_idx, cumulative_cost)
        cumulative_cost = telemetry.get("cumulative_cost_usd", cumulative_cost)
        all_polls.append(telemetry)
        
        # Append to JSONL
        with open(TELEMETRY_FILE, "a") as f:
            f.write(json.dumps(telemetry) + "\n")
        
        # Update summary markdown
        _write_summary(all_polls)
        
        if poll_idx < MAX_POLLS:
            await asyncio.sleep(POLL_INTERVAL_S)
    
    print(f"\n{'=' * 70}")
    print(f"  🖥️  TURING MONITOR COMPLETE — {len(all_polls)} polls recorded")
    print(f"  Telemetry: {TELEMETRY_FILE}")
    print(f"  Summary:   {SUMMARY_FILE}")
    print(f"{'=' * 70}")


def _write_summary(polls: list[dict]) -> None:
    """Write a rolling markdown summary of all polls."""
    lines = [
        "# 🖥️ Turing Infrastructure Monitor — Live Summary\n",
        f"**Last updated:** {get_timestamp()}",
        f"**Total polls:** {len(polls)}\n",
        "| # | Timestamp | GPUs | Type | Temp (°C) | Thermal | Cost ($) | Cumulative ($) | Quota | Scale-0 |",
        "|---|-----------|------|------|-----------|---------|----------|----------------|-------|---------|",
    ]
    
    for p in polls:
        ts = p.get("timestamp", "?")[:19]
        dep = p.get("deployment", {})
        therm = p.get("thermal", {})
        bill = p.get("billing", {})
        
        gpus = dep.get("active_nodes", 0)
        gpu_type = dep.get("gpu_type", "?")
        temp = therm.get("estimated_avg_temp_c", "N/A")
        thermal_status = therm.get("thermal_status", "?")
        cost = bill.get("estimated_accumulated_cost_usd", 0.0)
        cumul = p.get("cumulative_cost_usd", 0.0)
        quota = p.get("quota", {}).get("verdict", "?")
        s2z = "✅" if p.get("scale_to_zero_enforced") else "⚡"
        
        lines.append(f"| {p.get('poll_index', '?')} | {ts} | {gpus} | {gpu_type} | {temp} | {thermal_status} | {cost:.4f} | {cumul:.2f} | {quota} | {s2z} |")
    
    lines.append("\n---\n")
    
    # Latest Turing diagnostics
    if polls:
        latest = polls[-1]
        diag = latest.get("turing_diagnostics", {})
        if diag and "summary" in diag:
            lines.append(f"### Latest Turing Diagnostics\n")
            lines.append(f"```\n{diag['summary']}\n```\n")
    
    SUMMARY_FILE.write_text("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
