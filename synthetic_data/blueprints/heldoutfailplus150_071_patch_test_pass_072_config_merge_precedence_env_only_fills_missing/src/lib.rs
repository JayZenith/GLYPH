#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Config {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub retries: Option<u8>,
}

impl Config {
    fn merged_with(self, other: Config) -> Config {
        Config {
            endpoint: other.endpoint.or(self.endpoint),
            token: other.token.or(self.token),
            profile: other.profile.or(self.profile),
            retries: other.retries.or(self.retries),
        }
    }
}

pub fn resolve_config(defaults: Config, file_cfg: Config, env_cfg: Config, user_cfg: Config) -> Config {
    defaults
        .merged_with(file_cfg)
        .merged_with(env_cfg)
        .merged_with(user_cfg)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(v: &str) -> Option<String> {
        Some(v.to_string())
    }

    #[test]
    fn env_fills_missing_file_values() {
        let defaults = Config {
            endpoint: s("https://default"),
            token: None,
            profile: s("default"),
            retries: Some(2),
        };
        let file_cfg = Config {
            endpoint: s("https://file"),
            token: None,
            profile: None,
            retries: Some(5),
        };
        let env_cfg = Config {
            endpoint: None,
            token: s("env-token"),
            profile: s("env-profile"),
            retries: None,
        };
        let user_cfg = Config::default();

        let resolved = resolve_config(defaults, file_cfg, env_cfg, user_cfg);

        assert_eq!(resolved.endpoint, s("https://file"));
        assert_eq!(resolved.token, s("env-token"));
        assert_eq!(resolved.profile, s("env-profile"));
        assert_eq!(resolved.retries, Some(5));
    }

    #[test]
    fn file_values_override_env_values_when_present() {
        let defaults = Config::default();
        let file_cfg = Config {
            endpoint: s("https://file"),
            token: s("file-token"),
            profile: None,
            retries: Some(4),
        };
        let env_cfg = Config {
            endpoint: s("https://env"),
            token: s("env-token"),
            profile: s("env-profile"),
            retries: Some(9),
        };
        let user_cfg = Config::default();

        let resolved = resolve_config(defaults, file_cfg, env_cfg, user_cfg);

        assert_eq!(resolved.endpoint, s("https://file"));
        assert_eq!(resolved.token, s("file-token"));
        assert_eq!(resolved.profile, s("env-profile"));
        assert_eq!(resolved.retries, Some(4));
    }

    #[test]
    fn user_values_override_both_file_and_env() {
        let defaults = Config {
            endpoint: s("https://default"),
            token: s("default-token"),
            profile: s("default-profile"),
            retries: Some(1),
        };
        let file_cfg = Config {
            endpoint: s("https://file"),
            token: s("file-token"),
            profile: None,
            retries: Some(3),
        };
        let env_cfg = Config {
            endpoint: s("https://env"),
            token: s("env-token"),
            profile: s("env-profile"),
            retries: Some(8),
        };
        let user_cfg = Config {
            endpoint: None,
            token: s("user-token"),
            profile: s("user-profile"),
            retries: Some(7),
        };

        let resolved = resolve_config(defaults, file_cfg, env_cfg, user_cfg);

        assert_eq!(resolved.endpoint, s("https://file"));
        assert_eq!(resolved.token, s("user-token"));
        assert_eq!(resolved.profile, s("user-profile"));
        assert_eq!(resolved.retries, Some(7));
    }

    #[test]
    fn defaults_remain_for_fields_missing_everywhere_else() {
        let defaults = Config {
            endpoint: s("https://default"),
            token: s("default-token"),
            profile: s("default-profile"),
            retries: Some(6),
        };
        let file_cfg = Config {
            endpoint: None,
            token: None,
            profile: None,
            retries: None,
        };
        let env_cfg = Config {
            endpoint: None,
            token: s("env-token"),
            profile: None,
            retries: None,
        };
        let user_cfg = Config {
            endpoint: None,
            token: None,
            profile: None,
            retries: None,
        };

        let resolved = resolve_config(defaults, file_cfg, env_cfg, user_cfg);

        assert_eq!(resolved.endpoint, s("https://default"));
        assert_eq!(resolved.token, s("env-token"));
        assert_eq!(resolved.profile, s("default-profile"));
        assert_eq!(resolved.retries, Some(6));
    }
}
