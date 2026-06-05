use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Config {
    mode: String,
    color: bool,
    output: String,
    retry: u32,
    threads: u32,
}

fn parse_bool(s: &str) -> Option<bool> {
    match s {
        "true" | "1" | "yes" | "on" => Some(true),
        "false" | "0" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn parse_file(input: &str) -> HashMap<String, String> {
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

fn merge(defaults: Config, file: &HashMap<String, String>, env: &HashMap<String, String>, cli: &[&str]) -> Config {
    let mut cfg = defaults;

    if let Some(v) = file.get("mode") {
        if !v.is_empty() {
            cfg.mode = v.clone();
        }
    }
    if let Some(v) = file.get("color") {
        if let Some(b) = parse_bool(v) {
            cfg.color = b;
        }
    }
    if let Some(v) = file.get("output") {
        if !v.is_empty() {
            cfg.output = v.clone();
        }
    }
    if let Some(v) = file.get("retry") {
        if let Ok(n) = v.parse::<u32>() {
            if n > 0 {
                cfg.retry = n;
            }
        }
    }
    if let Some(v) = file.get("threads") {
        if let Ok(n) = v.parse::<u32>() {
            cfg.threads = n;
        }
    }

    if let Some(v) = env.get("APP_MODE") {
        if !v.is_empty() {
            cfg.mode = v.clone();
        }
    }
    if let Some(v) = env.get("APP_COLOR") {
        if let Some(b) = parse_bool(v) {
            if b {
                cfg.color = true;
            }
        }
    }
    if let Some(v) = env.get("APP_OUTPUT") {
        if !v.is_empty() {
            cfg.output = v.clone();
        }
    }
    if let Some(v) = env.get("APP_RETRY") {
        if let Ok(n) = v.parse::<u32>() {
            if n > 0 {
                cfg.retry = n;
            }
        }
    }
    if let Some(v) = env.get("APP_THREADS") {
        if let Ok(n) = v.parse::<u32>() {
            cfg.threads = n;
        }
    }

    let mut i = 0;
    while i < cli.len() {
        match cli[i] {
            "--mode" if i + 1 < cli.len() => {
                let v = cli[i + 1];
                if !v.is_empty() {
                    cfg.mode = v.to_string();
                }
                i += 2;
            }
            "--color" => {
                cfg.color = true;
                i += 1;
            }
            "--output" if i + 1 < cli.len() => {
                let v = cli[i + 1];
                if !v.is_empty() {
                    cfg.output = v.to_string();
                }
                i += 2;
            }
            "--retry" if i + 1 < cli.len() => {
                if let Ok(n) = cli[i + 1].parse::<u32>() {
                    if n > 0 {
                        cfg.retry = n;
                    }
                }
                i += 2;
            }
            "--threads" if i + 1 < cli.len() => {
                if let Ok(n) = cli[i + 1].parse::<u32>() {
                    cfg.threads = n;
                }
                i += 2;
            }
            _ => {
                i += 1;
            }
        }
    }

    cfg
}

fn main() {
    let defaults = Config {
        mode: "safe".to_string(),
        color: true,
        output: "stdout".to_string(),
        retry: 3,
        threads: 2,
    };

    let file = parse_file(
        "mode=balanced\ncolor=true\noutput=file.log\nretry=5\nthreads=4\n",
    );

    let env = HashMap::from([
        ("APP_MODE".to_string(), "eco".to_string()),
        ("APP_COLOR".to_string(), "false".to_string()),
        ("APP_OUTPUT".to_string(), "env.log".to_string()),
        ("APP_RETRY".to_string(), "0".to_string()),
        ("APP_THREADS".to_string(), "6".to_string()),
    ]);

    let cli = [
        "--mode",
        "fast",
        "--output",
        "",
        "--retry",
        "0",
        "--threads",
        "8",
    ];

    let cfg = merge(defaults, &file, &env, &cli);
    println!("mode={}", cfg.mode);
    println!("color={}", cfg.color);
    println!("output={}", cfg.output);
    println!("retry={}", cfg.retry);
    print!("threads={}", cfg.threads);
}
