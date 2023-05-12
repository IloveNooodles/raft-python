use std::{
    collections::VecDeque,
    sync::{Arc, Mutex},
};

#[derive(Clone)]
pub struct AppState {
    queue: Arc<Mutex<VecDeque<String>>>,
}

impl AppState {
    pub fn new() -> AppState {
        AppState {
            queue: Arc::new(Mutex::new(VecDeque::new())),
        }
    }
}

pub enum Message {}
