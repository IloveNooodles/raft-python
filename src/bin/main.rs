use axum::{routing::get, routing::post, Router, Server};
use log::Level;
use raft_consensus::{client, logger, mq, network};
use std::{net::SocketAddr, sync::Arc};

/// Example tokio server
#[tokio::main]
async fn main() {
    // let mut state = mq::AppState::new();

    let router = Router::new()
        .route("/", get(route_get_handler))
        .route("/enqueue", post(enqueue))
        .route("/dequeue", post(dequeue));

    let server = Server::bind(&"0.0.0.0:8080".parse().unwrap()).serve(router.into_make_service());

    let sock_addr: SocketAddr = server.local_addr();
    println!("{:#?}", sock_addr);

    /* Serve server */
    server.await.unwrap();

    println!("Hello, world!");
}

async fn route_get_handler() -> &'static str {
    "Hi from axum"
}

async fn enqueue() -> &'static str {
    "Hi from axum"
}

async fn dequeue() -> &'static str {
    "Hi from axum"
}
