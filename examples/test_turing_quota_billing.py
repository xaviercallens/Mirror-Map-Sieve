#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""Verification script: Turing Agent GCP Quota & Dual-H100/L4 Pool Billing Estimator.

Validates the Turing Agent's ability to:
1. Estimate costs for dual-H100 and L4 Serverless Pools under 160GB VRAM / 250-node MCTS.
2. Monitor GCP infrastructure costs and verify quota availability.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.turing.agent import TuringAgent


async def run_turing_validation() -> None:
    print("=" * 90)
    print("🏛️  SocrateAI Agora — Turing Agent GCP Quota & Infrastructure Billing Verification")
    print("=" * 90)

    # 1. Activate Turing Agent
    turing = TuringAgent()
    print("[+] Turing Computational Optimizer Swarm Active ✓")

    # 2. CASE A: Validating dual-H100 Serverless Pool under 160GB VRAM / 250-node MCTS (Compliant Quota)
    print(f"\n[▶] Test CASE A: Querying dual-H100 Pool cost under 160GB VRAM & 250-node MCTS...")
    
    pool_cfg_h100 = {
        "gpu_type": "dual-H100",
        "vram_gb": 160.0,
        "mcts_nodes": 250.0,
        "base_duration_seconds": 0.12,
        "vcpu_request": 32,
    }
    
    # Active limits allow 4 H100s, 64 vCPUs
    quota_compliant = {
        "h100_limit": 4,
        "l4_limit": 8,
        "vcpu_limit": 64,
    }

    res_a = await turing.run(
        "Estimate cost for dual-H100 Serverless Pool under 160GB VRAM and 250-node MCTS",
        pool_config=pool_cfg_h100,
        quota_limits=quota_compliant,
    )
    
    report_a = res_a.answer.get("pool_report", {})
    print("-" * 90)
    print(f"  GPU Cluster Configured:    {report_a.get('gpu_type')}")
    print(f"  VRAM Allocation:           {report_a.get('vram_allocated_gb')} GB")
    print(f"  MCTS Tree Nodes Depth:     {report_a.get('mcts_nodes')} nodes")
    print(f"  Active GPUs Needed:        {report_a.get('active_gpus_requested')} cards")
    print(f"  vCPU Allocation Check:     {report_a.get('vcpu_requested')} cores")
    print(f"  Estimated Hourly Rate:     ${report_a.get('estimated_hourly_rate_usd'):.2f}/hr")
    print(f"  Latency per Query:         {report_a.get('estimated_query_latency_ms')} ms")
    print(f"  Hourly Query Throughput:   {report_a.get('estimated_query_throughput_per_hour')} queries")
    print(f"  Cost per Million Queries:  ${report_a.get('estimated_cost_per_million_queries_usd'):.2f}")
    print(f"  Quota Compliance Verdict:  {report_a.get('quota_status')} [STATUS: {report_a.get('verdict')}]")
    print(f"  Warnings:                  {report_a.get('warnings')}")
    print(f"  Recommendations:           {report_a.get('recommendations')}")
    print("-" * 90)

    assert report_a.get("quota_status") == "QUOTA_AVAILABLE"
    assert report_a.get("verdict") == "COMPLIANT"
    assert report_a.get("estimated_hourly_rate_usd") == 7.34
    print("    ✓ CASE A: PASS. Cost estimation and compliant quota verification correct.")

    # 3. CASE B: Validating L4 Serverless Pool (160GB VRAM requires ceil(160/24) = 7 active L4 GPUs)
    print(f"\n[▶] Test CASE B: Querying L4 Serverless Pool (160GB VRAM, 250-node MCTS)...")
    pool_cfg_l4 = {
        "gpu_type": "L4-Pool",
        "vram_gb": 160.0,
        "mcts_nodes": 250.0,
        "base_duration_seconds": 0.12,
        "vcpu_request": 32,
    }

    res_b = await turing.run(
        "Estimate cost for L4-Pool Serverless Pool under 160GB VRAM and 250-node MCTS",
        pool_config=pool_cfg_l4,
        quota_limits=quota_compliant,
    )
    
    report_b = res_b.answer.get("pool_report", {})
    print("-" * 90)
    print(f"  GPU Cluster Configured:    {report_b.get('gpu_type')}")
    print(f"  VRAM Allocation:           {report_b.get('vram_allocated_gb')} GB")
    print(f"  Active GPUs (L4) Needed:   {report_b.get('active_gpus_requested')} cards (VRAM check: 7 * 24GB = 168GB)")
    print(f"  Estimated Hourly Rate:     ${report_b.get('estimated_hourly_rate_usd'):.2f}/hr (7 * $0.70/L4)")
    print(f"  Quota Compliance Verdict:  {report_b.get('quota_status')} [STATUS: {report_b.get('verdict')}]")
    print("-" * 90)

    assert report_b.get("active_gpus_requested") == 7
    assert report_b.get("estimated_hourly_rate_usd") == 4.90
    print("    ✓ CASE B: PASS. L4 VRAM scaling ceiling computed accurately.")

    # 4. CASE C: Triggering Quota Violations (Non-Compliant Quota)
    print(f"\n[▶] Test CASE C: Triggering Quota Exceeded violation warnings...")
    quota_limited = {
        "h100_limit": 1,   # Requires 2
        "l4_limit": 4,     # Requires 7
        "vcpu_limit": 16,  # Requires 32
    }

    res_c = await turing.run(
        "Estimate dual-H100 pool with restricted quotas",
        pool_config=pool_cfg_h100,
        quota_limits=quota_limited,
    )
    
    report_c = res_c.answer.get("pool_report", {})
    print("-" * 90)
    print(f"  Quota Compliance Verdict:  {report_c.get('quota_status')} [STATUS: {report_c.get('verdict')}]")
    print(f"  Warnings:                  {report_c.get('warnings')}")
    print(f"  Recommendations:           {report_c.get('recommendations')}")
    print("-" * 90)

    assert report_c.get("quota_status") == "QUOTA_EXCEEDED"
    assert report_c.get("verdict") == "NON_COMPLIANT"
    assert len(report_c.get("warnings")) == 2  # H100 and vCPU violated
    print("    ✓ CASE C: PASS. GCP service limit violation caught and reported properly.")

    print("\n" + "=" * 90)
    print("🏛️  TURING VALIDATION SUCCESSFUL — ALL TESTS PASSED ✓")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(run_turing_validation())
