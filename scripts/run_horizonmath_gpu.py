#!/usr/bin/env python3
# Copyright (c) 2026 Xavier Callens / Socrate AI Lab
# Licensed under Apache 2.0 - see LICENSE file
"""
HorizonMath Top 10 GPU Execution Script — SymBrain v12
======================================================
Runs on NVIDIA H100 inside a Cloud Run Job.
Streams structured JSON progress to Cloud Logging.
Results written to GCS bucket for persistence.

Environment variables expected:
  - GEMINI_API_KEY       : Google Gemini API key
  - HF_TOKEN             : HuggingFace token for NuminaMath-7B
  - GCS_BUCKET           : GCS bucket (e.g. gs://symbrain-v12-results)
  - CLOUD_RUN_TASK_INDEX : Task index (0-9), one problem per task
  - CLOUD_RUN_TASK_COUNT : Total task count
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import datetime
import traceback
from pathlib import Path

import structlog
import torch
try:
    import pynvml  # nvidia-ml-py package
except ImportError:
    pynvml = None  # graceful fallback

# --- Setup structured logging to stdout (picked up by Cloud Logging) ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────
# GPU Probe
# ─────────────────────────────────────────────────────────────

def probe_gpu() -> dict:
    """Detect and report GPU configuration."""
    result = {"cuda_available": torch.cuda.is_available()}
    if torch.cuda.is_available() and pynvml:
        result["device_count"] = torch.cuda.device_count()
        result["devices"] = []
        try:
            pynvml.nvmlInit()
            for i in range(torch.cuda.device_count()):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                result["devices"].append({
                    "index": i,
                    "name": name if isinstance(name, str) else name.decode(),
                    "total_vram_gb": round(mem_info.total / 1e9, 2),
                    "free_vram_gb": round(mem_info.free / 1e9, 2),
                })
            pynvml.nvmlShutdown()
        except Exception as e:
            result["nvml_error"] = str(e)
    return result


def get_gpu_metrics() -> dict:
    """Snapshot current GPU utilization & memory."""
    if not torch.cuda.is_available() or not pynvml:
        return {"gpu_available": False}
    metrics = {"gpu_available": True, "devices": []}
    try:
        pynvml.nvmlInit()
        for i in range(torch.cuda.device_count()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            metrics["devices"].append({
                "index": i,
                "gpu_util_pct": util.gpu,
                "mem_util_pct": util.memory,
                "used_vram_gb": round(mem_info.used / 1e9, 2),
                "free_vram_gb": round(mem_info.free / 1e9, 2),
                "temperature_c": temp,
            })
        pynvml.nvmlShutdown()
    except Exception as e:
        metrics["nvml_error"] = str(e)
    return metrics


# ─────────────────────────────────────────────────────────────
# Problem Solver  (real GPU symbolic + numerical execution)
# ─────────────────────────────────────────────────────────────

async def solve_problem_on_gpu(problem: dict, task_idx: int) -> dict:
    """
    Execute the SymBrain v12 pipeline for a single HorizonMath problem on GPU.
    
    Pipeline:
      1. Galois (SymBrain v12) — conjecture generation via Lévy-MCTS on GPU
      2. Numerical verification — run problem's dedicated numerics script on CUDA tensors
      3. Euler — Lean 4 proof skeleton generation
      4. Pythagore — formal gap mapping
    """
    problem_id = problem["id"]
    prompt = problem.get("prompt", "")
    solvability = problem.get("solvability", 2)

    log.info("problem_start", task=task_idx, problem_id=problem_id,
             solvability=solvability, gpu_metrics=get_gpu_metrics())

    start_time = time.time()
    result = {
        "problem_id": problem_id,
        "solvability": solvability,
        "task_index": task_idx,
        "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # --- Step 1: GPU-accelerated numerical computation ---
    numerics_path = Path("/app") / f"scratch/HorizonMath/numerics/{problem_id}.py"
    # Fallback to bundled dataset copy
    if not numerics_path.exists():
        numerics_path = Path("/app") / f"numerics/{problem_id}.py"

    numeric_result = None
    if numerics_path.exists():
        log.info("numerics_run_start", problem_id=problem_id, script=str(numerics_path))
        try:
            import subprocess, sys
            proc = subprocess.run(
                [sys.executable, str(numerics_path)],
                capture_output=True, text=True, timeout=600,
                env={**os.environ, "CUDA_VISIBLE_DEVICES": "all", "PYTHONPATH": "/app"}
            )
            numeric_result = {
                "stdout": proc.stdout[-4000:] if proc.stdout else "",
                "returncode": proc.returncode,
                "status": "SUCCESS" if proc.returncode == 0 else "PARTIAL",
            }
            log.info("numerics_run_complete", problem_id=problem_id,
                     returncode=proc.returncode, output_len=len(proc.stdout))
        except subprocess.TimeoutExpired:
            numeric_result = {"status": "TIMEOUT", "message": "Numerics computation exceeded 600s"}
            log.warning("numerics_timeout", problem_id=problem_id)
        except Exception as exc:
            numeric_result = {"status": "ERROR", "message": str(exc)}
            log.error("numerics_error", problem_id=problem_id, error=str(exc))
    else:
        log.warning("numerics_not_found", problem_id=problem_id,
                    searched=str(numerics_path))
        numeric_result = {"status": "NOT_FOUND", "message": f"No numerics script for {problem_id}"}

    result["numeric_result"] = numeric_result

    # --- Step 2: SymBrain v12 Galois Agent (symbolic AI) ---
    log.info("galois_start", problem_id=problem_id)
    
    # Load v11 continuous learning context if available
    v11_context = ""
    try:
        monograph_path = Path("/app/docs/horizonmath_top10_monograph.md")
        if not monograph_path.exists():
            monograph_path = Path("/app/scratch/HorizonMath/docs/horizonmath_top10_monograph.md")
        if monograph_path.exists():
            v11_context = f"\n\nPrior SymBrain v11 Insights:\n{monograph_path.read_text()[-4000:]}"
    except Exception as e:
        log.warning("v11_context_load_failed", error=str(e))
        
    try:
        # Import inline to avoid circular issues at module load time
        from agents.galois.agent import GaloisAgent
        galois = GaloisAgent()
        
        symbrain_version = "v12_large" if solvability >= 3 else "v12_small"
        mcts_iterations = 2048 if symbrain_version == "v12_large" else 512
        
        query_prompt = (
            f"Solve this complex mathematical problem using SymBrain {symbrain_version} (GPU-accelerated, "
            f"MCTS depth={mcts_iterations}): {prompt}{v11_context}"
        )
        
        galois_res = await galois.run(query_prompt, symbrain_version=symbrain_version, mcts_iterations=mcts_iterations)
        result["galois"] = {
            "conjectures": str(galois_res.answer)[:2000],
            "confidence": galois_res.confidence,
            "cost_usd": galois_res.cost_usd,
        }
        log.info("galois_complete", problem_id=problem_id, confidence=galois_res.confidence)
    except Exception as exc:
        result["galois"] = {"error": str(exc), "traceback": traceback.format_exc()[-1000:]}
        log.error("galois_error", problem_id=problem_id, error=str(exc))

    # --- Step 3: Euler Lean 4 Verification ---
    log.info("euler_start", problem_id=problem_id)
    try:
        from agents.euler.agent import EulerAgent
        euler = EulerAgent()
        euler_res = await euler.run(
            f"Verify the following mathematical solution formally: {result.get('galois', {}).get('conjectures', '')}. Original problem: {prompt}"
        )
        result["euler"] = {
            "verdict": str(euler_res.answer)[:2000],
            "confidence": euler_res.confidence,
            "cost_usd": euler_res.cost_usd,
        }
        log.info("euler_complete", problem_id=problem_id,
                 confidence=euler_res.confidence)
    except Exception as exc:
        result["euler"] = {"error": str(exc)}
        log.error("euler_error", problem_id=problem_id, error=str(exc))

    # --- Step 4: Pythagore Formalization ---
    log.info("pythagore_start", problem_id=problem_id)
    try:
        from agents.pythagore.agent import PythagoreAgent
        pythagore = PythagoreAgent()
        pyth_res = await pythagore.run(
            f"Generate a formal Lean 4 proof draft for the Euler-verified solution: {result.get('euler', {}).get('verdict', '')}. Problem: {prompt}"
        )
        result["pythagore"] = {
            "draft": str(pyth_res.answer)[:3000],
            "cost_usd": pyth_res.cost_usd,
        }
        log.info("pythagore_complete", problem_id=problem_id)
    except Exception as exc:
        result["pythagore"] = {"error": str(exc)}
        log.error("pythagore_error", problem_id=problem_id, error=str(exc))

    elapsed = time.time() - start_time
    result["elapsed_seconds"] = round(elapsed, 2)
    result["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result["final_gpu_metrics"] = get_gpu_metrics()

    log.info("problem_complete", problem_id=problem_id,
             elapsed_s=result["elapsed_seconds"],
             numerics_status=numeric_result.get("status", "unknown"))

    return result


async def upload_to_gcs(result: dict, filename: str) -> None:
    """Upload result JSON to GCS bucket if configured."""
    bucket = os.environ.get("GCS_BUCKET", "")
    if not bucket:
        return
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket_name = bucket.replace("gs://", "").rstrip("/")
        blob_name = f"horizonmath-v12/{filename}"
        bucket_obj = client.bucket(bucket_name)
        blob = bucket_obj.blob(blob_name)
        blob.upload_from_string(
            json.dumps(result, indent=2, default=str),
            content_type="application/json"
        )
        log.info("gcs_upload_complete", bucket=bucket_name, blob=blob_name)
    except Exception as exc:
        log.warning("gcs_upload_failed", error=str(exc))


async def main() -> None:
    """Main entry point for the Cloud Run GPU Job."""
    # Cloud Run sets CLOUD_RUN_TASK_INDEX for parallel tasks
    task_index = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    task_count = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "10"))

    # GPU probe
    gpu_info = probe_gpu()
    log.info("gpu_probe", **gpu_info, task_index=task_index)

    if not gpu_info["cuda_available"]:
        log.warning("no_gpu_detected", message="Running in CPU fallback mode — production should use H100")

    # Load HorizonMath dataset
    data_candidates = [
        Path("/app/scratch/HorizonMath/data/problems_full.json"),
        Path("/app/docs/horizonmath_top10_data.json"),
        Path("/tmp/problems_full.json"),
    ]
    data_path = None
    for candidate in data_candidates:
        if candidate.exists():
            data_path = candidate
            break

    if data_path is None:
        log.error("data_not_found", searched=[str(p) for p in data_candidates])
        # Create minimal embedded dataset for the 10 HorizonMath problems
        problems = _get_embedded_horizonmath_top10()
        log.info("using_embedded_dataset", problem_count=len(problems))
    else:
        with open(data_path) as f:
            all_problems = json.load(f)
        problems = [p for p in all_problems if p.get("solvability", 0) >= 2][:10]
        log.info("dataset_loaded", path=str(data_path), problem_count=len(problems))

    # This task handles one specific problem (Cloud Run parallel tasks)
    if task_index >= len(problems):
        log.info("no_work", task_index=task_index, total_problems=len(problems))
        return

    problem = problems[task_index]
    log.info("task_assigned", task_index=task_index, problem_id=problem["id"])

    # Execute pipeline on GPU
    result = await solve_problem_on_gpu(problem, task_index)

    # Write result locally
    out_dir = Path("/tmp/results")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"problem_{task_index:02d}_{problem['id']}.json"
    out_file.write_text(json.dumps(result, indent=2, default=str))
    log.info("result_saved_local", path=str(out_file))

    # Upload to GCS
    await upload_to_gcs(result, f"problem_{task_index:02d}_{problem['id']}.json")

    # Summary to stdout for monitoring
    print(json.dumps({
        "event": "TASK_COMPLETE",
        "task_index": task_index,
        "problem_id": problem["id"],
        "solvability": problem.get("solvability"),
        "elapsed_seconds": result["elapsed_seconds"],
        "galois_confidence": result.get("galois", {}).get("confidence"),
        "euler_confidence": result.get("euler", {}).get("confidence"),
        "numeric_status": result.get("numeric_result", {}).get("status"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }, indent=2))


def _get_embedded_horizonmath_top10() -> list[dict]:
    """Embedded Top 10 HorizonMath problems (Class 2 & 3) as fallback dataset."""
    return [
        {"id": "w5_watson_integral", "solvability": 3,
         "prompt": "Find a closed-form expression for Watson's triple integral W5 = (1/π³)∫₀^π∫₀^π∫₀^π dx dy dz / (5 - cos x - cos y - cos z - cos(x+y+z))."},
        {"id": "w6_watson_integral", "solvability": 3,
         "prompt": "Determine Watson's triple integral W6 = (1/π³)∫₀^π∫₀^π∫₀^π dx dy dz / (6 - cos x - cos y - cos z - cos(x+y) - cos(y+z) - cos(x+z))."},
        {"id": "bessel_moment_c5_0", "solvability": 3,
         "prompt": "Compute the 5th-order Bessel moment C(5,0) = ∫₀^∞ t [J₀(t)]⁵ dt in closed form using Gamma functions and hypergeometric series."},
        {"id": "bessel_moment_c5_1", "solvability": 3,
         "prompt": "Compute the Bessel moment C(5,1) = ∫₀^∞ t² [J₀(t)]⁵ J₁(t) dt in closed form."},
        {"id": "box_integral_b5_neg2", "solvability": 3,
         "prompt": "Evaluate the 5-dimensional box integral B(5,-2) = ∫₀¹···∫₀¹ |r|^(-2) dx₁···dx₅ where |r|² = x₁² + ··· + x₅² in closed form."},
        {"id": "feigenbaum_delta", "solvability": 3,
         "prompt": "Prove or disprove that the Feigenbaum constant δ ≈ 4.66920160910299 is transcendental. Provide a formal argument or derive new bounds."},
        {"id": "anderson_lyapunov_exponent", "solvability": 3,
         "prompt": "Compute the Lyapunov exponent γ(λ) for the Anderson model H = Δ + λV on Z^d for d ≥ 3 in closed form at the mobility edge."},
        {"id": "autocorr_signed_upper", "solvability": 2,
         "prompt": "Determine the exact supremum of |ρ(k)| over all stationary processes with given spectral density constraints — autocorrelation upper bound problem."},
        {"id": "elliptic_k_moment_4", "solvability": 2,
         "prompt": "Compute ∫₀^1 K(k)⁴ dk in closed form, where K(k) is the complete elliptic integral of the first kind."},
        {"id": "calabi_yau_c5", "solvability": 2,
         "prompt": "Compute the Calabi-Yau constant C₅ = ∫₀^∞ (∏_{j=1}^{5} J₀(jt)) t dt in closed form using hypergeometric techniques."},
    ]


if __name__ == "__main__":
    asyncio.run(main())
