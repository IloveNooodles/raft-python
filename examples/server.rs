use std::{
    collections::HashMap,
    net::{IpAddr, Ipv4Addr, SocketAddr},
};

use axum::{
    body::{Body, Bytes},
    extract::{Extension, Json, Path, Query},
    headers::UserAgent,
    http::{HeaderMap, Request, StatusCode},
    routing::get,
    routing::post,
    Router, TypedHeader,
};
use log::{error, info};
use raft_consensus::logger;
use serde_json::{json, Value};

/// Example tokio server
#[tokio::main]
async fn main() {
    logger::init_logger();

    let app = Router::new()
        .route("/", get(request))
        .route("/path/:user_id", post(path))
        .route("/query", post(query))
        .route("/user_agent", post(user_agent))
        .route("/headers", get(headers))
        .route("/string", post(string))
        .route("/bytes", post(bytes))
        .route("/json", post(json))
        .route("/extension", post(extension));

    let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)), 8000);

    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap()
}

async fn request(req: Request<Body>) -> Result<Json<Value>, StatusCode> {
    let some_condition = true;
    info!("[INFO] {:#?}", req);

    if some_condition {
        return Ok(Json(json!({
          "test": {
            "Gare": 1,
          }
        })));
    }

    return Err(StatusCode::INTERNAL_SERVER_ERROR);
}

// `Path` gives you the path parameters and deserializes them. See its docs for
// more details
async fn path(Path(user_id): Path<u32>) {
    info!("[INFO] {:#?}", user_id);
}

// `Query` gives you the query parameters and deserializes them.
async fn query(Query(params): Query<HashMap<String, String>>) {}

// `HeaderMap` gives you all the headers
async fn headers(headers: HeaderMap) {
    info!("[INFO] {:#?}", headers);
}

// `TypedHeader` can be used to extract a single header
// note this requires you've enabled axum's `headers` feature
async fn user_agent(TypedHeader(user_agent): TypedHeader<UserAgent>) {
    info!("[INFO] {:#?}", user_agent);
}

// `String` consumes the request body and ensures it is valid utf-8
async fn string(body: String) {
    info!("[INFO] {:#?}", body);
}

// `Bytes` gives you the raw request body
async fn bytes(body: Bytes) {
    info!("[INFO] {:#?}", body);
}

// We've already seen `Json` for parsing the request body as json
async fn json(Json(payload): Json<Value>) {
    info!("[INFO] {:#?}", payload);
}

// `Extension` extracts data from "request extensions"
// This is commonly used to share state with handlers
async fn extension(Extension(state): Extension<State>) {}

#[derive(Clone)]
struct State {/* ... */}
