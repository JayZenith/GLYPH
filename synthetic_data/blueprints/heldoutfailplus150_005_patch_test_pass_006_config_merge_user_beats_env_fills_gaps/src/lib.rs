#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub endpoint: String,
    pub token: Option<String>,
    pub profile: String,
    pub timeout_secs: u64,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub timeout_secs: Option<u64>,
    pub retries: Option<u8>,
}

impl PartialConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

pub fn merge_config(user: PartialConfig, env: PartialConfig) -> Config {
    Config {
        endpoint: env
            .endpoint
            .or(user.endpoint)
            .unwrap_or_else(|| "https://api.default.local".to_string()),
        token: env.token.or(user.token),
        profile: env
            .profile
            .or(user.profile)
            .unwrap_or_else(|| "default".to_string()),
        timeout_secs: user.timeout_secs.unwrap_or(30),
        retries: user.retries.unwrap_or(3),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn user_values_override_env_values() {
        let user = PartialConfig {
            endpoint: Some("https://user.example".into()),
            token: Some("user-token".into()),
            profile: Some("user-profile".into()),
            timeout_secs: Some(12),
            retries: Some(1),
        };
        let env = PartialConfig {
            endpoint: Some("https://env.example".into()),
            token: Some("env-token".into()),
            profile: Some("env-profile".into()),
            timeout_secs: Some(50),
            retries: Some(9),
        };

        let cfg = merge_config(user, env);

        assert_eq!(
            cfg,
            Config {
                endpoint: "https://user.example".into(),
                token: Some("user-token".into()),
                profile: "user-profile".into(),
                timeout_secs: 12,
                retries: 1,
            }
        );
    }

    #[test]
    fn env_fills_missing_user_values() {
        let user = PartialConfig {
            endpoint: None,
            token: None,
            profile: Some("chosen".into()),
            timeout_secs: None,
            retries: Some(2),
        };
        let env = PartialConfig {
            endpoint: Some("https://env.example".into()),
            token: Some("env-token".into()),
            profile: Some("ignored-env-profile".into()),
            timeout_secs: Some(45),
            retries: Some(8),
        };

        let cfg = merge_config(user, env);

        assert_eq!(cfg.endpoint, "https://env.example");
        assert_eq!(cfg.token.as_deref(), Some("env-token"));
        assert_eq!(cfg.profile, "chosen");
        assert_eq!(cfg.timeout_secs, 45);
        assert_eq!(cfg.retries, 2);
    }

    #[test]
    fn defaults_apply_only_when_both_sources_missing() {
        let cfg = merge_config(PartialConfig::default(), PartialConfig::default());

        assert_eq!(
            cfg,
            Config {
                endpoint: "https://api.default.local".into(),
                token: None,
                profile: "default".into(),
                timeout_secs: 30,
                retries: 3,
            }
        );
    }

    #[test]
    fn merge_is_field_by_field_not_all_or_nothing() {
        let user = PartialConfig {
            endpoint: Some("https://user.example".into()),
            token: None,
            profile: None,
            timeout_secs: Some(9),
            retries: None,
        };
        let env = PartialConfig {
            endpoint: Some("https://env.example".into()),
            token: Some("env-token".into()),
            profile: Some("env-profile".into()),
            timeout_secs: Some(33),
            retries: Some(7),
        };

        let cfg = merge_config(user, env);

        assert_eq!(cfg.endpoint, "https://user.example");
        assert_eq!(cfg.token.as_deref(), Some("env-token"));
        assert_eq!(cfg.profile, "env-profile");
        assert_eq!(cfg.timeout_secs, 9);
        assert_eq!(cfg.retries, 7);
    }
}
