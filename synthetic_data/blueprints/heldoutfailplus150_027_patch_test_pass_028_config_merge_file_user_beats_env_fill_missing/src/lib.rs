#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub profile: String,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub profile: Option<String>,
}

pub fn merge_config(defaults: &Config, file: &PartialConfig, env: &PartialConfig) -> Config {
    Config {
        host: env
            .host
            .clone()
            .or_else(|| file.host.clone())
            .unwrap_or_else(|| defaults.host.clone()),
        port: env.port.or(file.port).unwrap_or(defaults.port),
        tls: env.tls.or(file.tls).unwrap_or(defaults.tls),
        profile: file
            .profile
            .clone()
            .or_else(|| env.profile.clone())
            .unwrap_or_else(|| defaults.profile.clone()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "127.0.0.1".to_string(),
            port: 8080,
            tls: false,
            profile: "dev".to_string(),
        }
    }

    #[test]
    fn explicit_file_values_override_env_values() {
        let file = PartialConfig {
            host: Some("file.internal".to_string()),
            port: Some(9000),
            tls: Some(false),
            profile: Some("file-profile".to_string()),
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: Some(7000),
            tls: Some(true),
            profile: Some("env-profile".to_string()),
        };

        let merged = merge_config(&defaults(), &file, &env);

        assert_eq!(
            merged,
            Config {
                host: "file.internal".to_string(),
                port: 9000,
                tls: false,
                profile: "file-profile".to_string(),
            }
        );
    }

    #[test]
    fn env_fills_fields_missing_from_file() {
        let file = PartialConfig {
            host: Some("file.internal".to_string()),
            port: None,
            tls: None,
            profile: None,
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: Some(7000),
            tls: Some(true),
            profile: Some("staging".to_string()),
        };

        let merged = merge_config(&defaults(), &file, &env);

        assert_eq!(merged.host, "file.internal");
        assert_eq!(merged.port, 7000);
        assert!(merged.tls);
        assert_eq!(merged.profile, "staging");
    }

    #[test]
    fn defaults_remain_when_both_file_and_env_are_missing() {
        let file = PartialConfig::default();
        let env = PartialConfig::default();

        let merged = merge_config(&defaults(), &file, &env);

        assert_eq!(merged, defaults());
    }

    #[test]
    fn precedence_is_applied_per_field_not_per_source() {
        let file = PartialConfig {
            host: None,
            port: Some(9100),
            tls: None,
            profile: Some("ops".to_string()),
        };
        let env = PartialConfig {
            host: Some("env-only.internal".to_string()),
            port: Some(7200),
            tls: Some(true),
            profile: Some("env-profile".to_string()),
        };

        let merged = merge_config(&defaults(), &file, &env);

        assert_eq!(
            merged,
            Config {
                host: "env-only.internal".to_string(),
                port: 9100,
                tls: true,
                profile: "ops".to_string(),
            }
        );
    }

    #[test]
    fn explicit_false_and_zero_like_values_are_not_treated_as_missing() {
        let file = PartialConfig {
            host: None,
            port: Some(0),
            tls: Some(false),
            profile: None,
        };
        let env = PartialConfig {
            host: None,
            port: Some(6553),
            tls: Some(true),
            profile: None,
        };

        let merged = merge_config(&defaults(), &file, &env);

        assert_eq!(merged.port, 0);
        assert!(!merged.tls);
    }
}
