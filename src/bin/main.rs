use raft_consensus::{client, logger, mq, network};
use std::env;

/// Example tokio server
#[tokio::main]
async fn main() {
    let args: Vec<String> = env::args().collect();

    match args.len() {
        1 => {
            println!("Please specify a command");
            std::process::exit(1);
        },
        2 => {
            println!("Please specify the port number");
            std::process::exit(1);
        }
        3 => {
            match args[1].as_str() {
                "server" => {
                    match args[2].parse::<u16>() {
                        Ok(port) => {
                            network::server::start_server(port).await;
                        },
                        Err(_) => {
                            println!("Invalid port number");
                            std::process::exit(1);
                        }
                    }
                },
                _ => {
                    println!("Unknown command");
                    std::process::exit(1);
                }
            }
        }
        _ => {
            println!("Too many arguments");
            std::process::exit(1);
        }
    }

}