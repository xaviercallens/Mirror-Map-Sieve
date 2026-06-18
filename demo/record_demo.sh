#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Tesla Prototyping Pipeline — Demo Recording Script                     ║
# ║                                                                         ║
# ║  Records demo_prototype.py with asciinema, generates GIF/SVG output     ║
# ╚══════════════════════════════════════════════════════════════════════════╝

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_SCRIPT="${SCRIPT_DIR}/demo_prototype.py"
RECORDINGS_DIR="${SCRIPT_DIR}/recordings"
RUST_SRC="${SCRIPT_DIR}/demo_rust_solver.rs"
RUST_BIN="${SCRIPT_DIR}/demo_rust_solver"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

info()  { echo -e "  ${CYAN}[INFO]${RESET} $1"; }
ok()    { echo -e "  ${GREEN}[OK]${RESET}   $1"; }
warn()  { echo -e "  ${YELLOW}[WARN]${RESET} $1"; }
err()   { echo -e "  ${RED}[ERR]${RESET}  $1"; }

header() {
    echo ""
    echo -e "  ${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "  ${BOLD}${CYAN}║  $1$(printf '%*s' $((60 - ${#1})) '')║${RESET}"
    echo -e "  ${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Dependency Checks
# ─────────────────────────────────────────────────────────────────────────────

header "DEPENDENCY CHECK"

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON_VER=$(python3 --version 2>&1)
    ok "Python3 found: ${PYTHON_VER}"
else
    err "Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check demo script
if [[ -f "${DEMO_SCRIPT}" ]]; then
    ok "Demo script found: ${DEMO_SCRIPT}"
else
    err "Demo script not found: ${DEMO_SCRIPT}"
    exit 1
fi

# Check asciinema
HAS_ASCIINEMA=false
if command -v asciinema &>/dev/null; then
    ASCIINEMA_VER=$(asciinema --version 2>&1 || echo "unknown")
    ok "asciinema found: ${ASCIINEMA_VER}"
    HAS_ASCIINEMA=true
else
    warn "asciinema not found."
    echo -e "    ${DIM}Install with: brew install asciinema${RESET}"
    echo -e "    ${DIM}Or:           pip install asciinema${RESET}"
    echo -e "    ${DIM}Or:           sudo apt install asciinema${RESET}"
    echo ""
    warn "Will run demo without recording."
fi

# Check agg (asciinema gif generator)
HAS_AGG=false
if command -v agg &>/dev/null; then
    ok "agg (asciinema gif generator) found"
    HAS_AGG=true
else
    warn "agg not found (used for GIF generation)"
    echo -e "    ${DIM}Install with: cargo install agg${RESET}"
    echo -e "    ${DIM}Or:           brew install agg${RESET}"
fi

# Check svg-term (fallback for GIF)
HAS_SVG_TERM=false
if command -v svg-term &>/dev/null; then
    ok "svg-term found (fallback renderer)"
    HAS_SVG_TERM=true
else
    if [[ "${HAS_AGG}" == "false" ]]; then
        warn "svg-term not found (fallback renderer)"
        echo -e "    ${DIM}Install with: npm install -g svg-term-cli${RESET}"
    fi
fi

# Check Rust compiler (optional, for Rust demo)
HAS_RUSTC=false
if command -v rustc &>/dev/null; then
    RUSTC_VER=$(rustc --version 2>&1)
    ok "Rust compiler found: ${RUSTC_VER}"
    HAS_RUSTC=true
else
    warn "rustc not found — Rust demo will be skipped"
    echo -e "    ${DIM}Install with: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh${RESET}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Create recordings directory
# ─────────────────────────────────────────────────────────────────────────────

mkdir -p "${RECORDINGS_DIR}"
ok "Recordings directory: ${RECORDINGS_DIR}"

# ─────────────────────────────────────────────────────────────────────────────
# Compile Rust solver (if available)
# ─────────────────────────────────────────────────────────────────────────────

if [[ "${HAS_RUSTC}" == "true" && -f "${RUST_SRC}" ]]; then
    header "COMPILING RUST SOLVER"
    info "Compiling ${RUST_SRC}..."
    if rustc -o "${RUST_BIN}" "${RUST_SRC}" 2>&1; then
        ok "Rust solver compiled: ${RUST_BIN}"
    else
        warn "Rust compilation failed — skipping Rust demo"
        HAS_RUSTC=false
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Run / Record Demo Iterations
# ─────────────────────────────────────────────────────────────────────────────

NUM_ITERATIONS=5

header "RUNNING DEMO (${NUM_ITERATIONS} iterations)"

for i in $(seq 1 ${NUM_ITERATIONS}); do
    echo ""
    info "━━━ Recording iteration ${i}/${NUM_ITERATIONS} ━━━"

    CAST_FILE="${RECORDINGS_DIR}/demo_iter_${i}_${TIMESTAMP}.cast"

    if [[ "${HAS_ASCIINEMA}" == "true" ]]; then
        info "Recording to: ${CAST_FILE}"
        asciinema rec \
            --title "Tesla Pipeline Demo — Iteration ${i}/${NUM_ITERATIONS}" \
            --idle-time-limit 2 \
            --command "python3 ${DEMO_SCRIPT}" \
            "${CAST_FILE}" \
            2>&1

        if [[ -f "${CAST_FILE}" ]]; then
            CAST_SIZE=$(wc -c < "${CAST_FILE}" | tr -d ' ')
            ok "Recorded: ${CAST_FILE} (${CAST_SIZE} bytes)"
        else
            warn "Recording file not created for iteration ${i}"
        fi
    else
        info "Running without recording (iteration ${i})..."
        python3 "${DEMO_SCRIPT}"
        ok "Iteration ${i} completed (not recorded)"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Run Rust solver (if compiled)
# ─────────────────────────────────────────────────────────────────────────────

if [[ "${HAS_RUSTC}" == "true" && -f "${RUST_BIN}" ]]; then
    header "RUNNING RUST SOLVER"

    RUST_CAST="${RECORDINGS_DIR}/rust_solver_${TIMESTAMP}.cast"

    if [[ "${HAS_ASCIINEMA}" == "true" ]]; then
        info "Recording Rust solver..."
        asciinema rec \
            --title "ExactRationalWitness Rust Verifier" \
            --idle-time-limit 2 \
            --command "${RUST_BIN}" \
            "${RUST_CAST}" \
            2>&1

        ok "Rust solver recorded: ${RUST_CAST}"
    else
        "${RUST_BIN}"
        ok "Rust solver completed (not recorded)"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Generate GIF / SVG from recordings
# ─────────────────────────────────────────────────────────────────────────────

if [[ "${HAS_ASCIINEMA}" == "true" ]]; then
    header "GENERATING OUTPUT MEDIA"

    # Use the first recording as the showcase
    SHOWCASE_CAST=$(ls -t "${RECORDINGS_DIR}"/demo_iter_1_*.cast 2>/dev/null | head -1)

    if [[ -n "${SHOWCASE_CAST}" ]]; then
        if [[ "${HAS_AGG}" == "true" ]]; then
            GIF_OUTPUT="${RECORDINGS_DIR}/demo_showcase.gif"
            info "Generating GIF with agg..."
            agg \
                --font-size 14 \
                --cols 100 \
                --rows 40 \
                --theme monokai \
                "${SHOWCASE_CAST}" \
                "${GIF_OUTPUT}" \
                2>&1 && ok "GIF created: ${GIF_OUTPUT}" || warn "GIF generation failed"

        elif [[ "${HAS_SVG_TERM}" == "true" ]]; then
            SVG_OUTPUT="${RECORDINGS_DIR}/demo_showcase.svg"
            info "Generating SVG with svg-term..."
            svg-term \
                --in "${SHOWCASE_CAST}" \
                --out "${SVG_OUTPUT}" \
                --window \
                --width 100 \
                --height 40 \
                2>&1 && ok "SVG created: ${SVG_OUTPUT}" || warn "SVG generation failed"
        else
            warn "No GIF/SVG generator available. Cast files are in ${RECORDINGS_DIR}/"
            info "Install agg or svg-term to generate visual output."
        fi
    else
        warn "No cast files found for media generation"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# Generate DEMO_README.md
# ─────────────────────────────────────────────────────────────────────────────

header "GENERATING DEMO README"

README_FILE="${SCRIPT_DIR}/DEMO_README.md"

cat > "${README_FILE}" << 'HEREDOC_README'
# 🚀 Tesla Prototyping Pipeline — Demo

## Overview

This demo showcases three verified inventions from the **ExactRationalWitness.lean** and **Q-arithmetic** formal verification framework:

| # | Invention | Key Concept | Verification |
|---|-----------|-------------|--------------|
| 1 | **Safe Motion Planning** | Hypercube safety corridors | Trajectory containment in rational bounds |
| 2 | **HFT Deterministic Execution** | Exact rational price bounds | Zero-rounding VWAP & exposure limits |
| 3 | **Telesurgery Force-Feedback** | Force vector verification | Tissue threshold compliance |

## Quick Start

### Python Demo (recommended)

```bash
# Run the full demo (5 iterations)
python3 demo/demo_prototype.py
```

### Rust Verifier

```bash
# Compile and run the Rust verifier
rustc demo/demo_rust_solver.rs -o demo/demo_rust_solver
./demo/demo_rust_solver
```

### Record a Demo Session

```bash
# Record with asciinema + generate GIF
bash demo/record_demo.sh
```

## Prerequisites

### Required
- **Python 3.8+** — Only stdlib modules used (`fractions`, `decimal`, `math`, `time`, `sys`, `os`)

### Optional
- **Rust** — For the Rust verifier (`rustc`)
- **asciinema** — For recording terminal sessions (`brew install asciinema`)
- **agg** — For generating GIF from recordings (`cargo install agg`)
- **svg-term** — Fallback SVG renderer (`npm install -g svg-term-cli`)

## Architecture

```
demo/
├── demo_prototype.py      # Main Python demo — exact rational arithmetic
├── demo_rust_solver.rs     # Rust verifier — integer arithmetic
├── record_demo.sh          # Recording & media generation script
├── DEMO_README.md          # This file
└── recordings/             # asciinema recordings & generated media
    ├── demo_iter_*.cast    # Raw asciinema recordings
    ├── rust_solver_*.cast  # Rust solver recording
    ├── demo_showcase.gif   # Generated GIF (if agg installed)
    └── demo_showcase.svg   # Generated SVG (if svg-term installed)
```

## Key Design Principles

### Exact Rational Arithmetic
All numeric computations use **exact rational numbers** (`fractions.Fraction` in Python, `i128` rationals in Rust). This eliminates floating-point rounding errors that could compromise safety-critical systems.

### No External Dependencies
- Python demo uses **only stdlib** — no pip packages required
- Rust demo compiles with **rustc alone** — no Cargo dependencies
- No API calls, no LLM calls, no network access

### Formal Verification Bridge
The demos implement simplified versions of the invariants proven in `ExactRationalWitness.lean`:
- **Hypercube containment**: ∀ waypoint w ∈ trajectory, lo ≤ w ≤ hi (component-wise)
- **Corridor separation**: ∃ axis i, corridor_a.hi[i] < corridor_b.lo[i]
- **Force bound**: |F|² ≤ threshold² (avoids irrational sqrt)
- **Price determinism**: VWAP(trades) = VWAP(reverse(trades)) (exact equality)

## Sample Output

The demo produces colorful terminal output with:
- `[PASS]` in green for passing verifications
- `[FAIL]` in red for detected violations
- Exact rational values (e.g., `7/12`) alongside float approximations
- Progress bars and ASCII art headers
- A final summary table with pass rates

## Recordings

After running `record_demo.sh`, recordings are saved to `demo/recordings/`. You can:

```bash
# Replay a recording
asciinema play demo/recordings/demo_iter_1_*.cast

# Upload to asciinema.org
asciinema upload demo/recordings/demo_iter_1_*.cast

# Generate GIF manually
agg demo/recordings/demo_iter_1_*.cast output.gif
```

---

*Generated by the Tesla Prototyping Pipeline demo system.*
HEREDOC_README

ok "DEMO_README.md created: ${README_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# Final Summary
# ─────────────────────────────────────────────────────────────────────────────

header "RECORDING COMPLETE"

echo -e "  ${BOLD}Files generated:${RESET}"
echo -e "    ${GREEN}✓${RESET} ${README_FILE}"

if [[ "${HAS_ASCIINEMA}" == "true" ]]; then
    CAST_COUNT=$(ls "${RECORDINGS_DIR}"/*.cast 2>/dev/null | wc -l | tr -d ' ')
    echo -e "    ${GREEN}✓${RESET} ${CAST_COUNT} asciinema recordings in ${RECORDINGS_DIR}/"
fi

if [[ -f "${RECORDINGS_DIR}/demo_showcase.gif" ]]; then
    echo -e "    ${GREEN}✓${RESET} ${RECORDINGS_DIR}/demo_showcase.gif"
fi

if [[ -f "${RECORDINGS_DIR}/demo_showcase.svg" ]]; then
    echo -e "    ${GREEN}✓${RESET} ${RECORDINGS_DIR}/demo_showcase.svg"
fi

if [[ "${HAS_RUSTC}" == "true" && -f "${RUST_BIN}" ]]; then
    echo -e "    ${GREEN}✓${RESET} ${RUST_BIN} (compiled)"
fi

echo ""
echo -e "  ${DIM}To replay: asciinema play ${RECORDINGS_DIR}/demo_iter_1_*.cast${RESET}"
echo -e "  ${DIM}To view:   cat ${README_FILE}${RESET}"
echo ""
