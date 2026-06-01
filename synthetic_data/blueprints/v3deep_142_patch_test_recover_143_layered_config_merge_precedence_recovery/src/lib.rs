#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub timeout_ms: u64,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub timeout_ms: Option<u64>,
    pub retries: Option<u8>,
}

pub fn merge_config(
    defaults: &PartialConfig,
    env: &PartialConfig,
    overrides: &PartialConfig,
) -> Config {
    let host = defaults
        .host
        .clone()
        .or_else(|| env.host.clone())
        .or_else(|| overrides.host.clone())
        .unwrap_or_else(|| "localhost".to_string());

    let port = defaults
        .port
        .or(env.port)
        .or(overrides.port)
        .unwrap_or(8080);

    let use_tls = overrides
        .use_tls
        .or(defaults.use_tls)
        .or(env.use_tls)
        .unwrap_or(false);

    let timeout_ms = overrides
        .timeout_ms
        .or(env.timeout_ms)
        .or(defaults.timeout_ms)
        .unwrap_or(0);

    let retries = defaults
        .retries
        .or(env.retries)
        .or(overrides.retries)
        .unwrap_or(3);

    Config {
        host,
        port,
        use_tls,
        timeout_ms,
        retries,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn partial(
        host: Option<&str>,
        port: Option<u16>,
        use_tls: Option<bool>,
        timeout_ms: Option<u64>,
        retries: Option<u8>,
    ) -> PartialConfig {
        PartialConfig {
            host: host.map(str::to_string),
            port,
            use_tls,
            timeout_ms,
            retries,
        }
    }

    #[test]
    fn override_precedence_applies_per_field() {
        let defaults = partial(Some("default.local"), Some(80), Some(false), Some(1000), Some(1));
        let env = partial(Some("env.local"), Some(8080), Some(true), Some(2000), Some(2));
        let overrides = partial(Some("cli.local"), Some(9090), Some(false), Some(3000), Some(5));

        let cfg = merge_config(&defaults, &env, &overrides);

        assert_eq!(cfg.host, "cli.local");
        assert_eq!(cfg.port, 9090);
        assert!(!cfg.use_tls);
        assert_eq!(cfg.timeout_ms, 3000);
        assert_eq!(cfg.retries, 5);
    }

    #[test]
    fn env_used_when_override_missing() {
        let defaults = partial(Some("default.local"), Some(80), Some(false), Some(1000), Some(1));
        let env = partial(Some("env.local"), Some(8080), Some(true), Some(2500), Some(4));
        let overrides = partial(None, None, None, None, None);

        let cfg = merge_config(&defaults, &env, &overrides);

        assert_eq!(cfg.host, "env.local");
        assert_eq!(cfg.port, 8080);
        assert!(cfg.use_tls);
        assert_eq!(cfg.timeout_ms, 2500);
        assert_eq!(cfg.retries, 4);
    }

    #[test]
    fn defaults_are_last_layer_before_builtins() {
        let defaults = partial(Some("default.local"), Some(81), Some(true), Some(1500), Some(7));
        let env = partial(None, None, None, None, None);
        let overrides = partial(None, None, None, None, None);

        let cfg = merge_config(&defaults, &env, &overrides);

        assert_eq!(cfg.host, "default.local");
        assert_eq!(cfg.port, 81);
        assert!(cfg.use_tls);
        assert_eq!(cfg.timeout_ms, 1500);
        assert_eq!(cfg.retries, 7);
    }

    #[test]
    fn builtins_fill_when_all_layers_missing() {
        let empty = partial(None, None, None, None, None);
        let cfg = merge_config(&empty, &empty, &empty);

        assert_eq!(cfg.host, "localhost");
        assert_eq!(cfg.port, 8080);
        assert!(!cfg.use_tls);
        assert_eq!(cfg.timeout_ms, 5000);
        assert_eq!(cfg.retries, 3);
    }

    #[test]
    fn false_override_must_not_be_ignored() {
        let defaults = partial(None, None, Some(true), None, None);
        let env = partial(None, None, Some(true), None, None);
        let overrides = partial(None, None, Some(false), None, None);

        let cfg = merge_config(&defaults, &env, &overrides);
        assert!(!cfg.use_tls);
    }
}
