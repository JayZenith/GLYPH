#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub profile: String,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub profile: Option<String>,
}

pub fn merge_config(file: PartialConfig, user: PartialConfig, env: PartialConfig) -> Config {
    let host = env
        .host
        .or(user.host)
        .or(file.host)
        .unwrap_or_else(|| "127.0.0.1".to_string());

    let port = env.port.or(user.port).or(file.port).unwrap_or(8080);

    let use_tls = user.use_tls.or(env.use_tls).or(file.use_tls).unwrap_or(false);

    let profile = env
        .profile
        .or(file.profile)
        .or(user.profile)
        .unwrap_or_else(|| "default".to_string());

    Config {
        host,
        port,
        use_tls,
        profile,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pc(
        host: Option<&str>,
        port: Option<u16>,
        use_tls: Option<bool>,
        profile: Option<&str>,
    ) -> PartialConfig {
        PartialConfig {
            host: host.map(str::to_string),
            port,
            use_tls,
            profile: profile.map(str::to_string),
        }
    }

    #[test]
    fn user_values_override_env_and_file_for_every_field() {
        let file = pc(Some("file.local"), Some(7000), Some(false), Some("file-profile"));
        let user = pc(Some("user.local"), Some(9000), Some(true), Some("user-profile"));
        let env = pc(Some("env.local"), Some(6000), Some(false), Some("env-profile"));

        let cfg = merge_config(file, user, env);

        assert_eq!(
            cfg,
            Config {
                host: "user.local".to_string(),
                port: 9000,
                use_tls: true,
                profile: "user-profile".to_string(),
            }
        );
    }

    #[test]
    fn env_only_fills_missing_user_and_file_values() {
        let file = pc(Some("file.local"), None, None, Some("file-profile"));
        let user = pc(None, Some(5001), None, None);
        let env = pc(Some("env.local"), Some(6000), Some(true), Some("env-profile"));

        let cfg = merge_config(file, user, env);

        assert_eq!(cfg.host, "file.local");
        assert_eq!(cfg.port, 5001);
        assert_eq!(cfg.use_tls, true);
        assert_eq!(cfg.profile, "file-profile");
    }

    #[test]
    fn file_beats_env_when_user_missing() {
        let file = pc(Some("file.local"), Some(4100), Some(false), Some("file-profile"));
        let user = pc(None, None, None, None);
        let env = pc(Some("env.local"), Some(4200), Some(true), Some("env-profile"));

        let cfg = merge_config(file, user, env);

        assert_eq!(cfg.host, "file.local");
        assert_eq!(cfg.port, 4100);
        assert!(!cfg.use_tls);
        assert_eq!(cfg.profile, "file-profile");
    }

    #[test]
    fn env_is_used_when_both_explicit_layers_are_missing() {
        let file = pc(None, None, None, None);
        let user = pc(None, None, None, None);
        let env = pc(Some("env.local"), Some(6123), Some(true), Some("ci"));

        let cfg = merge_config(file, user, env);

        assert_eq!(
            cfg,
            Config {
                host: "env.local".to_string(),
                port: 6123,
                use_tls: true,
                profile: "ci".to_string(),
            }
        );
    }

    #[test]
    fn defaults_apply_only_when_all_layers_are_missing() {
        let cfg = merge_config(pc(None, None, None, None), pc(None, None, None, None), pc(None, None, None, None));

        assert_eq!(
            cfg,
            Config {
                host: "127.0.0.1".to_string(),
                port: 8080,
                use_tls: false,
                profile: "default".to_string(),
            }
        );
    }

    #[test]
    fn false_user_flag_still_overrides_true_env_flag() {
        let file = pc(None, None, Some(true), None);
        let user = pc(None, None, Some(false), None);
        let env = pc(None, None, Some(true), None);

        let cfg = merge_config(file, user, env);

        assert!(!cfg.use_tls);
    }
}
