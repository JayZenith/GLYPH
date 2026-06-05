use std::collections::HashMap;

#[derive(Clone, Debug, Default)]
struct Config {
    host: Option<String>,
    port: Option<u16>,
    color: Option<bool>,
    mode: Option<String>,
    tags: Option<Vec<String>>,
}

fn parse_map(s: &str) -> HashMap<String, String> {
    let mut map = HashMap::new();
    for part in s.split(';') {
        if part.is_empty() {
            continue;
        }
        if let Some((k, v)) = part.split_once('=') {
            map.insert(k.to_string(), v.to_string());
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
        .filter(|p| !p.is_empty())
        .map(|p| p.to_string())
        .collect()
}

fn config_from_map(map: &HashMap<String, String>) -> Config {
    Config {
        host: map.get("host").cloned().filter(|s| !s.is_empty()),
        port: map.get("port").and_then(|s| s.parse::<u16>().ok()).filter(|p| *p != 0),
        color: map.get("color").and_then(|s| parse_bool(s)).filter(|b| *b),
        mode: map.get("mode").cloned().filter(|s| !s.is_empty()),
        tags: map.get("tags").map(|s| parse_tags(s)).filter(|v| !v.is_empty()),
    }
}

fn merge(defaults: Config, file: Config, env: Config, cli: Config) -> Config {
    Config {
        host: defaults.host.or(file.host).or(env.host).or(cli.host),
        port: defaults.port.or(file.port).or(env.port).or(cli.port),
        color: defaults.color.or(file.color).or(env.color).or(cli.color),
        mode: defaults.mode.or(file.mode).or(env.mode).or(cli.mode),
        tags: defaults.tags.or(file.tags).or(env.tags).or(cli.tags),
    }
}

fn main() {
    let defaults = Config {
        host: Some("localhost".to_string()),
        port: Some(8080),
        color: Some(true),
        mode: Some("safe".to_string()),
        tags: Some(vec!["base".to_string()]),
    };

    let file = config_from_map(&parse_map("host=file.example;port=9000;color=true;mode=;tags=file1,file2"));
    let env = config_from_map(&parse_map("host=;port=7000;color=false;mode=debug;tags="));
    let cli = config_from_map(&parse_map("port=0;tags=cli1,cli2;mode="));

    let merged = merge(defaults, file, env, cli);
    println!(
        "{{\"host\":\"{}\",\"port\":{},\"color\":{},\"mode\":\"{}\",\"tags\":[{}]}}",
        merged.host.unwrap_or_default(),
        merged.port.unwrap_or(0),
        merged.color.unwrap_or(false),
        merged.mode.unwrap_or_default(),
        merged
            .tags
            .unwrap_or_default()
            .into_iter()
            .map(|t| format!("\"{}\"", t))
            .collect::<Vec<_>>()
            .join(",")
    );
}
