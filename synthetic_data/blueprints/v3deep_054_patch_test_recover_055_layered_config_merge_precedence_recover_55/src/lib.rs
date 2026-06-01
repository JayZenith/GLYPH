#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub retries: u8,
    pub timeout_ms: u32,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub retries: Option<u8>,
    pub timeout_ms: Option<u32>,
}

pub fn merge_config(
    defaults: Config,
    file: PartialConfig,
    env: PartialConfig,
    forced: PartialConfig,
) -> Config {
    Config {
        host: defaults.host,
        port: defaults.port,
        tls: defaults.tls,
        retries: defaults.retries,
        timeout_ms: defaults.timeout_ms,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "127.0.0.1".into(),
            port: 8080,
            tls: false,
            retries: 3,
            timeout_ms: 1000,
        }
    }

    #[test]
    fn precedence_is_defaults_then_file_then_env_then_forced() {
        let file = PartialConfig {
            host: Some("file.internal".into()),
            port: Some(9000),
            tls: Some(true),
            retries: None,
            timeout_ms: Some(2500),
        };
        let env = PartialConfig {
            host: None,
            port: Some(7000),
            tls: Some(false),
            retries: Some(5),
            timeout_ms: None,
        };
        let forced = PartialConfig {
            host: Some("forced.example".into()),
            port: None,
            tls: None,
            retries: Some(1),
            timeout_ms: Some(3000),
        };

        let merged = merge_config(defaults(), file, env, forced);
        assert_eq!(merged.host, "forced.example");
        assert_eq!(merged.port, 7000);
        assert!(!merged.tls);
        assert_eq!(merged.retries, 1);
        assert_eq!(merged.timeout_ms, 3000);
    }

    #[test]
    fn missing_values_fall_back_without_zeroing_or_clearing() {
        let file = PartialConfig {
            host: Some("filebox".into()),
            port: None,
            tls: None,
            retries: Some(0),
            timeout_ms: None,
        };
        let env = PartialConfig {
            host: None,
            port: None,
            tls: Some(true),
            retries: None,
            timeout_ms: Some(0),
        };
        let forced = PartialConfig::default();

        let merged = merge_config(defaults(), file, env, forced);
        assert_eq!(merged.host, "filebox");
        assert_eq!(merged.port, 8080);
        assert!(merged.tls);
        assert_eq!(merged.retries, 0);
        assert_eq!(merged.timeout_ms, 0);
    }

    #[test]
    fn explicit_false_and_zero_from_higher_layers_must_win() {
        let file = PartialConfig {
            host: None,
            port: Some(9001),
            tls: Some(true),
            retries: Some(9),
            timeout_ms: Some(9000),
        };
        let env = PartialConfig {
            host: Some("env-host".into()),
            port: None,
            tls: Some(false),
            retries: Some(0),
            timeout_ms: Some(0),
        };
        let forced = PartialConfig {
            host: None,
            port: Some(0),
            tls: Some(false),
            retries: None,
            timeout_ms: None,
        };

        let merged = merge_config(defaults(), file, env, forced);
        assert_eq!(merged.host, "env-host");
        assert_eq!(merged.port, 0);
        assert!(!merged.tls);
        assert_eq!(merged.retries, 0);
        assert_eq!(merged.timeout_ms, 0);
    }
}
