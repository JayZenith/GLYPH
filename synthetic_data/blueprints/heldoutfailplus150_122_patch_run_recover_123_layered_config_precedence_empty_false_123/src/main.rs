#[derive(Clone, Debug)]
struct Config {
    host: Option<String>,
    port: Option<u16>,
    verbose: Option<bool>,
    mode: Option<String>,
}

fn defaults() -> Config {
    Config {
        host: Some("localhost".to_string()),
        port: Some(8080),
        verbose: Some(false),
        mode: Some("safe".to_string()),
    }
}

fn file_cfg() -> Config {
    Config {
        host: Some("filehost".to_string()),
        port: Some(7000),
        verbose: Some(true),
        mode: Some("fast".to_string()),
    }
}

fn env_cfg() -> Config {
    Config {
        host: Some("envhost".to_string()),
        port: Some(9000),
        verbose: Some(false),
        mode: Some("".to_string()),
    }
}

fn cli_cfg() -> Config {
    Config {
        host: Some("".to_string()),
        port: Some(0),
        verbose: Some(false),
        mode: Some("debug".to_string()),
    }
}

fn merge(base: Config, overlay: Config) -> Config {
    Config {
        host: if let Some(h) = overlay.host {
            if h.is_empty() { base.host } else { Some(h) }
        } else {
            base.host
        },
        port: overlay.port.or(base.port),
        verbose: if overlay.verbose == Some(false) {
            base.verbose
        } else {
            overlay.verbose.or(base.verbose)
        },
        mode: if let Some(m) = overlay.mode {
            if m.is_empty() { base.mode } else { Some(m) }
        } else {
            base.mode
        },
    }
}

fn render(cfg: &Config) -> String {
    format!(
        "host={}\nport={}\nverbose={}\nmode={}",
        cfg.host.clone().unwrap_or_else(|| "-".to_string()),
        cfg.port.unwrap_or(0),
        cfg.verbose.unwrap_or(false),
        cfg.mode.clone().unwrap_or_else(|| "-".to_string())
    )
}

fn main() {
    let cfg = merge(cli_cfg(), merge(env_cfg(), merge(file_cfg(), defaults())));
    println!("{}", render(&cfg));
}
