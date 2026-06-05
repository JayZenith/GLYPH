use std::collections::BTreeMap;

#[derive(Clone, Debug, Default)]
struct Config {
    mode: Option<String>,
    timeout: Option<u32>,
    verbose: Option<bool>,
    profile: Option<String>,
}

fn parse_pairs(s: &str) -> BTreeMap<String, String> {
    let mut map = BTreeMap::new();
    for part in s.split(';') {
        if part.is_empty() {
            continue;
        }
        let mut it = part.splitn(2, '=');
        let k = it.next().unwrap_or("").trim();
        let v = it.next().unwrap_or("").trim();
        if !k.is_empty() {
            map.insert(k.to_string(), v.to_string());
        }
    }
    map
}

fn parse_config(s: &str) -> Config {
    let m = parse_pairs(s);
    Config {
        mode: m.get("mode").filter(|v| !v.is_empty()).cloned(),
        timeout: m.get("timeout").and_then(|v| v.parse::<u32>().ok()).filter(|v| *v > 0),
        verbose: m.get("verbose").and_then(|v| match v.as_str() {
            "true" => Some(true),
            "false" => Some(false),
            _ => None,
        }),
        profile: m.get("profile").filter(|v| !v.is_empty()).cloned(),
    }
}

fn merge(base: Config, overlay: Config) -> Config {
    Config {
        mode: overlay.mode.or(base.mode),
        timeout: overlay.timeout.or(base.timeout),
        verbose: overlay.verbose.or(base.verbose),
        profile: overlay.profile.or(base.profile),
    }
}

fn main() {
    let defaults = parse_config("mode=standard;timeout=30;verbose=true;profile=dev");
    let env_cfg = parse_config("mode=ops;timeout=45;verbose=false;profile=prod");
    let file_cfg = parse_config("mode=;timeout=0;verbose=false;profile=");
    let cli_cfg = parse_config("mode=;profile=;verbose=false");

    let merged = merge(merge(merge(defaults, env_cfg), file_cfg), cli_cfg);

    let mode = merged.mode.unwrap_or_else(|| "<unset>".to_string());
    let timeout = merged.timeout.unwrap_or(99);
    let verbose = merged.verbose.unwrap_or(true);
    let profile = merged.profile.unwrap_or_else(|| "default".to_string());

    println!("mode={}", mode);
    println!("timeout={}", timeout);
    println!("verbose={}", verbose);
    println!("profile={}", profile);
}
