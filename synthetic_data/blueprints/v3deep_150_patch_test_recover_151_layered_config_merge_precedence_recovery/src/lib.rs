#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub endpoint: String,
    pub retries: u8,
    pub timeout_ms: u32,
    pub dry_run: bool,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub endpoint: Option<String>,
    pub retries: Option<u8>,
    pub timeout_ms: Option<u32>,
    pub dry_run: Option<bool>,
    pub tags: Option<Vec<String>>,
}

pub fn merge_config(defaults: &Config, env: &PartialConfig, cli: &PartialConfig) -> Config {
    Config {
        endpoint: defaults.endpoint.clone(),
        retries: defaults.retries,
        timeout_ms: defaults.timeout_ms,
        dry_run: defaults.dry_run,
        tags: defaults.tags.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            endpoint: "https://default.local".to_string(),
            retries: 3,
            timeout_ms: 1000,
            dry_run: false,
            tags: vec!["base".to_string()],
        }
    }

    #[test]
    fn cli_overrides_env_and_defaults() {
        let env = PartialConfig {
            endpoint: Some("https://env.local".to_string()),
            retries: Some(5),
            timeout_ms: Some(2000),
            dry_run: Some(true),
            tags: Some(vec!["env".to_string()]),
        };
        let cli = PartialConfig {
            endpoint: Some("https://cli.local".to_string()),
            retries: Some(1),
            timeout_ms: Some(500),
            dry_run: Some(false),
            tags: Some(vec!["cli".to_string()]),
        };

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged.endpoint, "https://cli.local");
        assert_eq!(merged.retries, 1);
        assert_eq!(merged.timeout_ms, 500);
        assert!(!merged.dry_run);
        assert_eq!(merged.tags, vec!["cli"]);
    }

    #[test]
    fn env_fills_missing_cli_values() {
        let env = PartialConfig {
            endpoint: Some("https://env.local".to_string()),
            retries: Some(4),
            timeout_ms: Some(2500),
            dry_run: Some(true),
            tags: Some(vec!["env".to_string(), "shared".to_string()]),
        };
        let cli = PartialConfig {
            endpoint: None,
            retries: Some(2),
            timeout_ms: None,
            dry_run: None,
            tags: None,
        };

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged.endpoint, "https://env.local");
        assert_eq!(merged.retries, 2);
        assert_eq!(merged.timeout_ms, 2500);
        assert!(merged.dry_run);
        assert_eq!(merged.tags, vec!["env", "shared"]);
    }

    #[test]
    fn empty_cli_tags_clear_env_tags_but_nonempty_override() {
        let env = PartialConfig {
            endpoint: None,
            retries: None,
            timeout_ms: None,
            dry_run: None,
            tags: Some(vec!["env".to_string()]),
        };
        let cli = PartialConfig {
            endpoint: None,
            retries: None,
            timeout_ms: None,
            dry_run: None,
            tags: Some(vec![]),
        };

        let merged = merge_config(&defaults(), &env, &cli);
        assert!(merged.tags.is_empty());
    }

    #[test]
    fn zero_values_from_overrides_fall_back_to_lower_precedence() {
        let env = PartialConfig {
            endpoint: None,
            retries: Some(7),
            timeout_ms: Some(3000),
            dry_run: None,
            tags: None,
        };
        let cli = PartialConfig {
            endpoint: None,
            retries: Some(0),
            timeout_ms: Some(0),
            dry_run: None,
            tags: None,
        };

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged.retries, 7);
        assert_eq!(merged.timeout_ms, 3000);
    }

    #[test]
    fn defaults_used_when_no_override_exists() {
        let env = PartialConfig::default();
        let cli = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &cli);
        assert_eq!(merged, defaults());
    }
}
