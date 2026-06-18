# NVIDIA Scientific AI Integrations

This module provides Python interfaces to NVIDIA NIM (NVIDIA Inference
Microservices) endpoints for scientific computing.

## Supported Models

| Module | Model | Use Case |
|--------|-------|----------|
| `bionemo/` | ESM2 | Protein structure prediction & embeddings |
| `earth2/` | FourCastNet | Global weather forecasting (0.25° res) |
| `modulus/` | Navier–Stokes | Physics-informed neural PDE solving |

## Architecture

Each module provides:
- **Model interface** — High-level API for the NIM endpoint
- **Validator** — Physics/domain-specific input/output validation

## Requirements

- `NVIDIA_NIM_API_KEY` environment variable
- `NVIDIA_NIM_API_BASE` (default: `https://integrate.api.nvidia.com/v1`)

## Patent

US-PAT-PEND-2026-0525 — Neuro-symbolic scientific AI framework.
