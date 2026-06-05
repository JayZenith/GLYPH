#[derive(Clone, Debug)]
struct Config {
    service: Option<String>,
    port: Option<u16>,
    debug: Option<bool>,
    color: Option<bool>,
    mode: Option<String>,
}

impl Config {
    fn empty() -> Self {
        Self {
            service: None,
            port: None,
            debug: None,
            color: None,
            mode: None,
        }
    }
}

fn merge(base: Config, over: Config) -> Config {
    Config {
        service: if over.service.as_deref().unwrap_or("").is_empty() { base.service } else { over.service },
        port: over.port.or(base.port),
        debug: over.debug.filter(|v| *v).or(base.debug),
        color: over.color.filter(|v| *v).or(base.color),
        mode: over.mode.or(base.mode),
    }
}

fn main() {
    let defaults = Config {
        service: Some("core".to_string()),
        port: Some(3000),
        debug: Some(false),
        color: Some(true),
        mode: Some("safe".to_string()),
    };

    let env_cfg = Config {
        service: Some("envsvc".to_string()),
        port: Some(8080),
        debug: Some(true),
        color: Some(true),
        mode: None,
    };

    let file_cfg = Config {
        service: Some("".to_string()),
        port: None,
        debug: Some(false),
        color: None,
        mode: Some("fast".to_string()),
    };

    let cli_cfg = Config {
        service: None,
        port: None,
        debug: Some(false),
        color: Some(false),
        mode: Some("".to_string()),
    };

    let merged = merge(merge(merge(defaults, env_cfg), file_cfg), cli_cfg);

    let service = merged.service.unwrap_or_else(|| "core".to_string());
    let port = merged.port.unwrap_or(3000);
    let debug = merged.debug.unwrap_or(false);
    let color = merged.color.unwrap_or(true);
    let mode = merged.mode.unwrap_or_else(|| "safe".to_string());

    println!("service={}", service);
    println!("port={}", port);
    println!("debug={}", debug);
    println!("color={}", color);
    println!("mode={}", mode);
}
