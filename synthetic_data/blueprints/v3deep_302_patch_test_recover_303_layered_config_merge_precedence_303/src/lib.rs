#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub timeout_ms: u64,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub timeout_ms: Option<u64>,
}

impl Config {
    pub fn defaults() -> Self {
        Self {
            host: "localhost".to_string(),
            port: 8080,
            use_tls: false,
            timeout_ms: 5000,
        }
    }
}

pub fn merge_config(defaults: Config, file: PartialConfig, env: PartialConfig) -> Config {
    Config {
        host: file.host.or(env.host).unwrap_or(defaults.host),
        port: file.port.or(env.port).unwrap_or(defaults.port),
        use_tls: file.use_tls.or(env.use_tls).unwrap_or(defaults.use_tls),
        timeout_ms: env.timeout_ms.unwrap_or(defaults.timeout_ms),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_overrides_file_and_defaults() {
        let defaults = Config::defaults();
        let file = PartialConfig {
            host: Some("file.internal".into()),
            port: Some(9000),
            use_tls: Some(false),
            timeout_ms: Some(7000),
        };
        let env = PartialConfig {
            host: Some("env.service".into()),
            port: Some(9443),
            use_tls: Some(true),
            timeout_ms: Some(12000),
        };

        let merged = merge_config(defaults, file, env);
        assert_eq!(
            merged,
            Config {
                host: "env.service".into(),
                port: 9443,
                use_tls: true,
                timeout_ms: 12000,
            }
        );
    }

    #[test]
    fn file_fills_missing_env_values() {
        let defaults = Config::defaults();
        let file = PartialConfig {
            host: Some("cache.internal".into()),
            port: Some(7001),
            use_tls: Some(true),
            timeout_ms: Some(6500),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            use_tls: Some(false),
            timeout_ms: None,
        };

        let merged = merge_config(defaults, file, env);
        assert_eq!(merged.host, "cache.internal");
        assert_eq!(merged.port, 7001);
        assert!(!merged.use_tls);
        assert_eq!(merged.timeout_ms, 6500);
    }

    #[test]
    fn defaults_are_used_when_no_layer_sets_a_value() {
        let merged = merge_config(Config::defaults(), PartialConfig::default(), PartialConfig::default());
        assert_eq!(merged, Config::defaults());
    }

    #[test]
    fn zero_values_are_valid_explicit_overrides() {
        let defaults = Config::defaults();
        let file = PartialConfig {
            host: None,
            port: Some(0),
            use_tls: None,
            timeout_ms: Some(0),
        };
        let env = PartialConfig {
            host: Some("edge".into()),
            port: None,
            use_tls: Some(false),
            timeout_ms: None,
        };

        let merged = merge_config(defaults, file, env);
        assert_eq!(merged.host, "edge");
        assert_eq!(merged.port, 0);
        assert!(!merged.use_tls);
        assert_eq!(merged.timeout_ms, 0);
    }
}
