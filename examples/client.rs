use reqwest::{Error, Response};

#[tokio::main]
async fn main() {
    let client = reqwest::Client::new();
    /* GET */
    let body = reqwest::get("http://localhost:8000/").await;

    let result = match body {
        Err(e) => {
            println!("{:#?}", e);
            String::new()
        }
        Ok(res) => res.text().await.unwrap_or_default(),
    };

    println!("body = {:?}", result);

    /* POST */
    let res = client
        .post("http://localhost:8000/path/1231231")
        .body("THIS IS BODY")
        .send()
        .await;

    match res {
        Err(e) => println!("{:#?}", e),
        Ok(a) => println!("{:#?}", a),
    }
}
