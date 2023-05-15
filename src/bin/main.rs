use raft_consensus::{client, logger, mq, network};

/// Example tokio server
#[tokio::main]
async fn main() {
    network::server::create(8000).await;
}