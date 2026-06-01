#[derive(Clone, Debug)]
struct Config {
    mode: Option<&'static str>,
    port: Option<u16>,
    log: Option<bool>,
    tags: Vec<&'static str>,
    workers: Option<u8>,
}

fn merge(defaults: Config, file: Config, env: Config, cli: Config) -> Config {
    let mode = defaults.mode.or(file.mode).or(env.mode).or(cli.mode);
    let port = defaults.port.or(file.port).or(env.port).or(cli.port);
    let log = defaults.log.or(file.log).or(env.log).or(cli.log);

    let mut tags = Vec::new();
    tags.extend(cli.tags.iter().copied());
    tags.extend(env.tags.iter().copied());
    tags.extend(file.tags.iter().copied());
    tags.extend(defaults.tags.iter().copied());

    let workers = defaults.workers.or(file.workers).or(env.workers).or(cli.workers);

    Config {
        mode,
        port,
        log,
        tags,
        workers,
    }
}

fn main() {
    let defaults = Config {
        mode: Some("release"),
        port: Some(8080),
        log: Some(false),
        tags: vec!["base"],
        workers: Some(4),
    };
    let file = Config {
        mode: Some("debug"),
        port: Some(9000),
        log: None,
        tags: vec!["file"],
        workers: None,
    };
    let env = Config {
        mode: None,
        port: Some(7000),
        log: Some(true),
        tags: vec!["env"],
        workers: Some(8),
    };
    let cli = Config {
        mode: None,
        port: None,
        log: None,
        tags: vec!["cli"],
        workers: None,
    };

    let merged = merge(defaults, file, env, cli);

    println!("mode={}", merged.mode.unwrap_or("unset"));
    println!("port={}", merged.port.unwrap_or(0));
    println!("log={}", merged.log.unwrap_or(false));
    println!("tags={}", merged.tags.join(","));
    println!("workers={}", merged.workers.unwrap_or(0));
}
