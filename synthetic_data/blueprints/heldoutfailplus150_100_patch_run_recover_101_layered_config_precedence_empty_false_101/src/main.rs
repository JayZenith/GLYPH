use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Config {
    endpoint: String,
    retries: u32,
    debug: bool,
    features: Vec<String>,
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
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn parse_features(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .map(|p| p.to_string())
        .collect()
}

fn merge(
    defaults: Config,
    file: &HashMap<String, String>,
    env: &HashMap<String, String>,
    cli: &HashMap<String, String>,
) -> Config {
    let mut cfg = defaults;

    if let Some(v) = file.get("endpoint") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }
    if let Some(v) = file.get("retries") {
        if let Ok(n) = v.parse::<u32>() {
            cfg.retries = n;
        }
    }
    if let Some(v) = file.get("debug") {
        if let Some(b) = parse_bool(v) {
            cfg.debug = b;
        }
    }
    if let Some(v) = file.get("features") {
        let parsed = parse_features(v);
        if !parsed.is_empty() {
            cfg.features = parsed;
        }
    }

    if let Some(v) = env.get("APP_ENDPOINT") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }
    if let Some(v) = env.get("APP_RETRIES") {
        if let Ok(n) = v.parse::<u32>() {
            if n > 0 {
                cfg.retries = n;
            }
        }
    }
    if let Some(v) = env.get("APP_DEBUG") {
        if let Some(b) = parse_bool(v) {
            if b {
                cfg.debug = true;
            }
        }
    }
    if let Some(v) = env.get("APP_FEATURES") {
        let parsed = parse_features(v);
        if !parsed.is_empty() {
            cfg.features.extend(parsed);
        }
    }

    if let Some(v) = cli.get("endpoint") {
        if !v.is_empty() {
            cfg.endpoint = v.clone();
        }
    }
    if let Some(v) = cli.get("retries") {
        if let Ok(n) = v.parse::<u32>() {
            if n > 0 {
                cfg.retries = n;
            }
        }
    }
    if let Some(v) = cli.get("debug") {
        if let Some(b) = parse_bool(v) {
            if b {
                cfg.debug = true;
            }
        }
    }
    if let Some(v) = cli.get("features") {
        let parsed = parse_features(v);
        if !parsed.is_empty() {
            cfg.features = parsed;
        }
    }

    cfg
}

fn main() {
    let defaults = Config {
        endpoint: "https://default.service".to_string(),
        retries: 3,
        debug: false,
        features: vec!["base".to_string()],
    };

    let file = parse_kv(
        "endpoint=https://file.service
retries=5
debug=true
features=file-a,file-b",
    );
    let env = parse_kv(
        "APP_ENDPOINT=https://env.service
APP_RETRIES=0
APP_DEBUG=false
APP_FEATURES=env-a,env-b",
    );
    let cli = parse_kv(
        "endpoint=
retries=0
debug=false
features=cli-only",
    );

    let cfg = merge(defaults, &file, &env, &cli);
    println!(
        "endpoint={}\nretries={}\ndebug={}\nfeatures={}",
        cfg.endpoint,
        cfg.retries,
        cfg.debug,
        cfg.features.join(",")
    );
}
