# SocrateAI Scientific Agora — Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Google Cloud Platform               │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Socrates  │  │ Galileo  │  │  Euler   │       │
│  │ Cloud Run │  │ Cloud Run│  │ Cloud Run│       │
│  │ min=0     │  │ min=0    │  │ min=0    │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────┴──────────────┴──────────────┴────┐       │
│  │          GCS Checkpoint Storage        │       │
│  └───────────────────────────────────────┘       │
│                                                   │
│  Budget Alerts: $50 / $100 / $500                │
└─────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

```bash
# Install tools
brew install terraform google-cloud-sdk docker

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Terraform Deployment

```bash
cd deploy/terraform
terraform init
terraform plan -var="project_id=YOUR_PROJECT_ID"
terraform apply -var="project_id=YOUR_PROJECT_ID"
```

### 3. Docker Local Development

```bash
cd deploy/docker
docker-compose up --build
```

### 4. Kubernetes (Advanced)

See `deploy/k8s/README.md` for Kubernetes deployment on GKE.

## Budget Policy

| Constraint | Limit |
|-----------|-------|
| Per experiment | $100 |
| Project total | $500 |
| min_replicas | 0 (mandatory) |
| GPU type | L4 (default) |
| Region | us-central1 |

## Container Images

| Image | Purpose | Base |
|-------|---------|------|
| `Dockerfile.agent` | Python agents | python:3.11-slim |
| `Dockerfile.solver` | rusty-SUNDIALS | rust:1.79 → debian:slim |

## Patent

US-PAT-PEND-2026-0525
