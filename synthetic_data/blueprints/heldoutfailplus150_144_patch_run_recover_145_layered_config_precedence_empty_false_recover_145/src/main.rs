use std::collections::HashMap;

#[derive(Clone, Debug)]
struct Layer {
    host: Option<String>,
    port: Option<u16>,
    verbose: Option<bool>,
    token: Option<String>,
}

#[derive(Clone, Debug)]
struct FinalConfig {
    host: String,
    port: u16,
    verbose: bool,
    token: String,
    host_src: &'static str,
    port_src: &'static str,
    verbose_src: &'static str,
    token_src: &'static str,
}

fn parse_file(input: &str) -> Layer {
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
    Layer {
        host: map.get("host").cloned().filter(|s| !s.is_empty()),
        port: map.get("port").and_then(|s| s.parse().ok()),
        verbose: map.get("verbose").map(|s| s == "true"),
        token: map.get("token").cloned().filter(|s| !s.is_empty()),
    }
}

fn parse_env(entries: &[(&str, &str)]) -> Layer {
    let mut layer = Layer {
        host: None,
        port: None,
        verbose: None,
        token: None,
    };
    for (k, v) in entries {
        match *k {
            "APP_HOST" => {
                if !v.is_empty() {
                    layer.host = Some((*v).to_string())
                }
            }
            "APP_PORT" => layer.port = v.parse().ok(),
            "APP_VERBOSE" => layer.verbose = Some(*v == "true"),
            "APP_TOKEN" => {
                if !v.is_empty() {
                    layer.token = Some((*v).to_string())
                }
            }
            _ => {}
        }
    }
    layer
}

fn parse_cli(args: &[&str]) -> Layer {
    let mut layer = Layer {
        host: None,
        port: None,
        verbose: None,
        token: None,
    };
    let mut it = args.iter();
    while let Some(arg) = it.next() {
        match *arg {
            "--host" => {
                if let Some(v) = it.next() {
                    if !v.is_empty() {
                        layer.host = Some((*v).to_string());
                    }
                }
            }
            "--port" => {
                if let Some(v) = it.next() {
                    layer.port = v.parse().ok();
                }
            }
            "--verbose" => layer.verbose = Some(true),
            "--token" => {
                if let Some(v) = it.next() {
                    if !v.is_empty() {
                        layer.token = Some((*v).to_string());
                    }
                }
            }
            _ => {}
        }
    }
    layer
}

fn merge(defaults: Layer, file: Layer, env: Layer, cli: Layer) -> FinalConfig {
    let mut out = FinalConfig {
        host: defaults.host.unwrap_or_else(|| "localhost".to_string()),
        port: defaults.port.unwrap_or(3000),
        verbose: defaults.verbose.unwrap_or(false),
        token: defaults.token.unwrap_or_else(|| "default-token".to_string()),
        host_src: "default",
        port_src: "default",
        verbose_src: "default",
        token_src: "default",
    };

    for (name, layer) in [("file", file), ("env", env), ("cli", cli)] {
        if let Some(v) = layer.host.clone() {
            out.host = v;
            out.host_src = name;
        }
        if let Some(v) = layer.port {
            out.port = v;
            out.port_src = name;
        }
        if let Some(v) = layer.verbose {
            if v {
                out.verbose = true;
                out.verbose_src = name;
            }
        }
        if let Some(v) = layer.token.clone() {
            out.token = v;
            out.token_src = name;
        }
    }

    out
}

fn main() {
    let defaults = Layer {
        host: Some("localhost".to_string()),
        port: Some(3000),
        verbose: Some(true),
        token: Some("default-token".to_string()),
    };

    let file_cfg = parse_file("host=filebox\nport=7000\nverbose=true\ntoken=file-token\n");
    let env_cfg = parse_env(&[("APP_HOST", ""), ("APP_PORT", "8080"), ("APP_VERBOSE", "false")]);
    let cli_cfg = parse_cli(&["--host", "", "--verbose", "false", "--token", "cli-token"]);

    let cfg = merge(defaults, file_cfg, env_cfg, cli_cfg);

    println!("host={}", cfg.host);
    println!("port={}", cfg.port);
    println!("verbose={}", cfg.verbose);
    println!("token={}", cfg.token);
    println!("source.host={}", cfg.host_src);
    println!("source.port={}", cfg.port_src);
    println!("source.verbose={}", cfg.verbose_src);
    print!("source.token={}", cfg.token_src);
}
