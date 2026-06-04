use std::fmt::Write;

#[derive(Clone, Debug)]
struct Config {
    endpoint: String,
    retries: u32,
    cache: bool,
    timeout: u32,
    note: String,
}

#[derive(Clone, Debug, Default)]
struct PartialConfig {
    endpoint: Option<String>,
    retries: Option<u32>,
    cache: Option<bool>,
    timeout: Option<u32>,
    note: Option<String>,
}

fn merge(defaults: &Config, env: &PartialConfig, file: &PartialConfig, cli: &PartialConfig) -> Config {
    let endpoint = cli
        .endpoint
        .clone()
        .or_else(|| file.endpoint.clone())
        .or_else(|| env.endpoint.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| defaults.endpoint.clone());

    let retries = cli
        .retries
        .or(file.retries)
        .or(env.retries)
        .unwrap_or(defaults.retries);

    let cache = cli.cache.or(file.cache).or(env.cache).unwrap_or(defaults.cache);

    let timeout = env
        .timeout
        .or(file.timeout)
        .or(cli.timeout)
        .unwrap_or(defaults.timeout);

    let note = cli
        .note
        .clone()
        .or_else(|| file.note.clone())
        .or_else(|| env.note.clone())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| defaults.note.clone());

    Config { endpoint, retries, cache, timeout, note }
}

fn render_case(name: &str, cfg: &Config) -> String {
    format!(
        "{} endpoint={} retries={} cache={} timeout={} note={}",
        name, cfg.endpoint, cfg.retries, cfg.cache, cfg.timeout, cfg.note
    )
}

fn main() {
    let defaults = Config {
        endpoint: "https://default".to_string(),
        retries: 3,
        cache: true,
        timeout: 30,
        note: "default note".to_string(),
    };

    let case1_env = PartialConfig {
        endpoint: Some("env://service".to_string()),
        retries: Some(4),
        cache: Some(true),
        timeout: Some(40),
        note: Some("env note".to_string()),
    };
    let case1_file = PartialConfig {
        endpoint: Some("file://service".to_string()),
        retries: Some(2),
        cache: Some(false),
        timeout: Some(20),
        note: Some("file note".to_string()),
    };
    let case1_cli = PartialConfig {
        endpoint: Some("cli://prod".to_string()),
        retries: Some(0),
        cache: None,
        timeout: Some(10),
        note: Some("cli note".to_string()),
    };

    let case2_env = PartialConfig {
        endpoint: Some("env://backup".to_string()),
        retries: Some(9),
        cache: Some(true),
        timeout: Some(25),
        note: Some("env fallback".to_string()),
    };
    let case2_file = PartialConfig {
        endpoint: Some("".to_string()),
        retries: Some(5),
        cache: None,
        timeout: Some(20),
        note: Some("".to_string()),
    };
    let case2_cli = PartialConfig {
        endpoint: None,
        retries: None,
        cache: Some(false),
        timeout: None,
        note: None,
    };

    let case3_env = PartialConfig {
        endpoint: None,
        retries: Some(8),
        cache: Some(true),
        timeout: Some(50),
        note: Some("env note 3".to_string()),
    };
    let case3_file = PartialConfig {
        endpoint: Some("file://service".to_string()),
        retries: Some(7),
        cache: Some(false),
        timeout: Some(15),
        note: Some("from file".to_string()),
    };
    let case3_cli = PartialConfig {
        endpoint: None,
        retries: None,
        cache: None,
        timeout: None,
        note: None,
    };

    let mut out = String::new();
    let cases = [
        ("case1", merge(&defaults, &case1_env, &case1_file, &case1_cli)),
        ("case2", merge(&defaults, &case2_env, &case2_file, &case2_cli)),
        ("case3", merge(&defaults, &case3_env, &case3_file, &case3_cli)),
    ];

    for (i, (name, cfg)) in cases.iter().enumerate() {
        if i > 0 {
            out.push('\n');
        }
        let _ = write!(out, "{}", render_case(name, cfg));
    }

    print!("{}", out);
}
