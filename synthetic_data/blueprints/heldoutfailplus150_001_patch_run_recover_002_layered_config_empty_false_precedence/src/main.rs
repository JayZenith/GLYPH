use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Config {
    profile: String,
    endpoint: String,
    retries: u32,
    debug: bool,
    timeout: u32,
    label: String,
}

#[derive(Clone, Debug, Default)]
struct PartialConfig {
    profile: Option<String>,
    endpoint: Option<String>,
    retries: Option<u32>,
    debug: Option<bool>,
    timeout: Option<u32>,
    label: Option<String>,
}

fn defaults() -> Config {
    Config {
        profile: "dev".to_string(),
        endpoint: "http://default".to_string(),
        retries: 3,
        debug: false,
        timeout: 30,
        label: "base".to_string(),
    }
}

fn parse_map(input: &str) -> HashMap<String, String> {
    let mut out = HashMap::new();
    for line in input.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            out.insert(k.trim().to_string(), v.trim().to_string());
        }
    }
    out
}

fn parse_bool(v: &str) -> Option<bool> {
    match v {
        "true" | "1" | "yes" | "on" => Some(true),
        "false" | "0" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn partial_from_map(map: &HashMap<String, String>, prefix: &str) -> PartialConfig {
    let get = |k: &str| map.get(&format!("{}{}", prefix, k)).cloned();
    PartialConfig {
        profile: get("profile").filter(|s| !s.is_empty()),
        endpoint: get("endpoint").filter(|s| !s.is_empty()),
        retries: get("retries").and_then(|s| s.parse().ok()).filter(|n| *n > 0),
        debug: get("debug").and_then(|s| parse_bool(&s)).filter(|b| *b),
        timeout: get("timeout").and_then(|s| s.parse().ok()),
        label: get("label").filter(|s| !s.is_empty()),
    }
}

fn merge(base: Config, layer: PartialConfig) -> Config {
    Config {
        profile: layer.profile.unwrap_or(base.profile),
        endpoint: layer.endpoint.unwrap_or(base.endpoint),
        retries: layer.retries.unwrap_or(base.retries),
        debug: layer.debug.unwrap_or(base.debug),
        timeout: base.timeout,
        label: layer.label.unwrap_or(base.label),
    }
}

fn render(cfg: &Config) -> String {
    format!(
        "profile={}\nendpoint={}\nretries={}\ndebug={}\ntimeout={}\nlabel={}",
        cfg.profile, cfg.endpoint, cfg.retries, cfg.debug, cfg.timeout, cfg.label
    )
}

fn main() {
    let defaults = defaults();

    let file1 = parse_map(
        "profile=prod
endpoint=http://file
retries=5
debug=true
timeout=90
label=file-tag",
    );
    let env1 = parse_map(
        "APP_ENDPOINT=
APP_RETRIES=0
APP_DEBUG=false
APP_LABEL=",
    );
    let cli1 = parse_map("");

    let file2 = parse_map(
        "profile=stage
endpoint=http://file2
retries=7
debug=false
timeout=45
label=file2",
    );
    let env2 = parse_map(
        "APP_PROFILE=dev
APP_ENDPOINT=http://env
APP_RETRIES=2
APP_DEBUG=false
APP_TIMEOUT=20
APP_LABEL=env-tag",
    );
    let cli2 = parse_map(
        "profile=
endpoint=http://cli
debug=true
label=cli-tag",
    );

    let cfg1 = merge(
        merge(merge(defaults.clone(), partial_from_map(&env1, "APP_")), partial_from_map(&file1, "")),
        partial_from_map(&cli1, ""),
    );
    let cfg2 = merge(
        merge(merge(defaults, partial_from_map(&env2, "APP_")), partial_from_map(&file2, "")),
        partial_from_map(&cli2, ""),
    );

    println!("{}\n---\n{}", render(&cfg1), render(&cfg2));
}
