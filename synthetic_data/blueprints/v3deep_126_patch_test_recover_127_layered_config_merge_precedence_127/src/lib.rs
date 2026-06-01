#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub retries: Option<u8>,
}

pub fn merge_config(
    defaults: &Config,
    env: &PartialConfig,
    overrides: &PartialConfig,
) -> Config {
    let host = env
        .host
        .clone()
        .or_else(|| overrides.host.clone())
        .unwrap_or_else(|| defaults.host.clone());

    let port = overrides.port.or(env.port).unwrap_or(defaults.port);

    let use_tls = overrides.use_tls.unwrap_or(env.use_tls.unwrap_or(defaults.use_tls));

    let retries = overrides
        .retries
        .or(env.retries)
        .unwrap_or(defaults.retries);

    Config {
        host,
        port,
        use_tls,
        retries,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".to_string(),
            port: 8080,
            use_tls: false,
            retries: 3,
        }
    }

    #[test]
    fn overrides_take_precedence_over_env_and_defaults() {
        let env = PartialConfig {
            host: Some("env.service".to_string()),
            port: Some(9000),
            use_tls: Some(true),
            retries: Some(5),
        };
        let overrides = PartialConfig {
            host: Some("cli.service".to_string()),
            port: Some(7000),
            use_tls: Some(false),
            retries: Some(2),
        };

        let merged = merge_config(&defaults(), &env, &overrides);
        assert_eq!(
            merged,
            Config {
                host: "cli.service".to_string(),
                port: 7000,
                use_tls: false,
                retries: 2,
            }
        );
    }

    #[test]
    fn env_fills_missing_values_before_defaults() {
        let env = PartialConfig {
            host: Some("env.service".to_string()),
            port: None,
            use_tls: Some(true),
            retries: None,
        };
        let overrides = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &overrides);
        assert_eq!(merged.host, "env.service");
        assert_eq!(merged.port, 8080);
        assert!(merged.use_tls);
        assert_eq!(merged.retries, 3);
    }

    #[test]
    fn zero_retries_in_override_disables_retries() {
        let env = PartialConfig {
            retries: Some(4),
            ..PartialConfig::default()
        };
        let overrides = PartialConfig {
            retries: Some(0),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &env, &overrides);
        assert_eq!(merged.retries, 0);
    }

    #[test]
    fn zero_retries_from_env_falls_back_to_default_when_no_override() {
        let env = PartialConfig {
            retries: Some(0),
            ..PartialConfig::default()
        };
        let overrides = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &overrides);
        assert_eq!(merged.retries, 3);
    }
}
