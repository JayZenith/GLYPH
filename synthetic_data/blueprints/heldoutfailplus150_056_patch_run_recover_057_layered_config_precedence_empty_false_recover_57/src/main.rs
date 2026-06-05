use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Config {
    mode: String,
    endpoint: String,
    color: bool,
    retries: u32,
    labels: Vec<String>,
}

fn defaults() -> Config {
    Config {
        mode: "safe".to_string(),
        endpoint: "https://default.local".to_string(),
        color: true,
        retries: 3,
        labels: vec!["base".to_string()],
    }
}

fn parse_kv(input: &str) -> HashMap<String, String> {
    let mut map = HashMap::new();
    for line in input.lines() {
        if let Some((k, v)) = line.split_once('=') {
            map.insert(k.trim().to_string(), v.trim().to_string());
        }
    }
    map
}

fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "1" | "yes" | "on" => Some(true),
        _ => None,
    }
}

fn parse_u32(s: &str) -> Option<u32> {
    s.parse().ok()
}

fn parse_list(s: &str) -> Vec<String> {
    s.split(',')
        .map(|part| part.trim().to_string())
        .filter(|part| !part.is_empty())
        .collect()
}

fn merge(mut cfg: Config, file: &HashMap<String, String>, env: &HashMap<String, String>, cli: &HashMap<String, String>) -> Config {
    for src in [file, env, cli] {
        if let Some(v) = src.get("mode") {
            if !v.is_empty() {
                cfg.mode = v.clone();
            }
        }
        if let Some(v) = src.get("endpoint") {
            if !v.is_empty() {
                cfg.endpoint = v.clone();
            }
        }
        if let Some(v) = src.get("color") {
            if let Some(b) = parse_bool(v) {
                if b {
                    cfg.color = b;
                }
            }
        }
        if let Some(v) = src.get("retries") {
            if let Some(n) = parse_u32(v) {
                if n > 0 {
                    cfg.retries = n;
                }
            }
        }
        if let Some(v) = src.get("labels") {
            let items = parse_list(v);
            if !items.is_empty() {
                cfg.labels.extend(items);
            }
        }
    }
    cfg
}

fn render(cfg: &Config) -> String {
    format!(
        "mode={}\nendpoint={}\ncolor={}\nretries={}\nlabels={}",
        cfg.mode,
        cfg.endpoint,
        cfg.color,
        cfg.retries,
        cfg.labels.join("|")
    )
}

fn main() {
    let file_cfg = parse_kv(
        "mode=file\nendpoint=https://file.local\ncolor=false\nretries=5\nlabels=fileA,fileB",
    );
    let env_cfg = parse_kv(
        "mode=debug\nendpoint=\ncolor=true\nretries=0\nlabels=",
    );
    let cli_cfg = parse_kv(
        "color=false\nlabels=cli1,cli2",
    );

    let cfg = merge(defaults(), &file_cfg, &env_cfg, &cli_cfg);
    println!("{}", render(&cfg));
}
