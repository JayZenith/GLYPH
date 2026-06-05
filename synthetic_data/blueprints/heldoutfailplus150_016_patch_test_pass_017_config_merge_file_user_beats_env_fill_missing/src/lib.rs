#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub profile: Option<String>,
    pub secure: Option<bool>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub profile: String,
    pub secure: bool,
}

impl Config {
    pub fn from_sources(file: Option<PartialConfig>, env: Option<PartialConfig>, user: Option<PartialConfig>) -> Self {
        let file = file.unwrap_or_default();
        let env = env.unwrap_or_default();
        let user = user.unwrap_or_default();

        Self {
            host: user.host.or(env.host).or(file.host).unwrap_or_else(|| "localhost".to_string()),
            port: user.port.or(env.port).or(file.port).unwrap_or(8080),
            profile: user.profile.or(env.profile).or(file.profile).unwrap_or_else(|| "dev".to_string()),
            secure: user.secure.or(env.secure).or(file.secure).unwrap_or(false),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{Config, PartialConfig};

    fn partial(host: Option<&str>, port: Option<u16>, profile: Option<&str>, secure: Option<bool>) -> PartialConfig {
        PartialConfig {
            host: host.map(str::to_string),
            port,
            profile: profile.map(str::to_string),
            secure,
        }
    }

    #[test]
    fn file_beats_env_when_both_set() {
        let file = partial(Some("file.internal"), Some(7000), Some("staging"), Some(true));
        let env = partial(Some("env.internal"), Some(9000), Some("prod"), Some(false));

        let cfg = Config::from_sources(Some(file), Some(env), None);

        assert_eq!(cfg.host, "file.internal");
        assert_eq!(cfg.port, 7000);
        assert_eq!(cfg.profile, "staging");
        assert_eq!(cfg.secure, true);
    }

    #[test]
    fn env_fills_only_missing_file_values() {
        let file = partial(Some("file.internal"), None, None, Some(true));
        let env = partial(Some("env.internal"), Some(9091), Some("prod"), Some(false));

        let cfg = Config::from_sources(Some(file), Some(env), None);

        assert_eq!(cfg.host, "file.internal");
        assert_eq!(cfg.port, 9091);
        assert_eq!(cfg.profile, "prod");
        assert_eq!(cfg.secure, true);
    }

    #[test]
    fn user_beats_both_file_and_env() {
        let file = partial(Some("file.internal"), Some(7000), Some("staging"), Some(false));
        let env = partial(Some("env.internal"), Some(9000), Some("prod"), Some(true));
        let user = partial(Some("cli.internal"), Some(5001), Some("debug"), Some(true));

        let cfg = Config::from_sources(Some(file), Some(env), Some(user));

        assert_eq!(cfg.host, "cli.internal");
        assert_eq!(cfg.port, 5001);
        assert_eq!(cfg.profile, "debug");
        assert_eq!(cfg.secure, true);
    }

    #[test]
    fn user_partial_still_preserves_file_over_env_for_other_fields() {
        let file = partial(Some("file.internal"), Some(7443), None, Some(false));
        let env = partial(Some("env.internal"), Some(9000), Some("prod"), Some(true));
        let user = partial(None, None, Some("debug"), None);

        let cfg = Config::from_sources(Some(file), Some(env), Some(user));

        assert_eq!(cfg.host, "file.internal");
        assert_eq!(cfg.port, 7443);
        assert_eq!(cfg.profile, "debug");
        assert_eq!(cfg.secure, false);
    }

    #[test]
    fn defaults_apply_only_when_all_sources_missing_field() {
        let cfg = Config::from_sources(
            Some(partial(None, None, None, None)),
            Some(partial(None, None, None, None)),
            Some(partial(None, None, None, None)),
        );

        assert_eq!(
            cfg,
            Config {
                host: "localhost".to_string(),
                port: 8080,
                profile: "dev".to_string(),
                secure: false,
            }
        );
    }
}
