#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub endpoint: String,
    pub token: String,
    pub retries: u32,
    pub verbose: bool,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub retries: Option<u32>,
    pub verbose: Option<bool>,
}

pub fn merge_config(file: PartialConfig, env: PartialConfig) -> Config {
    let defaults = Config {
        endpoint: "https://api.default.local".to_string(),
        token: "guest".to_string(),
        retries: 3,
        verbose: false,
    };

    Config {
        endpoint: env.endpoint.or(file.endpoint).unwrap_or(defaults.endpoint),
        token: env.token.or(file.token).unwrap_or(defaults.token),
        retries: env.retries.or(file.retries).unwrap_or(defaults.retries),
        verbose: env.verbose.or(file.verbose).unwrap_or(defaults.verbose),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_values_override_env_values() {
        let file = PartialConfig {
            endpoint: Some("https://from-file".into()),
            token: Some("file-token".into()),
            retries: Some(9),
            verbose: Some(false),
        };
        let env = PartialConfig {
            endpoint: Some("https://from-env".into()),
            token: Some("env-token".into()),
            retries: Some(1),
            verbose: Some(true),
        };

        let merged = merge_config(file, env);
        assert_eq!(
            merged,
            Config {
                endpoint: "https://from-file".into(),
                token: "file-token".into(),
                retries: 9,
                verbose: false,
            }
        );
    }

    #[test]
    fn env_fills_only_missing_fields() {
        let file = PartialConfig {
            endpoint: Some("https://from-file".into()),
            token: None,
            retries: None,
            verbose: Some(false),
        };
        let env = PartialConfig {
            endpoint: Some("https://from-env".into()),
            token: Some("env-token".into()),
            retries: Some(7),
            verbose: Some(true),
        };

        let merged = merge_config(file, env);
        assert_eq!(merged.endpoint, "https://from-file");
        assert_eq!(merged.token, "env-token");
        assert_eq!(merged.retries, 7);
        assert!(!merged.verbose);
    }

    #[test]
    fn defaults_fill_when_both_layers_missing() {
        let merged = merge_config(PartialConfig::default(), PartialConfig::default());
        assert_eq!(
            merged,
            Config {
                endpoint: "https://api.default.local".into(),
                token: "guest".into(),
                retries: 3,
                verbose: false,
            }
        );
    }

    #[test]
    fn mixed_zero_and_false_are_treated_as_explicit_values() {
        let file = PartialConfig {
            endpoint: None,
            token: Some("file-token".into()),
            retries: Some(0),
            verbose: Some(false),
        };
        let env = PartialConfig {
            endpoint: Some("https://from-env".into()),
            token: Some("env-token".into()),
            retries: Some(5),
            verbose: Some(true),
        };

        let merged = merge_config(file, env);
        assert_eq!(merged.endpoint, "https://from-env");
        assert_eq!(merged.token, "file-token");
        assert_eq!(merged.retries, 0);
        assert!(!merged.verbose);
    }

    #[test]
    fn per_field_precedence_is_independent() {
        let file = PartialConfig {
            endpoint: None,
            token: Some("file-token".into()),
            retries: Some(4),
            verbose: None,
        };
        let env = PartialConfig {
            endpoint: Some("https://from-env".into()),
            token: Some("env-token".into()),
            retries: None,
            verbose: Some(true),
        };

        let merged = merge_config(file, env);
        assert_eq!(
            merged,
            Config {
                endpoint: "https://from-env".into(),
                token: "file-token".into(),
                retries: 4,
                verbose: true,
            }
        );
    }
}
