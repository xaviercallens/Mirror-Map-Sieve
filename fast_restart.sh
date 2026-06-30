#!/usr/bin/env bash
# ==============================================================================
# Mirror Map Sieve — Fast Restart Script
# This script automates virtual environment recreation, dependency installation,
# Triton kernel verification, and optional benchmark/training re-execution.
# ==============================================================================

set -euo pipefail

# ANSI Color Codes for beautiful status logging
RED='\033[0.31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "Usage: ./fast_restart.sh [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message and exit"
    echo "  --setup-only    Only create virtual environment and install dependencies"
    echo "  --test          Run unit tests to verify Triton kernel correctness (default if no other flags)"
    echo "  --run-h13       Re-run the H13 task-specific slope training sweep"
    echo "  --run-h9        Re-run the H9 intermediate pruning prefill benchmarks"
    echo "  --all           Perform setup, verify Triton kernels, and run both H13 and H9 sweeps"
}

# Default flags
DO_SETUP=true
DO_TEST=false
DO_H13=false
DO_H9=false

# Parse arguments
if [ $# -eq 0 ]; then
    DO_TEST=true
else
    while [[ $# -gt 0 ]]; do
        key="$1"
        case $key in
            -h|--help)
                show_help
                exit 0
                ;;
            --setup-only)
                DO_SETUP=true
                DO_TEST=false
                DO_H13=false
                DO_H9=false
                shift
                ;;
            --test)
                DO_TEST=true
                shift
                ;;
            --run-h13)
                DO_H13=true
                shift
                ;;
            --run-h9)
                DO_H9=true
                shift
                ;;
            --all)
                DO_TEST=true
                DO_H13=true
                DO_H9=true
                shift
                ;;
            *)
                log_error "Unknown argument: $1"
                show_help
                exit 1
                ;;
        esac
    done
fi

# Ensure we are in the repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ==============================================================================
# Step 1: Python Virtual Environment Setup
# ==============================================================================
if [ "$DO_SETUP" = true ]; then
    log_info "Initializing Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        log_info "No virtual environment found. Creating 'venv' directory..."
        python3 -m venv venv
    else
        log_info "Existing virtual environment 'venv' detected."
    fi

    # Activate the virtual environment
    log_info "Activating virtual environment..."
    # shellcheck disable=SC1091
    source venv/bin/activate

    log_info "Upgrading pip..."
    pip install --upgrade pip

    log_info "Installing dependencies from 4_ai_hardware_attention/requirements-gpu.txt..."
    if [ -f "4_ai_hardware_attention/requirements-gpu.txt" ]; then
        pip install -r 4_ai_hardware_attention/requirements-gpu.txt
        log_success "Dependencies installed successfully."
    else
        log_error "requirements-gpu.txt not found at 4_ai_hardware_attention/requirements-gpu.txt!"
        exit 1
    fi
else
    # If setup is skipped, still attempt to activate venv if it exists
    if [ -d "venv" ]; then
        # shellcheck disable=SC1091
        source venv/bin/activate
    else
        log_warn "No virtual environment found; running commands using host Python."
    fi
fi

# ==============================================================================
# Step 2: Verification of Triton Kernels
# ==============================================================================
if [ "$DO_TEST" = true ]; then
    log_info "Running pytest suite to verify learnable ALiBi Triton kernel correctness..."
    if command -v pytest &> /dev/null; then
        pytest 4_ai_hardware_attention/test_cy_sieve_triton.py
        log_success "Triton kernel verified successfully against PyTorch reference."
    else
        log_error "pytest is not installed or virtual environment is not activated correctly."
        exit 1
    fi
fi

# ==============================================================================
# Step 3: Re-Running the H13 comparative training sweep
# ==============================================================================
if [ "$DO_H13" = true ]; then
    log_info "Launching H13 task-specific slope training sweep..."
    if [ -f "4_ai_hardware_attention/h13_comparative_training.py" ]; then
        python3 4_ai_hardware_attention/h13_comparative_training.py
        log_success "H13 comparative training sweep completed. Outputs:"
        echo "  - Log: 4_ai_hardware_attention/h13.log"
        echo "  - Raw metrics: 4_ai_hardware_attention/h13_results.json"
    else
        log_error "h13_comparative_training.py not found!"
        exit 1
    fi
fi

# ==============================================================================
# Step 4: Re-Running the H9 intermediate pruning prefill benchmarks
# ==============================================================================
if [ "$DO_H9" = true ]; then
    log_info "Launching H9 intermediate layer pruning prefill benchmarks..."
    if [ -f "4_ai_hardware_attention/h9_pruning_benchmark.py" ]; then
        python3 4_ai_hardware_attention/h9_pruning_benchmark.py
        log_success "H9 pruning prefill benchmark completed. Outputs:"
        echo "  - Log: 4_ai_hardware_attention/h9.log"
        echo "  - Raw metrics: 4_ai_hardware_attention/h9_results.json"
    else
        log_error "h9_pruning_benchmark.py not found!"
        exit 1
    fi
fi

log_success "Fast restart process completed."
