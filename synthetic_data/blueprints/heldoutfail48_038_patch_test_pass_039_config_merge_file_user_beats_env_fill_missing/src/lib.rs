#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub endpoint: String,
    pub token: String,
    pub profile: String,
    pub retries: u32,
    pub timeout_ms: u64,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub retries: Option<u32>,
    pub timeout_ms: Option<u64>,
}

pub fn merge_config(file: PartialConfig, env: PartialConfig) -> Config {
    let defaults = Config {
        endpoint: "https://default.service".to_string(),
        token: "anon".to_string(),
        profile: "default".to_string(),
        retries: 3,
        timeout_ms: 1000,
    };

    Config {
        endpoint: env.endpoint.or(file.endpoint).unwrap_or(defaults.endpoint),
        token: env.token.or(file.token).unwrap_or(defaults.token),
        profile: env.profile.or(file.profile).unwrap_or(defaults.profile),
        retries: env.retries.or(file.retries).unwrap_or(defaults.retries),
        timeout_ms: env.timeout_ms.or(file.timeout_ms).unwrap_or(defaults.timeout_ms),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base_file() -> PartialConfig {
        PartialConfig {
            endpoint: Some("https://file.service".into()),
            token: Some("file-token".into()),
            profile: Some("file-profile".into()),
            retries: Some(7),
            timeout_ms: Some(2500),
        }
    }

    fn base_env() -> PartialConfig {
        PartialConfig {
            endpoint: Some("https://env.service".into()),
            token: Some("env-token".into()),
            profile: Some("env-profile".into()),
            retries: Some(9),
            timeout_ms: Some(4000),
        }
    }

    #[test]
    fn file_values_override_env_when_both_present() {
        let merged = merge_config(base_file(), base_env());
        assert_eq!(
            merged,
            Config {
                endpoint: "https://file.service".into(),
                token: "file-token".into(),
                profile: "file-profile".into(),
                retries: 7,
                timeout_ms: 2500,
            }
        );
    }

    #[test]
    fn env_fills_only_missing_file_fields() {
        let file = PartialConfig {
            endpoint: Some("https://file.service".into()),
            token: None,
            profile: Some("file-profile".into()),
            retries: None,
            timeout_ms: Some(2500),
        };
        let env = base_env();

        let merged = merge_config(file, env);
        assert_eq!(merged.endpoint, "https://file.service");
        assert_eq!(merged.token, "env-token");
        assert_eq!(merged.profile, "file-profile");
        assert_eq!(merged.retries, 9);
        assert_eq!(merged.timeout_ms, 2500);
    }

    #[test]
    fn defaults_fill_when_both_layers_are_missing() {
        let file = PartialConfig {
            endpoint: None,
            token: None,
            profile: Some("file-profile".into()),
            retries: None,
            timeout_ms: None,
        };
        let env = PartialConfig {
            endpoint: None,
            token: Some("env-token".into()),
            profile: None,
            retries: None,
            timeout_ms: Some(4000),
        };

        let merged = merge_config(file, env);
        assert_eq!(merged.endpoint, "https://default.service");
        assert_eq!(merged.token, "env-token");
        assert_eq!(merged.profile, "file-profile");
        assert_eq!(merged.retries, 3);
        assert_eq!(merged.timeout_ms, 4000);
    }

    #[test]
    fn env_can_supply_everything_when_file_is_empty() {
        let merged = merge_config(PartialConfig::default(), base_env());
        assert_eq!(
            merged,
            Config {
                endpoint: "https://env.service".into(),
                token: "env-token".into(),
                profile: "env-profile".into(),
                retries: 9,
                timeout_ms: 4000,
            }
        );
    }
}
