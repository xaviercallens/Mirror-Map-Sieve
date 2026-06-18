"""Sorry Completer — 10-Hypothesis Autoresearch Proof Engine.

Orchestrates LeanBERT, DeepSeek-Prover-V2-7B, and Gemini Deep-Think to
generate 10 candidate proofs per sorry, verify via Lean 4 kernel, and
select the best 3.

Architecture:
    sorry_scanner → 10 hypotheses → lean 4 verify → rank → select best 3
    
Cost optimization:
    - LeanBERT: CPU-only Cloud Run (negligible cost)
    - DeepSeek-Prover-V2-7B: T4 GPU with 4-bit quantization (~$0.35/hr, scale-to-zero)
    - Gemini: API calls only when needed ($0.05/sorry)
    - Premium 671B escalation only for extreme-difficulty sorrys
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from agents.hilbert.tools.sorry_scanner import SorryTarget, AxiomTarget, scan_directory

logger = structlog.get_logger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
MAX_HYPOTHESES     = 10      # hypotheses per sorry
MAX_RATCHET_ITERS  = 3       # autoresearch retry loops per sorry
LEAN_BUILD_TIMEOUT = 120     # seconds for `lake build`
LEANBERT_HYPOTHESES    = 3   # from GAN generator
DEEPSEEK_HYPOTHESES    = 4   # from DeepSeek-Prover-V2-7B
GEMINI_HYPOTHESES      = 3   # from Gemini Deep-Think

DEEPSEEK_ENDPOINT  = os.environ.get(
    "DEEPSEEK_PROVER_ENDPOINT",
    # Default to Cloud Run service (requires IAM identity token for auth)
    # Falls back gracefully if service is unreachable
    "https://deepseek-prover-v2-291479295008.us-central1.run.app/prove",
)
DEEPSEEK_API_KEY   = os.environ.get("DEEPSEEK_API_KEY", "")  # For 671B premium escalation
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")


@dataclass
class Hypothesis:
    """A candidate proof for a sorry gap."""
    id: int
    source: str               # "leanbert", "deepseek-7b", "deepseek-671b", "gemini"
    proof_text: str            # the Lean 4 tactic proof body
    compile_success: bool = False
    error_message: str = ""
    wall_time_ms: float = 0.0
    leanbert_score: float = 0.0    # GAN critic probability [0, 1]
    proof_length: int = 0          # shorter = better


@dataclass
class CompletionResult:
    """Result of attempting to close a single sorry gap."""
    target: SorryTarget
    hypotheses: list[Hypothesis]
    best_3: list[Hypothesis]
    ratchet_iterations: int
    status: str                # "completed", "partial", "failed"
    applied_proof: str = ""    # the proof that was applied (if any)


@dataclass
class SweepReport:
    """Full report of a sorry-completion sweep."""
    results: list[CompletionResult]
    sorrys_closed: int
    sorrys_failed: int
    total_hypotheses_generated: int
    total_hypotheses_compiled: int
    total_cost_usd: float
    elapsed_s: float

# ─── LeanBERT GCS Model Download ──────────────────────────────────────────────

GCS_LEANBERT_BUCKET = "gs://agora-autoresearch-001-outputs/models/leanbert"
LOCAL_CACHE_DIR = Path("/tmp/leanbert")


def _download_leanbert_from_gcs() -> Path | None:
    """Download LeanBERT models from GCS to local cache.
    
    Used in Cloud Run environments where the local dev path doesn't exist.
    Downloads to /tmp/leanbert/ and caches for the container lifetime.
    
    Returns:
        Path to the local cache directory if successful, None otherwise.
    """
    if LOCAL_CACHE_DIR.exists() and (LOCAL_CACHE_DIR / "best_generator.pt").exists():
        logger.info("leanbert_gcs_cache_hit", path=str(LOCAL_CACHE_DIR))
        return LOCAL_CACHE_DIR

    try:
        LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for fname in ["best_generator.pt", "best_critic.pt", "lean4_vocab.json"]:
            gcs_uri = f"{GCS_LEANBERT_BUCKET}/{fname}"
            local_path = LOCAL_CACHE_DIR / fname
            result = subprocess.run(
                ["gsutil", "cp", gcs_uri, str(local_path)],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                logger.warning("leanbert_gcs_download_failed",
                               file=fname, error=result.stderr[:200])
                return None
            logger.info("leanbert_gcs_downloaded", file=fname,
                        size_mb=round(local_path.stat().st_size / 1e6, 1))

        # Also download lean_corpus.py and train.py for model class imports
        for py_file in ["lean_corpus.py", "train.py"]:
            gcs_py = f"gs://agora-autoresearch-001-outputs/models/leanbert/{py_file}"
            local_py = LOCAL_CACHE_DIR / py_file
            subprocess.run(
                ["gsutil", "cp", gcs_py, str(local_py)],
                capture_output=True, text=True, timeout=30,
            )
        
        return LOCAL_CACHE_DIR
    except Exception as e:
        logger.warning("leanbert_gcs_download_error", error=str(e))
        return None


# ─── LeanBERT Hypothesis Generator ───────────────────────────────────────────

def _generate_leanbert_hypotheses(
    target: SorryTarget, n: int = LEANBERT_HYPOTHESES
) -> list[Hypothesis]:
    """Generate tactic hypotheses from LeanBERT GAN latent space.
    
    Uses the trained generator to sample tactic sequences, then scores
    each with the NeuroSymbolicCritic to produce a probability estimate.
    
    Model resolution order:
      1. Local path (dev machine): /Users/xcallens/xdev/SocrateAI-Lean-Verification/autoresearch/data/
      2. GCS bucket (Cloud Run):   gs://agora-autoresearch-001-outputs/models/leanbert/
      3. Template fallback:         analysis-aware tactic templates
    """
    try:
        import torch
        import sys
        # Add autoresearch to path
        autoresearch_dir = Path("/Users/xcallens/xdev/SocrateAI-Lean-Verification/autoresearch")
        if str(autoresearch_dir) not in sys.path:
            sys.path.insert(0, str(autoresearch_dir))
        
        from lean_corpus import VOCAB_SIZE, MAX_SEQ_LEN, build_vocab

        # Load models — try local first, then GCS
        gen_path    = autoresearch_dir / "data" / "best_generator.pt"
        critic_path = autoresearch_dir / "data" / "best_critic.pt"
        vocab_path  = autoresearch_dir / "data" / "lean4_vocab.json"

        if not gen_path.exists() or not vocab_path.exists():
            # Attempt GCS download (for Cloud Run / remote environments)
            gcs_model_dir = _download_leanbert_from_gcs()
            if gcs_model_dir:
                gen_path    = gcs_model_dir / "best_generator.pt"
                critic_path = gcs_model_dir / "best_critic.pt"
                vocab_path  = gcs_model_dir / "lean4_vocab.json"
            
            # If still not found after GCS attempt, use template fallback
            if not gen_path.exists() or not vocab_path.exists():
                logger.warning("leanbert_models_not_found", msg="Using tactic template fallback")
                return _leanbert_template_fallback(target, n)

        # Load vocab (int → tactic)
        with open(vocab_path) as f:
            vocab = json.load(f)
        inv_vocab = {v: k for k, v in vocab.items()}

        # Import model classes
        from train import LeanGenerator, NeuroSymbolicCritic

        device = "cpu"
        gen = LeanGenerator().to(device)
        gen.load_state_dict(torch.load(gen_path, map_location=device, weights_only=False))
        gen.eval()

        critic = NeuroSymbolicCritic().to(device)
        critic.load_state_dict(torch.load(critic_path, map_location=device, weights_only=False))
        critic.eval()

        hypotheses: list[Hypothesis] = []
        for i in range(n * 3):  # oversample and rank by critic
            z = torch.randn(1, 128).to(device)
            with torch.no_grad():
                logits = gen(z)
                tokens = torch.argmax(logits, dim=-1)[0].tolist()
                # Decode tokens to tactic text
                tactic_parts = []
                for t in tokens:
                    part = inv_vocab.get(t, "")
                    if part and not part.startswith("__pad_"):
                        tactic_parts.append(part)
                    if part == "<EOS>":
                        break

                # Score with critic
                token_tensor = torch.argmax(logits, dim=-1)
                score = critic(token_tensor).item()

            proof_text = ' '.join(tactic_parts).strip()
            if proof_text:
                hypotheses.append(Hypothesis(
                    id=len(hypotheses),
                    source="leanbert",
                    proof_text=proof_text,
                    leanbert_score=score,
                    proof_length=len(proof_text),
                ))

        # Rank by critic score and return top N
        hypotheses.sort(key=lambda h: -h.leanbert_score)
        return hypotheses[:n]

    except Exception as e:
        logger.warning("leanbert_generation_failed", error=str(e))
        return _leanbert_template_fallback(target, n)


def _leanbert_template_fallback(target: SorryTarget, n: int) -> list[Hypothesis]:
    """Template-based fallback when GAN models are not available.
    
    Includes analysis-aware templates for HasDerivAt / constant function theorems.
    """
    # Standard tactic templates
    base_templates = [
        "simp",
        "ring",
        "norm_num",
        "omega",
        "decide",
        "linarith",
        "positivity",
        "exact?",
        "aesop",
        "trivial",
        "rfl",
        "constructor <;> simp",
    ]
    
    # Analysis-specific templates (for HasDerivAt / constant function theorems)
    analysis_templates = [
        "intro t₁ t₂\n  have h := fun t => (h_dMdt_zero t).hasDerivAt\n  exact is_const_of_deriv_eq_zero _ (fun t => (h_dMdt_zero t).deriv) t₁ t₂",
        "intro t₁ t₂\n  exact eq_of_has_deriv_at_eq_zero (fun t => h_dMdt_zero t) t₁ t₂",
        "intro t₁ t₂\n  have : ∀ t, HasDerivAt (totalMass cq μ) 0 t := h_dMdt_zero\n  exact Eq.symm (IsLocalMin.eq_of_deriv_eq_zero _ _ _ _)",
        "intro t₁ t₂\n  simp only [totalMass]\n  congr 1\n  ext x\n  have hsf := h_source_free x\n  simp [hsf]",
        "intro t₁ t₂\n  have key : ∀ t, HasDerivAt (totalEnergy es μ) 0 t := by\n    intro t; rw [h_isolated t]; simp; exact h_deriv t\n  exact is_const_of_deriv_eq_zero _ (fun t => (key t).deriv) t₁ t₂",
        "intro t₁ t₂\n  have := h_deriv t₁\n  have := h_deriv t₂\n  have := h_isolated t₁\n  have := h_isolated t₂\n  simp_all",
        "intro h; exact h",
        "push_neg; intro h; linarith",
    ]
    
    # Combine and select based on goal signature
    sig = target.goal_signature.lower()
    if any(kw in sig for kw in ["hasderivat", "totalenergy", "totalmass", "conservation"]):
        templates = analysis_templates + base_templates[:3]
    else:
        templates = base_templates + analysis_templates[:2]
    
    return [
        Hypothesis(id=i, source="leanbert-template", proof_text=t, leanbert_score=0.3)
        for i, t in enumerate(templates[:n])
    ]


# ─── DeepSeek-Prover-V2 Hypothesis Generator ─────────────────────────────────

def _generate_deepseek_hypotheses(
    target: SorryTarget,
    n: int = DEEPSEEK_HYPOTHESES,
    use_premium: bool = False,
) -> list[Hypothesis]:
    """Generate proof hypotheses using DeepSeek-Prover-V2.
    
    Primary: self-hosted 7B on T4 (4-bit quantized) via Vertex AI endpoint.
    Premium escalation: DeepSeek API with 671B for extreme-difficulty sorrys.
    """
    import urllib.request
    import urllib.error

    prompt = f"""Complete the following Lean 4 proof. Replace the `sorry` with a valid tactic proof.

Context (imports and surrounding code):
```lean4
{target.context_window}
```

The theorem to prove:
```lean4
{target.goal_signature}
```

Provide ONLY the tactic proof body (the part that replaces `sorry`). 
Do not include the theorem signature. Use standard Lean 4 / Mathlib4 tactics.
"""
    hypotheses: list[Hypothesis] = []

    if use_premium and DEEPSEEK_API_KEY:
        # ── 671B API for hard problems ────────────────────────────────────
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        }
        for i in range(n):
            body = json.dumps({
                "model": "deepseek-prover-v2",
                "messages": [
                    {"role": "system", "content": "You are DeepSeek-Prover-V2, an expert Lean 4 theorem prover. Output ONLY valid Lean 4 tactic proofs."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6,
                "max_tokens": 1024,
            }).encode()
            try:
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                proof = result["choices"][0]["message"]["content"].strip()
                proof = _extract_lean_code(proof)
                hypotheses.append(Hypothesis(
                    id=len(hypotheses), source="deepseek-671b",
                    proof_text=proof, proof_length=len(proof),
                ))
            except Exception as e:
                logger.warning("deepseek_671b_failed", error=str(e), attempt=i)
    else:
        # ── Self-hosted 7B on T4 ─────────────────────────────────────────
        if not DEEPSEEK_ENDPOINT.startswith("http"):
            logger.info("deepseek_7b_skipped", reason="endpoint not configured")
            return hypotheses[:n]
        for i in range(n):
            body = json.dumps({
                "goal_state": target.goal_signature,
                "context": target.context_window,
                "n_candidates": 1,
                "temperature": 0.6,
            }).encode()
            try:
                import ssl, subprocess
                _ssl_ctx = ssl.create_default_context()
                _ssl_ctx.check_hostname = False
                _ssl_ctx.verify_mode = ssl.CERT_NONE
                # Get IAM identity token for Cloud Run auth
                try:
                    id_token = subprocess.check_output(
                        ["/Users/xcallens/google-cloud-sdk/bin/gcloud", "auth", "print-identity-token"],
                        timeout=5
                    ).decode().strip()
                except Exception:
                    id_token = ""
                _headers = {"Content-Type": "application/json"}
                if id_token:
                    _headers["Authorization"] = f"Bearer {id_token}"
                req = urllib.request.Request(
                    DEEPSEEK_ENDPOINT,
                    data=body,
                    headers=_headers,
                )
                with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
                    result = json.loads(resp.read())
                for cand in result.get("candidates", []):
                    proof = cand.get("proof", "").strip()
                    if proof:
                        hypotheses.append(Hypothesis(
                            id=len(hypotheses), source="deepseek-7b",
                            proof_text=proof,
                            leanbert_score=cand.get("score", 0.0),
                            proof_length=len(proof),
                        ))
            except Exception as e:
                logger.warning("deepseek_7b_failed", error=str(e), attempt=i)

    return hypotheses[:n]


# ─── Gemini Deep-Think Hypothesis Generator ───────────────────────────────────

def _generate_gemini_hypotheses(
    target: SorryTarget, n: int = GEMINI_HYPOTHESES
) -> list[Hypothesis]:
    """Generate proof hypotheses using Gemini 3.1 Pro Deep-Think."""
    import urllib.request

    if not GEMINI_API_KEY:
        logger.warning("gemini_api_key_missing")
        return []

    # Truncate context to avoid MAX_TOKENS on output
    ctx_window = target.context_window[:2000] if len(target.context_window) > 2000 else target.context_window
    prompt = (
        "You are an expert Lean 4 / Mathlib4 theorem prover.\n"
        "Complete the `sorry` in the theorem below with a valid tactic proof.\n\n"
        f"File: {target.file}\n"
        f"Namespace: {target.namespace}\n"
        f"Imports: {', '.join(target.imports[:5])}\n\n"
        "Surrounding context:\n```lean4\n"
        f"{ctx_window}\n"
        "```\n\n"
        "Theorem to prove:\n```lean4\n"
        f"{target.goal_signature}\n"
        "```\n\n"
        "IMPORTANT RULES:\n"
        "- NEVER use `sorry`, `admit`, or `native_decide` — these are REJECTED\n"
        "- Use available hypotheses (h_dMdt_zero, h_source_free, h_isolated, h_deriv, etc.)\n"
        "- For constant-function theorems (∀ t₁ t₂, f t₁ = f t₂), start with `intro t₁ t₂`\n"
        "- Use Mathlib4 lemmas: `is_const_of_deriv_eq_zero`, `eq_of_has_deriv_at_eq_zero`\n"
        "- For HasDerivAt goals, check if hypotheses directly give the result\n"
        "- For inequality goals, try `linarith` with hypotheses\n"
        "- For unfolding definitions, try `unfold <defname>` then `linarith` or `simp`\n"
        "- Keep proofs SHORT (1-5 lines of tactics)\n\n"
        f"Provide {n} DIFFERENT candidate tactic proofs.\n"
        "Format each as: PROOF: <tactic proof>\n"
        "Output ONLY the PROOF: lines, nothing else.\n"
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
        f"?key={GEMINI_API_KEY}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 8192},
    }).encode()

    hypotheses: list[Hypothesis] = []
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            result = json.loads(resp.read())

        # Robust extraction — handle missing keys and safety-blocked responses
        candidates = result.get("candidates", [])
        if not candidates:
            logger.warning("gemini_no_candidates", result_keys=list(result.keys()))
            return hypotheses

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            logger.warning("gemini_empty_parts", finish_reason=finish_reason)
            return hypotheses

        text = parts[0].get("text", "")
        if not text:
            return hypotheses

        # Extract PROOF: blocks
        proofs = re.findall(r'PROOF:\s*(.+?)(?=PROOF:|$)', text, re.DOTALL)
        if not proofs:
            proofs = re.findall(r'```(?:lean4?)\s*\n(.*?)```', text, re.DOTALL)
        if not proofs:
            proofs = [_extract_lean_code(text)]

        for i, proof in enumerate(proofs[:n]):
            proof = proof.strip()
            if proof:
                hypotheses.append(Hypothesis(
                    id=i, source="gemini-deep-think",
                    proof_text=proof, proof_length=len(proof),
                ))
    except Exception as e:
        logger.warning("gemini_generation_failed", error=str(e))

    return hypotheses


# ─── Lean 4 Kernel Verification ───────────────────────────────────────────────

def _verify_hypothesis(
    target: SorryTarget, hypothesis: Hypothesis, project_root: str
) -> Hypothesis:
    """Substitute hypothesis into the .lean file and run `lake build`.
    
    Returns the hypothesis with compile_success and error_message updated.
    """
    filepath = Path(target.file)
    if not filepath.exists():
        hypothesis.error_message = f"File not found: {filepath}"
        return hypothesis

    original = filepath.read_text()
    lines = original.split('\n')

    # Replace the sorry line with the hypothesis
    sorry_line_idx = target.line - 1
    if sorry_line_idx < len(lines):
        indent = len(lines[sorry_line_idx]) - len(lines[sorry_line_idx].lstrip())
        indented_proof = '\n'.join(
            ' ' * indent + line if line.strip() else line
            for line in hypothesis.proof_text.split('\n')
        )
        lines[sorry_line_idx] = indented_proof
    modified = '\n'.join(lines)

    # Write modified file
    filepath.write_text(modified)
    t0 = time.monotonic()

    try:
        # Use `lake env lean <file>` for single-file verification
        result = subprocess.run(
            [os.path.expanduser("~/.elan/bin/lake"), "env", "lean", str(filepath)],
            cwd=project_root,
            capture_output=True, text=True,
            timeout=LEAN_BUILD_TIMEOUT,
        )
        hypothesis.wall_time_ms = (time.monotonic() - t0) * 1000
        output = result.stdout + result.stderr
        
        # Reject proofs that are trivially invalid (sorry/admit are no-ops)
        proof_stripped = hypothesis.proof_text.strip().lower()
        if proof_stripped in ('sorry', 'admit', 'native_decide', 'exact?'):
            hypothesis.error_message = f"Proof is trivially {proof_stripped}"
            return hypothesis
        # Also reject multi-line proofs where the effective tactic is sorry/admit
        effective_tactics = [l.strip().lower() for l in hypothesis.proof_text.strip().split('\n') if l.strip()]
        if effective_tactics and effective_tactics[-1] in ('sorry', 'admit'):
            hypothesis.error_message = "Proof ends with sorry/admit"
            return hypothesis

        
        # Check for errors specifically on our target theorem line
        # (other sorry warnings elsewhere in the file are acceptable)
        has_target_error = False
        for line in output.strip().split('\n'):
            if 'error:' in line.lower():
                # Check if this error is on our theorem's line range
                # Accept errors from OTHER theorems in the same file
                if f':{target.line}:' in line or 'unsolved goals' in line:
                    has_target_error = True
                    break
                # Also check nearby lines (proof might span multiple lines)
                try:
                    err_line = int(line.split(':')[1])
                    if abs(err_line - target.line) < 10:
                        has_target_error = True
                        break
                except (ValueError, IndexError):
                    has_target_error = True
                    break
        
        if not has_target_error:
            hypothesis.compile_success = True
            logger.info("hypothesis_compiled", theorem=target.theorem_name, source=hypothesis.source)
        else:
            hypothesis.error_message = output[-500:]
    except subprocess.TimeoutExpired:
        hypothesis.wall_time_ms = LEAN_BUILD_TIMEOUT * 1000
        hypothesis.error_message = "Lean build timed out"
    except Exception as e:
        hypothesis.error_message = str(e)
    finally:
        # Restore original
        filepath.write_text(original)

    return hypothesis


# ─── Scoring & Ranking ────────────────────────────────────────────────────────

def _score_hypothesis(h: Hypothesis) -> float:
    """Score a compiled hypothesis. Higher = better.
    
    Based on LeanBERT GAN latent-space critic probability,
    proof compactness, and source reliability.
    """
    if not h.compile_success:
        return -1.0

    source_bonus = {
        "deepseek-671b": 0.15,
        "deepseek-7b": 0.10,
        "gemini-deep-think": 0.08,
        "leanbert": 0.05,
        "leanbert-template": 0.02,
    }.get(h.source, 0.0)

    # Shorter proofs are preferred (less chance of being trivially wrong)
    length_penalty = max(0, 1.0 - h.proof_length / 500)

    return h.leanbert_score + source_bonus + length_penalty * 0.3


def _rank_and_select(hypotheses: list[Hypothesis], top_n: int = 3) -> list[Hypothesis]:
    """Rank compiled hypotheses and return the best N."""
    compiled = [h for h in hypotheses if h.compile_success]
    compiled.sort(key=_score_hypothesis, reverse=True)
    return compiled[:top_n]


# ─── Main Orchestrator ────────────────────────────────────────────────────────

def complete_sorry(
    target: SorryTarget,
    project_root: str,
    use_premium_for_extreme: bool = True,
) -> CompletionResult:
    """Attempt to close a single sorry gap using the 10-hypothesis pipeline.
    
    Implements the autoresearch ratchet loop: generate → verify → reflect → retry.
    """
    log = logger.bind(theorem=target.theorem_name, difficulty=target.difficulty)
    log.info("completing_sorry", file=target.file, line=target.line)

    all_hypotheses: list[Hypothesis] = []
    ratchet_iter = 0

    for ratchet_iter in range(MAX_RATCHET_ITERS):
        # ── Generate 10 hypotheses ────────────────────────────────────────
        use_premium = (
            use_premium_for_extreme
            and target.difficulty == "extreme"
            and DEEPSEEK_API_KEY
        )

        batch: list[Hypothesis] = []
        batch.extend(_generate_leanbert_hypotheses(target, LEANBERT_HYPOTHESES))
        batch.extend(_generate_deepseek_hypotheses(target, DEEPSEEK_HYPOTHESES, use_premium))
        batch.extend(_generate_gemini_hypotheses(target, GEMINI_HYPOTHESES))

        # Renumber
        for i, h in enumerate(batch):
            h.id = len(all_hypotheses) + i

        log.info("hypotheses_generated", count=len(batch), ratchet=ratchet_iter)

        # ── Verify each hypothesis ────────────────────────────────────────
        for h in batch:
            _verify_hypothesis(target, h, project_root)
            if h.compile_success:
                log.info("hypothesis_compiled", id=h.id, source=h.source, 
                         proof_len=h.proof_length)

        all_hypotheses.extend(batch)
        compiled = [h for h in batch if h.compile_success]

        if compiled:
            break  # Success — no need to ratchet

        # ── Ratchet: feed errors back as reflection ───────────────────────
        error_summary = "\n".join(
            f"Attempt {h.id} ({h.source}): {h.error_message[:100]}"
            for h in batch if h.error_message
        )
        log.info("ratchet_retry", iter=ratchet_iter, errors=len(batch))
        # Enrich the target context with error feedback for next iteration
        target = SorryTarget(
            file=target.file,
            line=target.line,
            theorem_name=target.theorem_name,
            goal_signature=target.goal_signature,
            sorry_text=target.sorry_text,
            context_window=target.context_window + f"\n\n-- Previous failed proof attempts:\n{error_summary}",
            namespace=target.namespace,
            imports=target.imports,
            difficulty=target.difficulty,
        )

    # ── Rank & select best 3 ──────────────────────────────────────────────
    best_3 = _rank_and_select(all_hypotheses, top_n=3)

    if best_3:
        status = "completed"
        applied = best_3[0].proof_text
    else:
        status = "failed"
        applied = ""

    return CompletionResult(
        target=target,
        hypotheses=all_hypotheses,
        best_3=best_3,
        ratchet_iterations=ratchet_iter + 1,
        status=status,
        applied_proof=applied,
    )


def complete_all_sorrys(
    root: str = "Agora",
    project_root: str = ".",
    apply_proofs: bool = False,
    max_difficulty: str = "hard",
) -> dict[str, Any]:
    """A2A tool entry point: sweep all sorry gaps and attempt completion.

    Args:
        root: Directory to scan for .lean files.
        project_root: Lean project root (where lakefile.lean lives).
        apply_proofs: If True, write successful proofs to disk.
        max_difficulty: Maximum difficulty to attempt ("low", "medium", "hard", "extreme").

    Returns:
        SweepReport as a dict.
    """
    difficulty_order = {"low": 0, "medium": 1, "hard": 2, "extreme": 3}
    max_diff_val = difficulty_order.get(max_difficulty, 2)

    scan_result = scan_directory(root)
    targets = [
        t for t in scan_result.sorry_targets
        if difficulty_order.get(t.difficulty, 3) <= max_diff_val
    ]

    logger.info("sweep_start", targets=len(targets), max_difficulty=max_difficulty)
    t0 = time.monotonic()

    results: list[CompletionResult] = []
    total_hyp = 0
    total_compiled = 0

    for target in targets:
        cr = complete_sorry(target, project_root)
        results.append(cr)
        total_hyp += len(cr.hypotheses)
        total_compiled += sum(1 for h in cr.hypotheses if h.compile_success)

        if apply_proofs and cr.status == "completed" and cr.applied_proof:
            _apply_proof(target, cr.applied_proof)

    elapsed = time.monotonic() - t0
    closed = sum(1 for r in results if r.status == "completed")
    failed = sum(1 for r in results if r.status == "failed")

    # Estimate cost
    cost = (
        total_hyp * 0.001  # LeanBERT: negligible
        + sum(1 for r in results for h in r.hypotheses if h.source.startswith("deepseek")) * 0.005
        + sum(1 for r in results for h in r.hypotheses if h.source == "gemini-deep-think") * 0.015
    )

    report = {
        "sorrys_closed": closed,
        "sorrys_failed": failed,
        "total_hypotheses_generated": total_hyp,
        "total_hypotheses_compiled": total_compiled,
        "total_cost_usd": round(cost, 4),
        "elapsed_s": round(elapsed, 1),
        "results": [
            {
                "theorem": r.target.theorem_name,
                "file": r.target.file,
                "difficulty": r.target.difficulty,
                "status": r.status,
                "ratchet_iterations": r.ratchet_iterations,
                "n_hypotheses": len(r.hypotheses),
                "n_compiled": sum(1 for h in r.hypotheses if h.compile_success),
                "best_proof": r.applied_proof[:200] if r.applied_proof else None,
                "best_score": round(_score_hypothesis(r.best_3[0]), 4) if r.best_3 else None,
                "best_source": r.best_3[0].source if r.best_3 else None,
            }
            for r in results
        ],
    }

    logger.info("sweep_complete", closed=closed, failed=failed, cost=cost)
    return report


def _apply_proof(target: SorryTarget, proof: str) -> None:
    """Write a successful proof to the original .lean file."""
    filepath = Path(target.file)
    content = filepath.read_text()
    lines = content.split('\n')
    idx = target.line - 1
    if idx < len(lines):
        indent = len(lines[idx]) - len(lines[idx].lstrip())
        indented = '\n'.join(
            ' ' * indent + l if l.strip() else l
            for l in proof.split('\n')
        )
        lines[idx] = indented
        filepath.write_text('\n'.join(lines))
        logger.info("proof_applied", file=str(filepath), line=target.line)


def _extract_lean_code(text: str) -> str:
    """Extract Lean 4 code from a markdown-wrapped LLM response."""
    m = re.search(r'```(?:lean4?)?\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Remove markdown artifacts
    text = re.sub(r'^```.*$', '', text, flags=re.MULTILINE)
    return text.strip()


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sorry completion engine")
    parser.add_argument("--root", default="Agora")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--module", help="Specific module to target (e.g., LoRA)")
    parser.add_argument("--apply", action="store_true", help="Apply successful proofs")
    parser.add_argument("--dry-run", action="store_true", help="Scan only, don't attempt proofs")
    parser.add_argument("--max-difficulty", default="hard", choices=["low", "medium", "hard", "extreme"])
    parser.add_argument("--max-hypotheses", type=int, default=MAX_HYPOTHESES)
    args = parser.parse_args()

    if args.dry_run:
        from sorry_scanner import scan_sorrys
        result = scan_sorrys(args.root)
        
        difficulty_order = {"low": 0, "medium": 1, "hard": 2, "extreme": 3}
        max_diff_val = difficulty_order.get(args.max_difficulty, 2)
        
        filtered_sorrys = [
            t for t in result.get("sorry_list", [])
            if difficulty_order.get(t.get("difficulty", "hard"), 3) <= max_diff_val
        ]
        
        print(json.dumps({
            "max_difficulty_filter": args.max_difficulty,
            "total_sorrys_found": result.get("sorrys", 0),
            "filtered_sorrys_count": len(filtered_sorrys),
            "filtered_sorrys": filtered_sorrys,
            "axioms": result.get("axioms", 0),
            "axiom_list": result.get("axiom_list", [])
        }, indent=2))
    else:
        report = complete_all_sorrys(
            root=args.root,
            project_root=args.project_root,
            apply_proofs=args.apply,
            max_difficulty=args.max_difficulty,
        )
        print(json.dumps(report, indent=2))
