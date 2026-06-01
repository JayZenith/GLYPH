struct Config {
    host: String,
    port: u16,
    tls: bool,
    retries: u8,
    timeout_ms: u32,
}

fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "1" | "yes" => Some(true),
        "false" | "0" | "no" => Some(false),
        _ => None,
    }
}

fn main() {
    let default = Config {
        host: "localhost".to_string(),
        port: 8080,
        tls: false,
        retries: 2,
        timeout_ms: 1000,
    };

    let file_cfg = Config {
        host: "db.internal".to_string(),
        port: 5432,
        tls: false,
        retries: 4,
        timeout_ms: 2500,
    };

    let env_host = Some("db.prod.local");
    let env_port = None::<u16>;
    let env_tls = Some("true");
    let env_retries = Some(0u8);
    let env_timeout = Some(0u32);

    let cli_host = None::<&str>;
    let cli_port = Some(7000u16);
    let cli_tls = None::<&str>;
    let cli_retries = Some(5u8);
    let cli_timeout = None::<u32>;

    let host = default.host.clone();
    let port = env_port.unwrap_or(file_cfg.port);
    let tls = parse_bool(cli_tls.unwrap_or("false")).unwrap_or(default.tls);
    let retries = env_retries.unwrap_or(cli_retries.unwrap_or(default.retries));
    let timeout_ms = env_timeout.unwrap_or(file_cfg.timeout_ms);

    println!("host={}", host);
    println!("port={}", port);
    println!("tls={}", tls);
    println!("retries={}", retries);
    println!("timeout_ms={}", timeout_ms);
}
