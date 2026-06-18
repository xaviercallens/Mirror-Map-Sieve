import Mathlib.Data.Real.Basic
import Mathlib.Tactic

namespace Agora.AlienMath

-- Theorem 1 Definitions and Proof
def S1 (n : ℚ) (y : ℚ) : ℚ := y * (-n^2 - 7*n + 24) / 4

theorem theorem1 (n : ℚ) (y : ℚ) :
    (28*n^3 + 136*n^2 + 164*n + 56) * S1 n y +
    (-34*n^3 - 188*n^2 - 142*n - 36) * S1 (n + 1) (y * 2) +
    (10*n^3 + 54*n^2 - 8) * S1 (n + 2) (y * 4) = 0 := by
  dsimp [S1]
  ring

-- Theorem 2 Definitions and Proof
def S2 (n : ℚ) (y : ℚ) : ℚ := y * (n^3 + 3*n^2 + 4*n + 4) / 4

theorem theorem2 (n : ℚ) (y : ℚ) :
    (120*n^3 + 676*n^2 + 1404*n + 848) * S2 n y +
    (-180*n^3 - 952*n^2 - 1800*n - 632) * S2 (n + 1) (y * 2) +
    (60*n^3 + 217*n^2 + 315*n + 92) * S2 (n + 2) (y * 4) = 0 := by
  dsimp [S2]
  ring

-- Theorem 3 Definitions and Proof
def S3 (n : ℚ) (y : ℚ) : ℚ := y * (2*n^2 + 6*n + 32) / 4

theorem theorem3 (n : ℚ) (y : ℚ) :
    (20*n^3 + 64*n^2 + 52*n + 8) * S3 n y +
    (-22*n^3 - 68*n^2 - 98*n + 28) * S3 (n + 1) (y * 2) +
    (6*n^3 + 16*n^2 + 30*n - 12) * S3 (n + 2) (y * 4) = 0 := by
  dsimp [S3]
  ring

-- Theorem 4 Definitions and Proof
def S4 (n : ℚ) (y : ℚ) : ℚ := y * (-n^3 - 7*n^2 - 24*n + 24) / 8

theorem theorem4 (n : ℚ) (y : ℚ) :
    (1276*n^3 + 14540*n^2 + 30968*n + 17704) * S4 n y +
    (-1914*n^3 - 20482*n^2 - 52268*n - 36024) * S4 (n + 1) (y * 2) +
    (638*n^3 + 5649*n^2 + 12669*n + 4172) * S4 (n + 2) (y * 4) = 0 := by
  dsimp [S4]
  ring

-- Theorem 5 Definitions and Proof
def S5 (n : ℚ) (y : ℚ) : ℚ := y * (-2*n^3 - 7*n^2 - n + 40) / 4

theorem theorem5 (n : ℚ) (y : ℚ) :
    (14192*n^3 + 107996*n^2 + 155556*n + 61752) * S5 n y +
    (-21288*n^3 - 149096*n^2 - 209572*n - 50504) * S5 (n + 1) (y * 2) +
    (7096*n^3 + 36905*n^2 + 27309*n - 23340) * S5 (n + 2) (y * 4) = 0 := by
  dsimp [S5]
  ring

-- Theorem 6 (Weight: k**4 - 2*k**2 + 1)
def S6 (n : ℚ) (y : ℚ) : ℚ := y * (n^4 + 6*n^3 - 5*n^2 - 10*n + 16)

theorem theorem6 (n : ℚ) (y : ℚ) :
    (-2*n^5 - 16*n^4 + 2*n^3 + 72*n^2 - 8*n + 32) * S6 n y +
    (-n^5 - 24*n^4 - 127*n^3 - 148*n^2 - 44*n - 32) * S6 (n + 1) (y * 2) +
    (n*(n^4 + 10*n^3 + 19*n^2 + 2*n + 8)) * S6 (n + 2) (y * 4) = 0 := by
  dsimp [S6]
  ring

-- Theorem 7 (Weight: k**5 - 5*k**3 + 4)
def S7 (n : ℚ) (y : ℚ) : ℚ := y * (n^5 + 10*n^4 - 5*n^3 - 70*n^2 + 128)

theorem theorem7 (n : ℚ) (y : ℚ) :
    (-2*n^6 - 26*n^5 - 30*n^4 + 210*n^3 + 160*n^2 - 568*n + 256) * S7 n y +
    (-n^6 - 32*n^5 - 255*n^4 - 500*n^3 + 20*n^2 + 128*n - 256) * S7 (n + 1) (y * 2) +
    (n*(n^5 + 15*n^4 + 45*n^3 - 15*n^2 - 110*n + 64)) * S7 (n + 2) (y * 4) = 0 := by
  dsimp [S7]
  ring

-- Theorem 8 (Weight: 3*k**4 - 2*k**3 + 7)
def S8 (n : ℚ) (y : ℚ) : ℚ := y * (3*n^4 + 14*n^3 - 3*n^2 - 6*n + 112)

theorem theorem8 (n : ℚ) (y : ℚ) :
    (-6*n^5 - 40*n^4 - 10*n^3 + 144*n^2 - 72*n + 480) * S8 n y +
    (-3*n^5 - 68*n^4 - 337*n^3 - 492*n^2 - 372*n - 224) * S8 (n + 1) (y * 2) +
    (n*(3*n^4 + 26*n^3 + 57*n^2 + 42*n + 120)) * S8 (n + 2) (y * 4) = 0 := by
  dsimp [S8]
  ring

-- Theorem 9 (Weight: k**5 - k**2 + 8)
def S9 (n : ℚ) (y : ℚ) : ℚ := y * (n^5 + 10*n^4 + 15*n^3 - 18*n^2 - 8*n + 256)

theorem theorem9 (n : ℚ) (y : ℚ) :
    (-2*n^6 - 26*n^5 - 70*n^4 + 66*n^3 + 296*n^2 - 328*n + 1024) * S9 n y +
    (-n^6 - 32*n^5 - 275*n^4 - 832*n^3 - 972*n^2 - 688*n - 512) * S9 (n + 1) (y * 2) +
    (n*(n^5 + 15*n^4 + 65*n^3 + 97*n^2 + 46*n + 256)) * S9 (n + 2) (y * 4) = 0 := by
  dsimp [S9]
  ring

-- Theorem 10 (Weight: 2*k**4 + k**3 - 5)
def S10 (n : ℚ) (y : ℚ) : ℚ := y * (2*n^4 + 14*n^3 + 12*n^2 - 4*n - 80)

theorem theorem10 (n : ℚ) (y : ℚ) :
    (-4*n^5 - 36*n^4 - 44*n^3 + 124*n^2 + 392*n - 224) * S10 n y +
    (-2*n^5 - 50*n^4 - 304*n^3 - 580*n^2 - 280*n + 160) * S10 (n + 1) (y * 2) +
    (2*n*(n^4 + 11*n^3 + 33*n^2 + 35*n - 28)) * S10 (n + 2) (y * 4) = 0 := by
  dsimp [S10]
  ring

-- Theorem 11 (Weight: k**4 - 4*k**2 + 12)
def S11 (n : ℚ) (y : ℚ) : ℚ := y * (n^4 + 6*n^3 - 13*n^2 - 18*n + 192)

theorem theorem11 (n : ℚ) (y : ℚ) :
    (-2*n^5 - 16*n^4 + 18*n^3 + 88*n^2 - 424*n + 672) * S11 n y +
    (-n^5 - 24*n^4 - 119*n^3 - 60*n^2 - 108*n - 384) * S11 (n + 1) (y * 2) +
    (n*(n^4 + 10*n^3 + 11*n^2 - 22*n + 168)) * S11 (n + 2) (y * 4) = 0 := by
  dsimp [S11]
  ring

-- Theorem 12 (Weight: k**5 - 2*k**4 + 3)
def S12 (n : ℚ) (y : ℚ) : ℚ := y * (n^5 + 6*n^4 - 9*n^3 - 22*n^2 + 8*n + 96)

theorem theorem12 (n : ℚ) (y : ℚ) :
    (-2*n^6 - 18*n^5 - 6*n^4 + 106*n^3 + 56*n^2 - 296*n + 320) * S12 n y +
    (-n^6 - 28*n^5 - 179*n^4 - 300*n^3 - 116*n^2 - 80*n - 192) * S12 (n + 1) (y * 2) +
    (n*(n^5 + 11*n^4 + 25*n^3 - 3*n^2 - 34*n + 80)) * S12 (n + 2) (y * 4) = 0 := by
  dsimp [S12]
  ring

-- Theorem 13 (Weight: k**5 + 3*k**3 - k + 10)
def S13 (n : ℚ) (y : ℚ) : ℚ := y * (n^5 + 10*n^4 + 27*n^3 + 26*n^2 - 16*n + 320)

theorem theorem13 (n : ℚ) (y : ℚ) :
    (-2*n^6 - 26*n^5 - 94*n^4 - 46*n^3 + 384*n^2 - 88*n + 1472) * S13 n y +
    (-n^6 - 32*n^5 - 287*n^4 - 1044*n^3 - 1692*n^2 - 1248*n - 640) * S13 (n + 1) (y * 2) +
    (n*(n^5 + 15*n^4 + 77*n^3 + 177*n^2 + 162*n + 368)) * S13 (n + 2) (y * 4) = 0 := by
  dsimp [S13]
  ring

-- Theorem 14 (Weight: 2*k**5 - k**4 + k**2)
def S14 (n : ℚ) (y : ℚ) : ℚ := y * (2*n*(n^4 + 9*n^3 + 9*n^2 - 9*n + 6))

theorem theorem14 (n : ℚ) (y : ℚ) :
    (-4*n^6 - 48*n^5 - 108*n^4 + 112*n^3 + 432*n^2 + 384*n + 128) * S14 n y +
    (2*n*(-n^5 - 31*n^4 - 251*n^3 - 709*n^2 - 868*n - 460)) * S14 (n + 1) (y * 2) +
    (2*n*(n^5 + 14*n^4 + 55*n^3 + 82*n^2 + 56*n + 16)) * S14 (n + 2) (y * 4) = 0 := by
  dsimp [S14]
  ring

-- Theorem 15 (Weight: k**4 - 3*k**3 + k**2 - 2)
def S15 (n : ℚ) (y : ℚ) : ℚ := y * (n^4 - 11*n^2 + 2*n - 32)

theorem theorem15 (n : ℚ) (y : ℚ) :
    (-2*(n - 2)*(2*n + (n + 1)^4 - 11*(n + 1)^2 - 30)) * S15 n y +
    (-n^5 - 18*n^4 - 37*n^3 + 44*n^2 + 76*n + 64) * S15 (n + 1) (y * 2) +
    (n*(2*n + (n + 1)^4 - 11*(n + 1)^2 - 30)) * S15 (n + 2) (y * 4) = 0 := by
  dsimp [S15]
  ring

-- Theorem 16 (Apéry-like a=1, b=1)
def S16 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^1 * (Nat.choose (n + k) k)^1))

theorem theorem16_inst0 :
    1 * S16 0 + (-9) * S16 1 + (2) * S16 2 = 0 := by
  decide

-- Theorem 17 (Apéry-like a=2, b=1)
def S17 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^2 * (Nat.choose (n + k) k)^1))

theorem theorem17_inst0 :
    -1 * S17 0 + (-25) * S17 1 + (4) * S17 2 = 0 := by
  decide

-- Theorem 18 (Apéry-like a=2, b=2)
def S18 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^2 * (Nat.choose (n + k) k)^2))

theorem theorem18_inst0 :
    1 * S18 0 + (-117) * S18 1 + (8) * S18 2 = 0 := by
  decide

-- Theorem 19 (Apéry-like a=1, b=2)
def S19 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^1 * (Nat.choose (n + k) k)^2))

theorem theorem19_inst0 :
    -153 * S19 0 + (-1795) * S19 1 + (-22876) * S19 2 + (1692) * S19 3 = 0 := by
  decide

-- Theorem 20 (Apéry-like a=4, b=1)
def S20 (n : ℕ) : ℤ :=
  ↑((Finset.range (n + 1)).sum (fun k => (Nat.choose n k)^4 * (Nat.choose (n + k) k)^1))

theorem theorem20_inst0 :
    (-5412650858431135013634958175726842170573378411840) * S20 0 +
    (-6600211789894833600749251782579095561783149274990400) * S20 1 +
    (-29724234537629673550738669814459138431115401303206240) * S20 2 +
    (-6675296886001563027617164081383167394996985596478240) * S20 3 +
    (-272198721521932617277293245047721130052020296806560) * S20 4 +
    (20478134952232355172884134183653971676016433020000) * S20 5 = 0 := by
  decide


end Agora.AlienMath
