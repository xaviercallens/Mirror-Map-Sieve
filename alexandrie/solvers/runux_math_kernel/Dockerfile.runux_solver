# Copyright (c) 2026 Xavier Callens and Socrate AI. All rights reserved.
# Multistage Dockerfile to produce a minimal scratch image for the Rust kernel.

# Stage 1: Build
FROM rust:1.82-slim-bullseye AS builder

WORKDIR /usr/src/runux_math_kernel
COPY . .

# Build for release, statically linking libc
RUN cargo build --release

# Stage 2: Minimal Runtime
FROM debian:bullseye-slim

WORKDIR /app
COPY --from=builder /usr/src/runux_math_kernel/target/release/runux_math_kernel .

# Environment variables for execution
ENV RUST_LOG=info

ENTRYPOINT ["./runux_math_kernel"]
