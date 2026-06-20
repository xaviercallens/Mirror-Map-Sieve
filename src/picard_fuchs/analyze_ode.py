#!/usr/bin/env python3
"""
analyze_ode.py — extract the exact order-6 ODE for f(z)=sum S_20(n) z^n and
read off its structure at z=0 (indicial equation / local exponents), which
decides MUM vs non-MUM and gives the first evidence on factorization.

We reconstruct the operator in theta = z d/dz form:
    L = sum_{i=0}^{6} R_i(z) theta^i ,   (theta z^n = n z^n)
because the theta-form makes the z=0 indicial equation immediate: the lowest
z-power part gives a polynomial in the exponent whose roots are the local
exponents at 0. A maximal-unipotent-monodromy (MUM) point — the hallmark of a
Calabi-Yau operator — has ALL local exponents equal (to 0), i.e. indicial
equation s^(order) = 0.

We get the theta-operator directly from the recurrence: for f=sum a_n z^n,
  theta f = sum n a_n z^n,
so a relation sum_i c_i(n) ... is most easily found as: L f = 0 with
L = sum_{i,j} b_{i,j} z^j theta^i, and [z^m](z^j theta^i f) = (m-j)^i a_{m-j}.
We find the b_{i,j} by exact nullspace over Q (small), then analyze.

Run:  python3 src/picard_fuchs/analyze_ode.py
"""
from __future__ import annotations
from math import comb
import sympy as sp
import json, os

def S(n): return sum(comb(n,k)**4*comb(n+k,k) for k in range(n+1))

ORDER = 6   # minimal ODE order (from find_ode.py)

def main():
    print("="*72)
    print("  Exact order-6 theta-ODE for f(z) and its z=0 indicial equation")
    print("="*72)

    # Find smallest theta-degree D (in z) admitting an order-6 relation
    # L = sum_{i=0}^{6} sum_{j=0}^{D} b_{i,j} z^j theta^i,  [z^m](z^j theta^i f)=(m-j)^i a_{m-j}.
    MAXN = 160
    Svals = [S(n) for n in range(MAXN+1)]

    found = None
    for D in range(1, 12):
        ncols = (ORDER+1)*(D+1)
        neq = ncols + 30
        if neq+0 > MAXN: break
        rows=[]
        for m in range(neq):
            row=[]
            for i in range(ORDER+1):
                for j in range(D+1):
                    a = m-j
                    row.append(sp.Integer((a**i)*Svals[a]) if a>=0 else sp.Integer(0))
            rows.append(row)
        M=sp.Matrix(rows)
        ns=M.nullspace()
        if len(ns)>=1:
            found=(D,ncols,ns)
            break
    if not found:
        print("no theta-ODE found up to z-degree 11"); return
    D,ncols,ns = found
    print(f"\nFound order-{ORDER} theta-ODE at z-degree D={D}; nullspace dim={len(ns)}")
    vec = ns[0]
    rats=[sp.Rational(x) for x in vec]
    lcm=sp.ilcm(*[r.q for r in rats]); intvec=[int(r*lcm) for r in rats]
    g=sp.igcd(*[v for v in intvec if v!=0]); intvec=[v//g for v in intvec]

    z,s = sp.symbols('z s')
    # b_{i,j} = intvec[i*(D+1)+j]; coefficient of theta^i is R_i(z)=sum_j b_{i,j} z^j
    Ri=[]
    for i in range(ORDER+1):
        Ri.append(sum(intvec[i*(D+1)+j]*z**j for j in range(D+1)))
    print("\ntheta-operator coefficients R_i(z) (coef of theta^i):")
    for i in range(ORDER+1):
        print(f"  R_{i}(z) = {sp.expand(Ri[i])}")

    # Indicial equation at z=0: take the z^0 part of each R_i, form sum_i R_i(0) s^i.
    indicial = sp.expand(sum(Ri[i].subs(z,0)*s**i for i in range(ORDER+1)))
    print(f"\nIndicial polynomial at z=0:  {indicial}")
    roots = sp.roots(sp.Poly(indicial, s))
    print(f"Local exponents at z=0 (root: multiplicity): {roots}")
    is_mum = (len(roots)==1 and list(roots.keys())[0]==0 and list(roots.values())[0]==ORDER)
    print(f"\nMUM point at z=0 (all exponents 0)?  {is_mum}")
    if is_mum:
        print("  => consistent with a Calabi-Yau operator with a MUM point.")
    else:
        print("  => NOT a single MUM point of full order; the operator likely")
        print("     FACTORS (apparent singularities / reducible). The exponents")
        print("     above tell us the Frobenius structure; integer-spaced")
        print("     exponents at 0 indicate apparent singularities to be removed.")

    # singular points: roots of leading theta coefficient R_6(z) (times z powers)
    print(f"\nLeading theta-coefficient R_{ORDER}(z) factored:")
    print(f"  {sp.factor(Ri[ORDER])}")

    out={"ode_order":ORDER,"theta_z_degree":D,
         "indicial_at_0":str(indicial),
         "local_exponents_at_0":{str(k):int(v) for k,v in roots.items()},
         "is_MUM_full_order":bool(is_mum),
         "leading_theta_coeff_factored":str(sp.factor(Ri[ORDER]))}
    with open(os.path.join(os.path.dirname(__file__),"ode_analysis.json"),"w") as fh:
        json.dump(out,fh,indent=2)
    print("\nSaved ode_analysis.json")

if __name__=="__main__":
    main()
