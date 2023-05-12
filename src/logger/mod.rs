use env_logger::Env;
use log::{error, info};

pub fn init_logger() {
    env_logger::Builder::from_env(Env::default().default_filter_or("info")).init();
}

pub fn log_info(s: &str) {
    info!("[INFO] {:#?}", s)
}

pub fn log_error(s: &str) {
    error!("[ERROR] {:#?}", s)
}
