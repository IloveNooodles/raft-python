use axum::{routing::get, Router, Server};
use raft_consensus::client;
use raft_consensus::mq;
use raft_consensus::network;

use std::net::SocketAddr;
/// Example tokio server
///
#[tokio::main]
async fn main() {
    let router = Router::new().route("/", get(route_get_handler));

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

struct AppState {}
