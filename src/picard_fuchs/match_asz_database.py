#!/usr/bin/env python3
"""
match_asz_database.py — Phase 2 prep: is the S_20 order-4 operator already in the
Almkvist--Straten--Zudilin (AESZ) tables of Calabi--Yau equations?

This is the single most useful novelty check (per docs/RESEARCH_PLAN.md and the
collaboration issue): if the operator is catalogued, S_20 is a known object under
a different normalization, and we should say so.

The AESZ database (548 entries, fields: id, operator_D in theta-notation,
latex_A_n) is maintained in the SocrateAI-Scientific-Agora repository as
asz_sequences.json. This script:

  (A) TEXTUAL PRESCREEN (available now): scans latex_A_n for the exact
      signature sum_k C(n,k)^4 C(n+k,k) and for near neighbours, and reports
      candidates. This is heuristic, NOT a proof of (non-)membership.

  (B) RIGOROUS OPERATOR MATCH (needs the Phase 1B Sage output): once the
      differential operator L for f(z)=sum S_20(n) z^n is known (theta-notation),
      compare it to each entry's operator_D up to the standard CY-operator
      equivalences (rescaling z -> c*z, and reflection). Hook left in place;
      fill in `S20_OPERATOR_THETA` from phase1_result.json when available.

Usage:
  python3 match_asz_database.py [path/to/asz_sequences.json]

If the path is omitted, it tries the known Agora location.
"""
from __future__ import annotations
import json, os, re, sys

DEFAULT_DB = os.path.expanduser(
    "~/xdev/SocrateAI-Scientific-Agora/asz_sequences.json")

# Fill this in from the Phase 1B Sage run (phase1_result.json -> ode/theta form),
# then re-run for the rigorous match. Left None until the certified operator
# is in theta-notation.
S20_OPERATOR_THETA = None


def load_db(path):
    with open(path) as fh:
        return json.load(fh)


def textual_prescreen(db):
    print("=" * 72)
    print("  (A) Textual prescreen of AESZ latex_A_n formulas")
    print("=" * 72)
    withA = [x for x in db if x.get("latex_A_n")]
    print(f"  entries with a closed form: {len(withA)} / {len(db)}\n")

    # Normalize latex to compare loosely (strip spaces/braces).
    def norm(s):
        return re.sub(r"[\s{}]", "", s or "")

    target_variants = [
        r"\sum_{k=0}^n\binom nk^4\binom{n+k}k",
        r"\sum_{k=0}^n\binom{n}{k}^4\binom{n+k}{k}",
        r"\sum_k\binom nk^4\binom{n+k}k",
    ]
    targets_n = [norm(t) for t in target_variants]

    exact = []
    powfour = []
    for x in withA:
        a = x["latex_A_n"]; an = norm(a)
        if any(t in an for t in targets_n):
            exact.append(x)
        # near neighbours: anything with a 4th power of a binomial AND an upper
        # binomial of the form (n+k choose k)
        if ("^4" in an or "^{4}" in an) and ("binom" in an):
            powfour.append(x)

    if exact:
        print("  *** EXACT signature found in AESZ — S_20 may be catalogued: ***")
        for x in exact:
            print(f"     id {x['id']}: {x['latex_A_n']}")
    else:
        print("  No exact 'sum_k C(n,k)^4 C(n+k,k)' signature in latex_A_n.")
        print("  (Heuristic only: many entries store no closed form, and equal")
        print("   operators can have different-looking A_n. Not a proof.)\n")

    print(f"  Fourth-power-binomial neighbours ({len(powfour)} entries) — review")
    print("  these manually / by operator once the ODE is known:")
    for x in powfour[:25]:
        print(f"     id {x['id']:>4}: {x['latex_A_n'][:70]}")
    if len(powfour) > 25:
        print(f"     ... and {len(powfour)-25} more")
    return exact, powfour


def rigorous_match(db):
    print("\n" + "=" * 72)
    print("  (B) Rigorous operator match")
    print("=" * 72)
    if S20_OPERATOR_THETA is None:
        print("  SKIPPED: the certified S_20 differential operator (theta-notation)")
        print("  is not yet filled in. Run Phase 1B (gcp_phase1_sage.py on")
        print("  SageMath), read the ODE from phase1_result.json, set")
        print("  S20_OPERATOR_THETA at the top of this script, and re-run.")
        print("  Then compare against each entry's operator_D up to z-rescaling.")
        return
    # (Implementation deferred until the operator is available.)
    print("  TODO: normalize S20_OPERATOR_THETA and each operator_D, compare up")
    print("  to z -> c*z rescaling and standard CY gauge.")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB
    if not os.path.exists(path):
        print(f"AESZ database not found at {path}")
        print("Pass the path to asz_sequences.json as an argument.")
        sys.exit(1)
    db = load_db(path)
    print(f"Loaded AESZ database: {len(db)} entries from {path}\n")
    textual_prescreen(db)
    rigorous_match(db)
    print("\nNote: a *negative* textual prescreen is weak evidence of novelty;")
    print("only the operator-level comparison (B) is decisive. See")
    print("docs/RESEARCH_PLAN.md, Phase 2.")


if __name__ == "__main__":
    main()
