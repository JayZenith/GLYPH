use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Config {
    endpoint: String,
    retries: u32,
    verbose: bool,
    timeout: u32,
    tags: Vec<String>,
}

fn parse_kv(input: &str) -> HashMap<String, String> {
    let mut map = HashMap::new();
    for line in input.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            map.insert(k.trim().to_string(), v.trim().to_string());
        }
    }
    map
}

fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "1" | "yes" | "on" => Some(true),
        "false" | "0" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn parse_tags(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim().to_string())
        .filter(|p| !p.is_empty())
        .collect()
}

fn merge(defaults: Config, env: &HashMap<String, String>, file: &HashMap<String, String>, cli: &HashMap<String, String>) -> Config {
    let mut cfg = defaults.clone();

    if let Some(v) = env.get("endpoint") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }
    if let Some(v) = file.get("endpoint") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }
    if let Some(v) = cli.get("endpoint") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }

    if let Some(v) = env.get("retries").and_then(|v| v.parse::<u32>().ok()) {
        if v > 0 {
            cfg.retries = v;
        }
    }
    if let Some(v) = file.get("retries").and_then(|v| v.parse::<u32>().ok()) {
        if v > 0 {
            cfg.retries = v;
        }
    }
    if let Some(v) = cli.get("retries").and_then(|v| v.parse::<u32>().ok()) {
        if v > 0 {
            cfg.retries = v;
        }
    }

    if let Some(v) = env.get("verbose").and_then(|v| parse_bool(v)) {
        if v {
            cfg.verbose = v;
        }
    }
    if let Some(v) = file.get("verbose").and_then(|v| parse_bool(v)) {
        if v {
            cfg.verbose = v;
        }
    }
    if let Some(v) = cli.get("verbose").and_then(|v| parse_bool(v)) {
        if v {
            cfg.verbose = v;
        }
    }

    if let Some(v) = env.get("timeout").and_then(|v| v.parse::<u32>().ok()) {
        cfg.timeout = v;
    }
    if let Some(v) = file.get("timeout").and_then(|v| v.parse::<u32>().ok()) {
        cfg.timeout = v;
    }
    if let Some(v) = cli.get("timeout").and_then(|v| v.parse::<u32>().ok()) {
        cfg.timeout = v;
    }

    if let Some(v) = env.get("tags") {
        let parsed = parse_tags(v);
        if !parsed.is_empty() {
            cfg.tags.extend(parsed);
        }
    }
    if let Some(v) = file.get("tags") {
        let parsed = parse_tags(v);
        if !parsed.is_empty() {
            cfg.tags = parsed;
        }
    }
    if let Some(v) = cli.get("tags") {
        let parsed = parse_tags(v);
        if !parsed.is_empty() {
            cfg.tags.extend(parsed);
        }
    }

    cfg
}

fn render(cfg: &Config) -> String {
    format!(
        "endpoint={}\nretries={}\nverbose={}\ntimeout={}\ntags=[{}]",
        cfg.endpoint,
        cfg.retries,
        cfg.verbose,
        cfg.timeout,
        cfg.tags.join(",")
    )
}

fn main() {
    let defaults = Config {
        endpoint: "https://default.service".to_string(),
        retries: 2,
        verbose: true,
        timeout: 30,
        tags: vec!["base".to_string(), "stable".to_string()],
    };

    let env = parse_kv(
        "endpoint=https://env.service
retries=4
verbose=true
timeout=40
tags=env1,env2",
    );
    let file = parse_kv(
        "endpoint=https://file.service
retries=0
verbose=false
timeout=45
tags=ops,canary",
    );
    let cli = parse_kv(
        "endpoint=
verbose=false
tags=",
    );

    let cfg = merge(defaults, &env, &file, &cli);
    println!("{}", render(&cfg));
}
