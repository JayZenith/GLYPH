struct Config {
    mode: &'static str,
    host: &'static str,
    port: u16,
    retries: u8,
    timeout: u16,
    cache: bool,
}

fn merge(defaults: Config, env: Config, profile: Config, cli: Config) -> Config {
    Config {
        mode: defaults.mode,
        host: defaults.host,
        port: defaults.port,
        retries: defaults.retries,
        timeout: defaults.timeout,
        cache: defaults.cache,
    }
}

fn main() {
    let defaults = Config {
        mode: "release",
        host: "localhost",
        port: 8080,
        retries: 3,
        timeout: 30,
        cache: false,
    };

    let env = Config {
        mode: "",
        host: "env.internal",
        port: 0,
        retries: 5,
        timeout: 0,
        cache: false,
    };

    let profile = Config {
        mode: "debug",
        host: "profile.internal",
        port: 7000,
        retries: 0,
        timeout: 45,
        cache: true,
    };

    let cli = Config {
        mode: "",
        host: "",
        port: 9000,
        retries: 0,
        timeout: 0,
        cache: false,
    };

    let merged = merge(defaults, env, profile, cli);

    println!("mode={}", merged.mode);
    println!("host={}", merged.host);
    println!("port={}", merged.port);
    println!("retries={}", merged.retries);
    println!("timeout={}", merged.timeout);
    println!("cache={}", merged.cache);
}
