#[tokio::main]
async fn main() {
    let body = reqwest::get("http://localhost:8000").await;

    let result = match body {
        Err(e) => {
            println!("{:#?}", e);
            String::new()
        }
        Ok(res) => res.text().await.unwrap_or_default(),
    };

    println!("body = {:?}", result);
}
