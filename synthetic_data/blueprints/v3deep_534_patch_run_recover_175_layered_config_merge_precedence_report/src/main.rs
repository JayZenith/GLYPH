#[derive(Clone, Copy)]
struct Layer {
    host: Option<&'static str>,
    port: Option<u16>,
    mode: Option<&'static str>,
    timeout: Option<u32>,
}

#[derive(Clone, Copy)]
struct Effective {
    host: &'static str,
    port: u16,
    mode: &'static str,
    timeout: u32,
}

fn merge(defaults: Layer, file: Layer, env: Layer, cli: Layer) -> (Effective, Vec<&'static str>) {
    let mut sources = vec!["default"];

    let host = defaults
        .host
        .or(file.host)
        .or(env.host)
        .or(cli.host)
        .unwrap();

    let port = defaults
        .port
        .or(file.port)
        .or(env.port)
        .or(cli.port)
        .unwrap();

    let mode = defaults
        .mode
        .or(file.mode)
        .or(env.mode)
        .or(cli.mode)
        .unwrap();

    let timeout = defaults
        .timeout
        .or(file.timeout)
        .or(env.timeout)
        .or(cli.timeout)
        .unwrap();

    if file.host.is_some() || file.port.is_some() || file.mode.is_some() || file.timeout.is_some() {
        sources.push("file");
    }
    if env.host.is_some() || env.port.is_some() || env.mode.is_some() {
        sources.push("env");
    }
    if cli.host.is_some() || cli.mode.is_some() || cli.timeout.is_some() {
        sources.push("cli");
    }

    (
        Effective {
            host,
            port,
            mode,
            timeout,
        },
        sources,
    )
}

fn main() {
    let defaults = Layer {
        host: Some("localhost"),
        port: Some(8080),
        mode: Some("release"),
        timeout: Some(30),
    };

    let file = Layer {
        host: Some("file.internal"),
        port: Some(7000),
        mode: None,
        timeout: Some(45),
    };

    let env = Layer {
        host: None,
        port: None,
        mode: Some("debug"),
        timeout: None,
    };

    let cli = Layer {
        host: Some("cli.internal"),
        port: Some(9000),
        mode: None,
        timeout: None,
    };

    let (effective, sources) = merge(defaults, file, env, cli);

    println!("host={}", effective.host);
    println!("port={}", effective.port);
    println!("mode={}", effective.mode);
    println!("timeout={}", effective.timeout);
    println!("sources={}", sources.join(","));
}
