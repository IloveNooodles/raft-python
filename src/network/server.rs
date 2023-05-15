
use std::{
    collections::HashMap,
    net::{IpAddr, Ipv4Addr, SocketAddr},
};

use axum::{
    body::{Body, Bytes},
    extract::{Extension, Json, Path, Query},
    headers::UserAgent,
    http::{HeaderMap, Request, StatusCode},
    middleware::Next,
    response::IntoResponse,
    routing::get,
    routing::post,
    Router, TypedHeader,
};

use serde_json::{json, Value};
use log::{error, info};
// FIXME: awkward import
use super::super::logger;

/// Example tokio server
pub async fn create(port: u16) {
    // let mut state = mq::AppState::new();
    logger::init_logger();

    // let app = Router::new()
    //     .route("/", get(route_get_handler))
    //     .route("/enqueue", post(enqueue))
    //     .route("/dequeue", post(dequeue));
    let app = Router::new()
        .route("/", get(route_get_handler))
        .route("/path/:user_id", post(path))
        .route("/query", post(query))
        .route("/user_agent", post(user_agent))
        .route("/headers", post(headers))
        .route("/string", post(string))
        .route("/bytes", post(bytes))
        .route("/json", post(json))
        .route("/request", post(request))
        .route("/extension", post(extension));

    let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)), port);

    println!("Server listening on {}", addr);
    
    axum::Server::bind(&addr)
        .serve(app.into_make_service())
        .await
        .unwrap()

}

async fn route_get_handler(req: Request<Body>) -> Result<Json<Value>, StatusCode> {
    let some_condition = true;
    // logger::log_info(req);
    info!("[INFO] {:#?}", req);
    if some_condition {
        return Ok(Json(json!({
          "Message": "Hello from node!"
        })));
    }

    return Err(StatusCode::INTERNAL_SERVER_ERROR);
}

// async fn enqueue() -> impl IntoResponse {
//     "Hi from axum"
// }

// async fn dequeue() -> impl IntoResponse {
//     "Hi from axum"
// }

// `Path` gives you the path parameters and deserializes them. See its docs for
// more details
async fn path(Path(user_id): Path<u32>) {}

// `Query` gives you the query parameters and deserializes them.
async fn query(Query(params): Query<HashMap<String, String>>) {}

// `HeaderMap` gives you all the headers
async fn headers(headers: HeaderMap) {}

// `TypedHeader` can be used to extract a single header
// note this requires you've enabled axum's `headers` feature
async fn user_agent(TypedHeader(user_agent): TypedHeader<UserAgent>) {}

// `String` consumes the request body and ensures it is valid utf-8
async fn string(body: String) {}

// `Bytes` gives you the raw request body
async fn bytes(body: Bytes) {}

// We've already seen `Json` for parsing the request body as json
async fn json(Json(payload): Json<Value>) {}

// `Request` gives you the whole request for maximum control
async fn request(request: Request<Body>) {}

// `Extension` extracts data from "request extensions"
// This is commonly used to share state with handlers
async fn extension(Extension(state): Extension<State>) {}

#[derive(Clone)]
struct State {/* ... */}
