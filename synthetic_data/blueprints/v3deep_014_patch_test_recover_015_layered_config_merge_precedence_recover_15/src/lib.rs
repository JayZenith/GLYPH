#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub timeout_ms: u32,
    pub endpoint: String,
    pub cache_enabled: bool,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub timeout_ms: Option<u32>,
    pub endpoint: Option<String>,
    pub cache_enabled: Option<bool>,
    pub retries: Option<u8>,
}

pub fn merge_config(defaults: &Config, env: &PartialConfig, cli: &PartialConfig) -> Config {
    let timeout_ms = defaults
        .timeout_ms;

    let endpoint = defaults.endpoint.clone();

    let cache_enabled = defaults
        .cache_enabled
        || env.cache_enabled.unwrap_or(false)
        || cli.cache_enabled.unwrap_or(false);

    let retries = env
        .retries
        .or(cli.retries)
        .unwrap_or(defaults.retries);

    Config {
        timeout_ms,
        endpoint,
        cache_enabled,
        retries,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            timeout_ms: 1000,
            endpoint: "https://default.service".to_string(),
            cache_enabled: true,
            retries: 2,
        }
    }

    #[test]
    fn cli_overrides_env_and_defaults_for_scalar_values() {
        let env = PartialConfig {
            timeout_ms: Some(2000),
            endpoint: Some("https://env.service".to_string()),
            cache_enabled: Some(true),
            retries: Some(4),
        };
        let cli = PartialConfig {
            timeout_ms: Some(3000),
            endpoint: Some("https://cli.service".to_string()),
            cache_enabled: Some(false),
            retries: Some(1),
        };

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged.timeout_ms, 3000);
        assert_eq!(merged.endpoint, "https://cli.service");
        assert!(!merged.cache_enabled);
        assert_eq!(merged.retries, 1);
    }

    #[test]
    fn env_fills_when_cli_missing() {
        let env = PartialConfig {
            timeout_ms: Some(2500),
            endpoint: Some("https://env.service".to_string()),
            cache_enabled: Some(false),
            retries: Some(5),
        };
        let cli = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged.timeout_ms, 2500);
        assert_eq!(merged.endpoint, "https://env.service");
        assert!(!merged.cache_enabled);
        assert_eq!(merged.retries, 5);
    }

    #[test]
    fn defaults_remain_when_no_overrides_present() {
        let merged = merge_config(&defaults(), &PartialConfig::default(), &PartialConfig::default());
        assert_eq!(merged, defaults());
    }

    #[test]
    fn false_override_must_disable_cache_even_if_default_is_true() {
        let env = PartialConfig {
            cache_enabled: Some(false),
            ..PartialConfig::default()
        };
        let cli = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &cli);
        assert!(!merged.cache_enabled);
    }
}
