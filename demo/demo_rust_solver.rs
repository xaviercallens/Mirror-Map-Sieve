// ╔══════════════════════════════════════════════════════════════════════════╗
// ║     EXACT RATIONAL WITNESS VERIFIER — Rust Implementation              ║
// ║                                                                        ║
// ║  Simplified verifier for ExactRationalWitness.lean concepts            ║
// ║  Uses integer arithmetic to avoid floating point entirely              ║
// ║                                                                        ║
// ║  Compile: rustc demo_rust_solver.rs                                    ║
// ║  Run:     ./demo_rust_solver                                           ║
// ╚══════════════════════════════════════════════════════════════════════════╝

use std::fmt;
use std::cmp::Ordering;

// ─────────────────────────────────────────────────────────────────────────────
// Exact Rational Number (numerator / denominator, always reduced)
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
struct Rational {
    num: i128,
    den: i128,
}

impl Rational {
    fn new(num: i128, den: i128) -> Self {
        assert!(den != 0, "Denominator cannot be zero");
        let sign = if den < 0 { -1 } else { 1 };
        let g = gcd(num.abs(), den.abs());
        Rational {
            num: sign * num / g,
            den: sign * den / g,
        }
    }

    fn from_int(n: i128) -> Self {
        Rational { num: n, den: 1 }
    }

    fn zero() -> Self {
        Rational { num: 0, den: 1 }
    }

    fn add(self, other: Rational) -> Rational {
        Rational::new(
            self.num * other.den + other.num * self.den,
            self.den * other.den,
        )
    }

    fn sub(self, other: Rational) -> Rational {
        Rational::new(
            self.num * other.den - other.num * self.den,
            self.den * other.den,
        )
    }

    fn mul(self, other: Rational) -> Rational {
        Rational::new(self.num * other.num, self.den * other.den)
    }

    fn div(self, other: Rational) -> Rational {
        assert!(other.num != 0, "Division by zero");
        Rational::new(self.num * other.den, self.den * other.num)
    }

    fn sq(self) -> Rational {
        self.mul(self)
    }

    fn is_positive(self) -> bool {
        self.num > 0
    }

    fn is_non_negative(self) -> bool {
        self.num >= 0
    }

    fn approx_f64(self) -> f64 {
        self.num as f64 / self.den as f64
    }
}

impl PartialEq for Rational {
    fn eq(&self, other: &Self) -> bool {
        self.num * other.den == other.num * self.den
    }
}

impl Eq for Rational {}

impl PartialOrd for Rational {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Rational {
    fn cmp(&self, other: &Self) -> Ordering {
        let lhs = self.num * other.den;
        let rhs = other.num * self.den;
        // If denominators have opposite effective signs, flip comparison
        let sign = if self.den * other.den > 0 { 1 } else { -1 };
        if sign > 0 {
            lhs.cmp(&rhs)
        } else {
            rhs.cmp(&lhs)
        }
    }
}

impl fmt::Display for Rational {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.den == 1 {
            write!(f, "{}", self.num)
        } else {
            write!(f, "{}/{}", self.num, self.den)
        }
    }
}

impl fmt::Debug for Rational {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Q({}/{})", self.num, self.den)
    }
}

fn gcd(a: i128, b: i128) -> i128 {
    let (mut a, mut b) = (a, b);
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    a
}

// ─────────────────────────────────────────────────────────────────────────────
// 3D Rational Point
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
struct Point3 {
    x: Rational,
    y: Rational,
    z: Rational,
}

impl Point3 {
    fn new(x: Rational, y: Rational, z: Rational) -> Self {
        Point3 { x, y, z }
    }

    fn lerp(a: &Point3, b: &Point3, t: Rational) -> Point3 {
        let one_minus_t = Rational::from_int(1).sub(t);
        Point3 {
            x: a.x.mul(one_minus_t).add(b.x.mul(t)),
            y: a.y.mul(one_minus_t).add(b.y.mul(t)),
            z: a.z.mul(one_minus_t).add(b.z.mul(t)),
        }
    }
}

impl fmt::Display for Point3 {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "({}, {}, {})", self.x, self.y, self.z)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Axis-Aligned Hypercube (3D Bounding Box)
// ─────────────────────────────────────────────────────────────────────────────

struct Hypercube {
    lo: Point3,
    hi: Point3,
}

impl Hypercube {
    fn new(lo: Point3, hi: Point3) -> Self {
        assert!(lo.x <= hi.x && lo.y <= hi.y && lo.z <= hi.z,
                "Invalid hypercube bounds");
        Hypercube { lo, hi }
    }

    fn contains(&self, p: &Point3) -> bool {
        p.x >= self.lo.x && p.x <= self.hi.x &&
        p.y >= self.lo.y && p.y <= self.hi.y &&
        p.z >= self.lo.z && p.z <= self.hi.z
    }

    fn volume(&self) -> Rational {
        let dx = self.hi.x.sub(self.lo.x);
        let dy = self.hi.y.sub(self.lo.y);
        let dz = self.hi.z.sub(self.lo.z);
        dx.mul(dy).mul(dz)
    }

    fn is_separated_from(&self, other: &Hypercube) -> bool {
        self.hi.x < other.lo.x || other.hi.x < self.lo.x ||
        self.hi.y < other.lo.y || other.hi.y < self.lo.y ||
        self.hi.z < other.lo.z || other.hi.z < self.lo.z
    }

    fn midpoint(&self) -> Point3 {
        let two = Rational::from_int(2);
        Point3 {
            x: self.lo.x.add(self.hi.x).div(two),
            y: self.lo.y.add(self.hi.y).div(two),
            z: self.lo.z.add(self.hi.z).div(two),
        }
    }
}

impl fmt::Display for Hypercube {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[{} → {}]", self.lo, self.hi)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Force Vector (for telesurgery verification)
// ─────────────────────────────────────────────────────────────────────────────

#[derive(Clone, Copy)]
struct ForceVec {
    fx: Rational,
    fy: Rational,
    fz: Rational,
}

impl ForceVec {
    fn new(fx: Rational, fy: Rational, fz: Rational) -> Self {
        ForceVec { fx, fy, fz }
    }

    fn magnitude_sq(&self) -> Rational {
        self.fx.sq().add(self.fy.sq()).add(self.fz.sq())
    }

    fn scale(&self, s: Rational) -> ForceVec {
        ForceVec {
            fx: self.fx.mul(s),
            fy: self.fy.mul(s),
            fz: self.fz.mul(s),
        }
    }

    fn add(&self, other: &ForceVec) -> ForceVec {
        ForceVec {
            fx: self.fx.add(other.fx),
            fy: self.fy.add(other.fy),
            fz: self.fz.add(other.fz),
        }
    }

    fn dot(&self, other: &ForceVec) -> Rational {
        self.fx.mul(other.fx)
            .add(self.fy.mul(other.fy))
            .add(self.fz.mul(other.fz))
    }
}

impl fmt::Display for ForceVec {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "F({}, {}, {})", self.fx, self.fy, self.fz)
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Test Harness
// ─────────────────────────────────────────────────────────────────────────────

struct TestResults {
    passed: u32,
    failed: u32,
}

impl TestResults {
    fn new() -> Self {
        TestResults { passed: 0, failed: 0 }
    }

    fn check(&mut self, condition: bool, name: &str) {
        if condition {
            self.passed += 1;
            println!("  \x1b[92m[PASS]\x1b[0m {}", name);
        } else {
            self.failed += 1;
            println!("  \x1b[91m[FAIL]\x1b[0m {}", name);
        }
    }

    fn total(&self) -> u32 {
        self.passed + self.failed
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN
// ─────────────────────────────────────────────────────────────────────────────

fn main() {
    println!();
    println!("\x1b[1m\x1b[95m  ╔════════════════════════════════════════════════════════════════╗\x1b[0m");
    println!("\x1b[1m\x1b[95m  ║   EXACT RATIONAL WITNESS VERIFIER — Rust Implementation      ║\x1b[0m");
    println!("\x1b[1m\x1b[95m  ║   Integer Arithmetic · Zero Float · Verified Safety           ║\x1b[0m");
    println!("\x1b[1m\x1b[95m  ╚════════════════════════════════════════════════════════════════╝\x1b[0m");
    println!();

    let mut results = TestResults::new();

    // ═══════════════════════════════════════════════════════════════════════
    // TEST SUITE 1: Rational Arithmetic Integrity
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[93m  ──── Rational Arithmetic Integrity ────────────────────────────\x1b[0m");

    let a = Rational::new(1, 3);
    let b = Rational::new(2, 3);
    let sum = a.add(b);
    results.check(sum == Rational::from_int(1), &format!("1/3 + 2/3 = {} (expect 1)", sum));

    let c = Rational::new(7, 12);
    let d = Rational::new(5, 12);
    let diff = c.sub(d);
    results.check(diff == Rational::new(1, 6), &format!("7/12 - 5/12 = {} (expect 1/6)", diff));

    let e = Rational::new(3, 7);
    let f = Rational::new(7, 3);
    let prod = e.mul(f);
    results.check(prod == Rational::from_int(1), &format!("3/7 * 7/3 = {} (expect 1)", prod));

    let g = Rational::new(22, 7);
    let h = Rational::new(11, 14);
    let quot = g.div(h);
    results.check(quot == Rational::from_int(4), &format!("22/7 ÷ 11/14 = {} (expect 4)", quot));

    // Associativity: (a + b) + c == a + (b + c)
    let x = Rational::new(1, 7);
    let y = Rational::new(3, 11);
    let z = Rational::new(5, 13);
    let lhs = x.add(y).add(z);
    let rhs = x.add(y.add(z));
    results.check(lhs == rhs, &format!("Associativity: ({} + {}) + {} == {} + ({} + {})", x, y, z, x, y, z));

    println!();

    // ═══════════════════════════════════════════════════════════════════════
    // TEST SUITE 2: Hypercube Bound Checking
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[93m  ──── Hypercube Bound Checking ─────────────────────────────────\x1b[0m");

    let cube = Hypercube::new(
        Point3::new(Rational::from_int(-10), Rational::from_int(-10), Rational::from_int(0)),
        Point3::new(Rational::from_int(10), Rational::from_int(10), Rational::from_int(5)),
    );

    let vol = cube.volume();
    println!("    Hypercube: {}", cube);
    println!("    Volume:    {} ≈ {:.2}", vol, vol.approx_f64());

    results.check(vol == Rational::from_int(2000), &format!("Volume = {} (expect 2000)", vol));

    // Point inside
    let p_in = Point3::new(Rational::from_int(0), Rational::from_int(0), Rational::new(5, 2));
    results.check(cube.contains(&p_in), &format!("Origin-ish point {} is inside", p_in));

    // Point outside
    let p_out = Point3::new(Rational::from_int(11), Rational::from_int(0), Rational::from_int(0));
    results.check(!cube.contains(&p_out), &format!("Point {} is outside", p_out));

    // Edge point (exactly on boundary)
    let p_edge = Point3::new(Rational::from_int(10), Rational::from_int(10), Rational::from_int(5));
    results.check(cube.contains(&p_edge), &format!("Boundary point {} is contained", p_edge));

    // Epsilon inside boundary
    let eps = Rational::new(1, 1_000_000_000);
    let p_eps = Point3::new(
        Rational::from_int(10).sub(eps),
        Rational::from_int(10).sub(eps),
        Rational::from_int(5).sub(eps),
    );
    results.check(cube.contains(&p_eps), &format!("ε-inside point contained (ε = {})", eps));

    // Epsilon outside boundary
    let p_eps_out = Point3::new(
        Rational::from_int(10).add(eps),
        Rational::from_int(0),
        Rational::from_int(0),
    );
    results.check(!cube.contains(&p_eps_out), &format!("ε-outside point rejected (ε = {})", eps));

    println!();

    // ═══════════════════════════════════════════════════════════════════════
    // TEST SUITE 3: Safety Corridor Trajectory Verification
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[93m  ──── Safety Corridor Trajectory Verification ─────────────────\x1b[0m");

    let corridor = Hypercube::new(
        Point3::new(Rational::from_int(-5), Rational::from_int(-5), Rational::from_int(0)),
        Point3::new(Rational::from_int(5), Rational::from_int(5), Rational::from_int(3)),
    );

    let start = Point3::new(Rational::from_int(-4), Rational::from_int(-4), Rational::from_int(1));
    let end = Point3::new(Rational::from_int(4), Rational::from_int(4), Rational::from_int(2));

    let steps = 20;
    let mut all_inside = true;
    for i in 0..=steps {
        let t = Rational::new(i, steps);
        let p = Point3::lerp(&start, &end, t);
        if !corridor.contains(&p) {
            all_inside = false;
            println!("    \x1b[91m✗\x1b[0m Waypoint {} at {} is OUTSIDE", i, p);
        }
    }
    results.check(all_inside, &format!("All {} waypoints within corridor", steps + 1));

    // Verify corridor separation (collision-free)
    let corridor_a = Hypercube::new(
        Point3::new(Rational::from_int(0), Rational::from_int(0), Rational::from_int(0)),
        Point3::new(Rational::from_int(5), Rational::from_int(5), Rational::from_int(5)),
    );
    let corridor_b = Hypercube::new(
        Point3::new(Rational::new(11, 2), Rational::from_int(0), Rational::from_int(0)),
        Point3::new(Rational::from_int(10), Rational::from_int(5), Rational::from_int(5)),
    );
    let sep = corridor_a.is_separated_from(&corridor_b);
    let gap = corridor_b.lo.x.sub(corridor_a.hi.x);
    results.check(sep, &format!("Corridors separated: gap = {} on X", gap));

    // Adjacent corridors (touching but not overlapping)
    let corridor_c = Hypercube::new(
        Point3::new(Rational::from_int(5), Rational::from_int(0), Rational::from_int(0)),
        Point3::new(Rational::from_int(10), Rational::from_int(5), Rational::from_int(5)),
    );
    let touching = !corridor_a.is_separated_from(&corridor_c);
    results.check(touching, "Adjacent corridors correctly detected as non-separated");

    println!();

    // ═══════════════════════════════════════════════════════════════════════
    // TEST SUITE 4: Force Vector Verification (Telesurgery)
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[93m  ──── Force Vector Verification ────────────────────────────────\x1b[0m");

    let f1 = ForceVec::new(Rational::new(1, 3), Rational::new(2, 3), Rational::new(1, 6));
    let mag_sq = f1.magnitude_sq();
    // |F|² = (1/3)² + (2/3)² + (1/6)² = 1/9 + 4/9 + 1/36 = 4/36 + 16/36 + 1/36 = 21/36 = 7/12
    results.check(
        mag_sq == Rational::new(7, 12),
        &format!("|F|² = {} (expect 7/12)", mag_sq),
    );

    // Threshold check: max force² = 1 N²
    let threshold = Rational::from_int(1);
    results.check(
        mag_sq <= threshold,
        &format!("|F|² = {} ≤ {} (safe for brain tissue)", mag_sq, threshold),
    );

    // Additivity: f1 + f2
    let f2 = ForceVec::new(Rational::new(1, 2), Rational::new(1, 4), Rational::new(1, 8));
    let sum_vec = f1.add(&f2);
    let expected_x = Rational::new(1, 3).add(Rational::new(1, 2));
    results.check(
        sum_vec.fx == expected_x,
        &format!("Force additivity X: {} + {} = {} (expect {})", f1.fx, f2.fx, sum_vec.fx, expected_x),
    );

    // Dot product commutativity
    let dot_12 = f1.dot(&f2);
    let dot_21 = f2.dot(&f1);
    results.check(dot_12 == dot_21, &format!("Dot product commutative: {} == {}", dot_12, dot_21));

    // Scaling preserves direction
    let scale = Rational::new(3, 7);
    let scaled = f1.scale(scale);
    let ratio = scaled.fx.div(f1.fx);
    results.check(ratio == scale, &format!("Scaling preserves direction: ratio = {} (expect {})", ratio, scale));

    println!();

    // ═══════════════════════════════════════════════════════════════════════
    // TEST SUITE 5: Deterministic Execution (HFT Price Bounds)
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[93m  ──── Deterministic Execution (HFT) ───────────────────────────\x1b[0m");

    // Build a simple order book
    let bid = Rational::new(15037, 100);  // 150.37
    let ask = Rational::new(15039, 100);  // 150.39
    let spread = ask.sub(bid);
    results.check(spread.is_positive(), &format!("Spread positive: {} = {}", spread, spread));
    println!("    Bid:    {} ≈ {:.4}", bid, bid.approx_f64());
    println!("    Ask:    {} ≈ {:.4}", ask, ask.approx_f64());
    println!("    Spread: {} ≈ {:.4}", spread, spread.approx_f64());

    // VWAP computation
    let trades: Vec<(Rational, Rational)> = vec![
        (Rational::new(15037, 100), Rational::from_int(100)),
        (Rational::new(15038, 100), Rational::from_int(200)),
        (Rational::new(15039, 100), Rational::from_int(150)),
        (Rational::new(15040, 100), Rational::from_int(50)),
    ];

    let total_value = trades.iter().fold(Rational::zero(), |acc, (p, q)| acc.add(p.mul(*q)));
    let total_qty = trades.iter().fold(Rational::zero(), |acc, (_, q)| acc.add(*q));
    let vwap = total_value.div(total_qty);

    // Recompute in reverse order — must be identical
    let total_value_rev = trades.iter().rev().fold(Rational::zero(), |acc, (p, q)| acc.add(p.mul(*q)));
    let total_qty_rev = trades.iter().rev().fold(Rational::zero(), |acc, (_, q)| acc.add(*q));
    let vwap_rev = total_value_rev.div(total_qty_rev);

    results.check(vwap == vwap_rev, &format!("VWAP deterministic: {} == {} (reversed)", vwap, vwap_rev));
    println!("    VWAP: {} ≈ {:.6}", vwap, vwap.approx_f64());

    // Exposure check
    let exposure = trades.iter().fold(Rational::zero(), |acc, (p, q)| acc.add(p.mul(*q)));
    let risk_limit = Rational::from_int(100_000);
    results.check(
        exposure <= risk_limit,
        &format!("Exposure {} ≤ risk limit {}", exposure, risk_limit),
    );

    println!();

    // ═══════════════════════════════════════════════════════════════════════
    // FINAL SUMMARY
    // ═══════════════════════════════════════════════════════════════════════

    println!("\x1b[1m\x1b[96m  ╔════════════════════════════════════════════════════════════════╗\x1b[0m");
    println!("\x1b[1m\x1b[96m  ║                      FINAL SUMMARY                            ║\x1b[0m");
    println!("\x1b[1m\x1b[96m  ╚════════════════════════════════════════════════════════════════╝\x1b[0m");
    println!();
    println!("  Total tests: {}", results.total());
    println!("  \x1b[92mPassed: {}\x1b[0m", results.passed);
    println!("  \x1b[91mFailed: {}\x1b[0m", results.failed);

    let rate = results.passed as f64 / results.total() as f64 * 100.0;
    println!("  Pass rate: {:.1}%", rate);
    println!();

    if results.failed == 0 {
        println!("  \x1b[1m\x1b[42m\x1b[97m  ✓ ALL TESTS PASSED — VERIFIER SOUND  \x1b[0m");
    } else {
        println!("  \x1b[1m\x1b[41m\x1b[97m  ✗ {} FAILURES DETECTED  \x1b[0m", results.failed);
    }

    println!();
    println!("  \x1b[2mExactRationalWitness Rust verifier complete.\x1b[0m");
    println!("  \x1b[2mAll arithmetic performed with i128 rationals — zero float rounding.\x1b[0m");
    println!();

    std::process::exit(if results.failed == 0 { 0 } else { 1 });
}
