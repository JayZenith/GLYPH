#[derive(Clone, Copy)]
struct PartialConfig {
    host: Option<&'static str>,
    port: Option<u16>,
    tls: Option<bool>,
    retries: Option<u8>,
    mode: Option<&'static str>,
}

#[derive(Clone, Copy)]
struct Config {
    host: &'static str,
    port: u16,
    tls: bool,
    retries: u8,
    mode: &'static str,
}

fn merge(defaults: Config, file: PartialConfig, env: PartialConfig, cli: PartialConfig) -> Config {
    let host = cli.host.or(file.host).or(env.host).unwrap_or(defaults.host);
    let port = cli.port.or(env.port).or(file.port).unwrap_or(defaults.port);
    let tls = cli.tls.unwrap_or(defaults.tls);
    let retries = cli.retries.or(env.retries).unwrap_or(defaults.retries);
    let mode = file.mode.or(env.mode).or(cli.mode).unwrap_or(defaults.mode);

    Config {
        host,
        port,
        tls,
        retries,
        mode,
    }
}

fn main() {
    let defaults = Config {
        host: "localhost",
        port: 8080,
        tls: false,
        retries: 3,
        mode: "standard",
    };

    let file = PartialConfig {
        host: Some("file.example.com"),
        port: Some(9000),
        tls: Some(true),
        retries: None,
        mode: Some("file"),
    };

    let env = PartialConfig {
        host: Some("env.example.com"),
        port: None,
        tls: None,
        retries: Some(5),
        mode: None,
    };

    let cli = PartialConfig {
        host: None,
        port: Some(7000),
        tls: None,
        retries: None,
        mode: Some("cli"),
    };

    let merged = merge(defaults, file, env, cli);

    println!("host={}", merged.host);
    println!("port={}", merged.port);
    println!("tls={}", merged.tls);
    println!("retries={}", merged.retries);
    println!("mode={}", merged.mode);
}
