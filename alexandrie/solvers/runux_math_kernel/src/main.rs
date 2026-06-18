// Copyright (c) 2026 Xavier Callens and Socrate AI. All rights reserved.
// Released under Apache 2.0 license.
// Runux Math Kernel - API Gateway & Hexagonal Architecture Core

mod solvers;

use axum::{
    extract::Json,
    routing::{post, get},
    Router,
};
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tower_http::cors::{Any, CorsLayer};
use std::fmt::Debug;

/// Hexagonal port for mathematical solvers
pub trait MathematicalSolver {
    type Problem: Debug;
    type Solution: Serialize + Debug;

    fn solve(&self, problem: &Self::Problem) -> Result<Self::Solution, String>;
}

// --- API Gateway Models ---

#[derive(Deserialize)]
struct KnRequest {
    n: u32,
}

#[derive(Deserialize)]
struct CalabiYauRequest {
    manifold_id: String,
}

// --- API Handlers ---

async fn solve_kn_crossing(Json(payload): Json<KnRequest>) -> Json<serde_json::Value> {
    let solver = solvers::kn_crossing::ZarankiewiczSolver::new();
    match solver.solve(&payload.n) {
        Ok(res) => Json(serde_json::to_value(res).unwrap()),
        Err(e) => Json(serde_json::json!({ "error": e })),
    }
}

async fn solve_calabi_yau(Json(payload): Json<CalabiYauRequest>) -> Json<serde_json::Value> {
    let solver = solvers::calabi_yau::PeriodexIntegrator::new();
    match solver.solve(&payload.manifold_id) {
        Ok(res) => Json(serde_json::to_value(res).unwrap()),
        Err(e) => Json(serde_json::json!({ "error": e })),
    }
}

async fn health_check() -> &'static str {
    "Runux Math Kernel API Gateway is running!"
}

#[tokio::main]
async fn main() {
    println!("--- Runux Math Kernel API Gateway ---");
    println!("Copyright (c) 2026 Xavier Callens and Socrate AI.");

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/", get(health_check))
        .route("/api/solve/kn_crossing", post(solve_kn_crossing))
        .route("/api/solve/calabi_yau", post(solve_calabi_yau))
        .layer(cors);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    println!("Listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
