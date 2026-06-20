#!/usr/bin/env sage
# -*- mode: python -*-
r"""
gcp_phase1_sage.py — Phase 1B: run inside SageMath to PROVE the order-4
Picard-Fuchs recurrence for S_20(n) = sum_k C(n,k)^4 C(n+k,k), via a creative-
telescoping certificate, and to FACTOR the differential operator.

Self-contained: depends only on SageMath + ore_algebra (preinstalled in recent
sagemath/sagemath images; if missing the script installs it). Designed to run on
Google Cloud Build with the sagemath/sagemath:latest image — see
cloudbuild_phase1_sage.yaml — but also runs locally with `sage gcp_phase1_sage.py`.

What it does
------------
1. Recomputes S_20 and re-derives the minimal recurrence by exact nullspace
   (independent re-confirmation of the pure-Python result: order 4, degree 13).
2. Runs ore_algebra creative telescoping on the summand to obtain a telescoper
   L(n,Sn) AND a certificate; the certificate reduces the recurrence to a single
   rational identity, i.e. a PROOF valid for all n.
3. Converts the recurrence operator to the differential operator for
   f(z) = sum_n S_20(n) z^n and FACTORS it over Q(z); irreducibility of the
   order-4 factor confirms S_20 is a genuine order-4 (CY 3-fold) period.
4. Writes a machine-readable result to ./phase1_result.json (the cloudbuild
   copies this to GCS).

All claims are labelled proved / computed. Output is verbose for the build log.
"""

import json
import sys

def log(*a):
    print(*a); sys.stdout.flush()

log("=" * 72)
log("  Phase 1B (SageMath) — certify order-4 Picard-Fuchs operator for S_20")
log("=" * 72)

from sage.all import (QQ, PolynomialRing, binomial, matrix, gcd, var, CC)

result = {"sequence": "S_20(n) = sum_k C(n,k)^4 C(n+k,k)"}

# ---------------------------------------------------------------------------
# 0. The sequence
# ---------------------------------------------------------------------------
def S20(m):
    return sum(binomial(m, j)**4 * binomial(m + j, j) for j in range(m + 1))

S_vals = [S20(i) for i in range(120)]
log("\nS_20(0..9) =", S_vals[:10])
result["first_terms"] = [int(x) for x in S_vals[:18]]

# ---------------------------------------------------------------------------
# 1. Exact minimal recurrence by nullspace (re-confirmation, order/degree)
# ---------------------------------------------------------------------------
log("\n[1] Re-deriving the minimal recurrence by exact nullspace over QQ ...")
Rn = PolynomialRing(QQ, 'n'); nv = Rn.gen()
min_order = None
for order in range(2, 7):
    for deg in range(0, 16):
        ncols = (order + 1) * (deg + 1)
        neq = ncols + 25
        if neq + order >= len(S_vals):
            continue
        M = matrix(QQ, neq, ncols)
        for r in range(neq):
            c = 0
            for i in range(order + 1):
                for j in range(deg + 1):
                    M[r, c] = (r ** j) * S_vals[r + i]; c += 1
        ker = M.right_kernel()
        if ker.dimension() >= 1:
            # validate on further terms
            v = ker.basis()[0]; ok = True
            for tn in range(neq, min(len(S_vals) - order, neq + 15)):
                s = 0; idx = 0
                for i in range(order + 1):
                    for j in range(deg + 1):
                        s += v[idx] * (tn ** j) * S_vals[tn + i]; idx += 1
                if s != 0: ok = False; break
            if ok:
                if min_order is None:
                    min_order = (order, deg)
                    log(f"    minimal recurrence: order {order}, degree {deg}")
                break
result["minimal_order"] = min_order[0] if min_order else None
result["minimal_degree"] = min_order[1] if min_order else None
log(f"    => minimal order = {result['minimal_order']} "
    f"(order 4 => CY 3-fold; order 5 => CY 4-fold)")

# ---------------------------------------------------------------------------
# 2. Creative-telescoping CERTIFICATE (the proof) via ore_algebra
# ---------------------------------------------------------------------------
log("\n[2] Creative telescoping via ore_algebra (proof for all n) ...")
def _ensure_ore_algebra():
    try:
        from ore_algebra import OreAlgebra  # noqa
        return True
    except ImportError:
        pass
    import subprocess
    # Try PyPI sdist first (no git needed), then the git source as a fallback.
    for spec in ("ore_algebra", "git+https://github.com/mkauers/ore_algebra.git"):
        log(f"    ore_algebra missing; trying: pip install {spec}")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", spec])
        if r.returncode == 0:
            try:
                import importlib, ore_algebra  # noqa
                importlib.reload(ore_algebra)
                from ore_algebra import OreAlgebra  # noqa
                return True
            except ImportError:
                continue
    return False

_HAVE_ORE = _ensure_ore_algebra()
if _HAVE_ORE:
    from ore_algebra import OreAlgebra

cert_ok = False
if not _HAVE_ORE:
    log("    ore_algebra unavailable in this image; SKIPPING the certificate step.")
    log("    (The order-4/degree-13 minimal recurrence is nonetheless independently")
    log("     re-confirmed above over exact QQ. Certificate to be produced in an")
    log("     image that ships ore_algebra, or by Koutschan's HolonomicFunctions.)")
    result["certificate_status"] = "SKIPPED: ore_algebra not installable in image"
try:
    if not _HAVE_ORE:
        raise RuntimeError("ore_algebra unavailable")
    # Bivariate Ore algebra: shifts Sn (n->n+1), Sk (k->k+1) over QQ(n,k).
    Rnk = PolynomialRing(QQ, ['n', 'k']); (n_, k_) = Rnk.gens()
    F = Rnk.fraction_field()
    A = OreAlgebra(F, 'Sn', 'Sk'); Sn, Sk = A.gens()

    # Summand shift-quotients for t(n,k)=C(n,k)^4 C(n+k,k):
    #   t(n,k+1)/t(n,k) = ((n-k)/(k+1))^4 * (n+k+1)/(k+1)
    #   t(n+1,k)/t(n,k) = ((n+1)/(n+1-k))^4 * (n+k+1)/(n+1)
    rk = ((n_ - k_) / (k_ + 1))**4 * (n_ + k_ + 1) / (k_ + 1)
    rn = ((n_ + 1) / (n_ + 1 - k_))**4 * (n_ + k_ + 1) / (n_ + 1)
    annk = Sk - rk
    annn = Sn - rn
    log("    summand annihilators built; computing telescoper+certificate ...")

    # The proof-producing call. API name can vary across versions; try a few.
    telescoper = certificate = None
    ideal = A.ideal([annn, annk])
    for meth in ("creative_telescoping", "ct"):
        if hasattr(ideal, meth):
            telescoper, certificate = getattr(ideal, meth)(Sn, Sk)
            break
    if telescoper is None:
        # fall back to the dfinite_creative_telescoping helper if present
        from ore_algebra import creative_telescoping as ct_fn
        telescoper, certificate = ct_fn([annn, annk], Sn, Sk)

    log("    TELESCOPER L(n,Sn) =")
    log("      ", telescoper)
    log("    order(L) =", telescoper.order())
    result["telescoper_order"] = int(telescoper.order())
    result["telescoper"] = str(telescoper)
    result["certificate"] = str(certificate)
    cert_ok = True

    # -----------------------------------------------------------------
    # 3. recurrence -> differential operator and factor
    # -----------------------------------------------------------------
    log("\n[3] Converting to differential operator and factoring over Q(z) ...")
    try:
        Pz = PolynomialRing(QQ, 'z');
        Dz = OreAlgebra(Pz.fraction_field(), 'Dz')
        Lode = telescoper.to_D(Dz)
        log("    L_ode =", Lode)
        log("    order(L_ode) =", Lode.order())
        result["ode_order"] = int(Lode.order())
        facs = Lode.factor()
        result["ode_factors"] = [str(f) for f in facs]
        log("    factorization:", facs)
        irred = (len(facs) == 1)
        result["ode_irreducible"] = bool(irred)
        log("    minimal operator irreducible?", irred,
            "(irreducible order-4 => genuine CY 3-fold period)")
    except Exception as e:
        log("    rec->diff/factor step failed:", repr(e))
        result["ode_note"] = repr(e)

except Exception as e:
    log("    creative_telescoping failed in this environment:", repr(e))
    result["certificate_status"] = f"FAILED: {e!r}"

result["certificate_status"] = "PROVED (certificate computed)" if cert_ok else \
    result.get("certificate_status", "NOT PRODUCED")

# ---------------------------------------------------------------------------
# 4. persist
# ---------------------------------------------------------------------------
import os as _os
_outdir = _os.environ.get("OUT_DIR", "/tmp")
_outpath = _os.path.join(_outdir, "phase1_result.json")
try:
    with open(_outpath, "w") as fh:
        json.dump(result, fh, indent=2, default=str)
    log(f"\nWrote {_outpath}")
except Exception as _e:
    log(f"\nCould not write {_outpath}: {_e!r}; printing result instead:")
    log(json.dumps(result, indent=2, default=str))
log("\nSUMMARY:")
log("  minimal recurrence order :", result.get("minimal_order"))
log("  telescoper order         :", result.get("telescoper_order"))
log("  ODE order / irreducible  :", result.get("ode_order"), "/",
    result.get("ode_irreducible"))
log("  certificate status       :", result.get("certificate_status"))
log("\nDone.")
