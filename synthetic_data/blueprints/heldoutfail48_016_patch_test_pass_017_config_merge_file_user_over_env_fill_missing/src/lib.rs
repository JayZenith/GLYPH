#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub profile: Option<String>,
    pub color: Option<bool>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppConfig {
    pub host: String,
    pub port: u16,
    pub profile: String,
    pub color: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            host: "localhost".to_string(),
            port: 8080,
            profile: "default".to_string(),
            color: false,
        }
    }
}

pub fn merge_config(
    defaults: AppConfig,
    file: PartialConfig,
    env: PartialConfig,
    user: PartialConfig,
) -> AppConfig {
    let mut cfg = defaults;

    if let Some(host) = file.host {
        cfg.host = host;
    }
    if let Some(port) = file.port {
        cfg.port = port;
    }
    if let Some(profile) = file.profile {
        cfg.profile = profile;
    }
    if let Some(color) = file.color {
        cfg.color = color;
    }

    if let Some(host) = user.host {
        cfg.host = host;
    }
    if let Some(port) = user.port {
        cfg.port = port;
    }
    if let Some(profile) = user.profile {
        cfg.profile = profile;
    }
    if let Some(color) = user.color {
        cfg.color = color;
    }

    if let Some(host) = env.host {
        cfg.host = host;
    }
    if let Some(port) = env.port {
        cfg.port = port;
    }
    if let Some(profile) = env.profile {
        cfg.profile = profile;
    }
    if let Some(color) = env.color {
        cfg.color = color;
    }

    cfg
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> AppConfig {
        AppConfig::default()
    }

    #[test]
    fn env_fills_when_file_and_user_missing() {
        let cfg = merge_config(
            defaults(),
            PartialConfig::default(),
            PartialConfig {
                host: Some("env.example".into()),
                port: Some(9001),
                profile: Some("env-profile".into()),
                color: Some(true),
            },
            PartialConfig::default(),
        );

        assert_eq!(
            cfg,
            AppConfig {
                host: "env.example".into(),
                port: 9001,
                profile: "env-profile".into(),
                color: true,
            }
        );
    }

    #[test]
    fn file_values_beat_env_values_field_by_field() {
        let cfg = merge_config(
            defaults(),
            PartialConfig {
                host: Some("file.example".into()),
                port: None,
                profile: Some("file-profile".into()),
                color: Some(false),
            },
            PartialConfig {
                host: Some("env.example".into()),
                port: Some(7000),
                profile: Some("env-profile".into()),
                color: Some(true),
            },
            PartialConfig::default(),
        );

        assert_eq!(cfg.host, "file.example");
        assert_eq!(cfg.port, 7000);
        assert_eq!(cfg.profile, "file-profile");
        assert!(!cfg.color);
    }

    #[test]
    fn user_values_beat_env_and_file_values() {
        let cfg = merge_config(
            defaults(),
            PartialConfig {
                host: Some("file.example".into()),
                port: Some(7000),
                profile: Some("file-profile".into()),
                color: Some(false),
            },
            PartialConfig {
                host: Some("env.example".into()),
                port: Some(7100),
                profile: Some("env-profile".into()),
                color: Some(true),
            },
            PartialConfig {
                host: None,
                port: Some(7200),
                profile: Some("user-profile".into()),
                color: Some(false),
            },
        );

        assert_eq!(cfg.host, "file.example");
        assert_eq!(cfg.port, 7200);
        assert_eq!(cfg.profile, "user-profile");
        assert!(!cfg.color);
    }

    #[test]
    fn defaults_remain_when_no_layer_sets_a_field() {
        let cfg = merge_config(
            defaults(),
            PartialConfig {
                host: None,
                port: None,
                profile: Some("file-profile".into()),
                color: None,
            },
            PartialConfig {
                host: None,
                port: None,
                profile: None,
                color: None,
            },
            PartialConfig {
                host: None,
                port: None,
                profile: None,
                color: None,
            },
        );

        assert_eq!(
            cfg,
            AppConfig {
                host: "localhost".into(),
                port: 8080,
                profile: "file-profile".into(),
                color: false,
            }
        );
    }

    #[test]
    fn env_only_backfills_missing_fields_after_file_and_user_layers() {
        let cfg = merge_config(
            defaults(),
            PartialConfig {
                host: Some("file.example".into()),
                port: None,
                profile: None,
                color: Some(true),
            },
            PartialConfig {
                host: Some("env.example".into()),
                port: Some(6060),
                profile: Some("env-profile".into()),
                color: Some(false),
            },
            PartialConfig {
                host: None,
                port: None,
                profile: Some("user-profile".into()),
                color: None,
            },
        );

        assert_eq!(
            cfg,
            AppConfig {
                host: "file.example".into(),
                port: 6060,
                profile: "user-profile".into(),
                color: true,
            }
        );
    }
}
