#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub profile: String,
    pub color: bool,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub profile: Option<String>,
    pub color: Option<bool>,
}

pub fn merge_config(file: PartialConfig, user: PartialConfig, env: PartialConfig) -> Config {
    let defaults = Config {
        host: "127.0.0.1".to_string(),
        port: 8080,
        profile: "dev".to_string(),
        color: true,
    };

    Config {
        host: env
            .host
            .or(user.host)
            .or(file.host)
            .unwrap_or(defaults.host),
        port: env.port.or(user.port).or(file.port).unwrap_or(defaults.port),
        profile: env
            .profile
            .or(user.profile)
            .or(file.profile)
            .unwrap_or(defaults.profile),
        color: env
            .color
            .or(user.color)
            .or(file.color)
            .unwrap_or(defaults.color),
    }
}

#[cfg(test)]
mod tests {
    use super::{merge_config, Config, PartialConfig};

    #[test]
    fn env_fills_missing_when_no_explicit_values_exist() {
        let file = PartialConfig::default();
        let user = PartialConfig::default();
        let env = PartialConfig {
            host: Some("env.example".into()),
            port: Some(9000),
            profile: Some("staging".into()),
            color: Some(false),
        };

        let merged = merge_config(file, user, env);
        assert_eq!(
            merged,
            Config {
                host: "env.example".into(),
                port: 9000,
                profile: "staging".into(),
                color: false,
            }
        );
    }

    #[test]
    fn user_values_override_env_but_env_still_fills_other_fields() {
        let file = PartialConfig {
            host: Some("file.example".into()),
            port: Some(7000),
            profile: None,
            color: None,
        };
        let user = PartialConfig {
            host: None,
            port: Some(7777),
            profile: Some("user-profile".into()),
            color: None,
        };
        let env = PartialConfig {
            host: Some("env.example".into()),
            port: Some(9999),
            profile: Some("env-profile".into()),
            color: Some(false),
        };

        let merged = merge_config(file, user, env);
        assert_eq!(merged.port, 7777);
        assert_eq!(merged.profile, "user-profile");
        assert_eq!(merged.host, "file.example");
        assert!(!merged.color);
    }

    #[test]
    fn file_values_override_env_when_user_missing() {
        let file = PartialConfig {
            host: Some("cfg.internal".into()),
            port: None,
            profile: Some("from-file".into()),
            color: Some(true),
        };
        let user = PartialConfig::default();
        let env = PartialConfig {
            host: Some("env.external".into()),
            port: Some(5050),
            profile: Some("from-env".into()),
            color: Some(false),
        };

        let merged = merge_config(file, user, env);
        assert_eq!(merged.host, "cfg.internal");
        assert_eq!(merged.profile, "from-file");
        assert!(merged.color);
        assert_eq!(merged.port, 5050);
    }

    #[test]
    fn explicit_false_from_user_beats_true_from_env() {
        let file = PartialConfig {
            host: None,
            port: None,
            profile: None,
            color: Some(true),
        };
        let user = PartialConfig {
            host: None,
            port: None,
            profile: None,
            color: Some(false),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            profile: None,
            color: Some(true),
        };

        let merged = merge_config(file, user, env);
        assert!(!merged.color);
    }

    #[test]
    fn defaults_apply_only_after_all_sources_are_missing() {
        let merged = merge_config(
            PartialConfig::default(),
            PartialConfig::default(),
            PartialConfig::default(),
        );

        assert_eq!(
            merged,
            Config {
                host: "127.0.0.1".into(),
                port: 8080,
                profile: "dev".into(),
                color: true,
            }
        );
    }
}
