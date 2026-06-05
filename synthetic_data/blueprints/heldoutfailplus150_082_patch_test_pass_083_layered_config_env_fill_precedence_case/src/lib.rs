#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub profile: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FinalConfig {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub profile: String,
}

impl Default for FinalConfig {
    fn default() -> Self {
        Self {
            host: "127.0.0.1".to_string(),
            port: 8080,
            tls: false,
            profile: "dev".to_string(),
        }
    }
}

fn parse_bool_like(s: &str) -> Option<bool> {
    match s.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

pub fn merge_config(file: PartialConfig, env: PartialConfig) -> FinalConfig {
    let defaults = FinalConfig::default();
    FinalConfig {
        host: env.host.or(file.host).unwrap_or(defaults.host),
        port: env.port.or(file.port).unwrap_or(defaults.port),
        tls: env.tls.or(file.tls).unwrap_or(defaults.tls),
        profile: match env.profile.or(file.profile) {
            Some(p) if !p.is_empty() => p,
            _ => defaults.profile,
        },
    }
}

pub fn env_config(vars: &[(&str, &str)]) -> PartialConfig {
    let mut cfg = PartialConfig {
        host: None,
        port: None,
        tls: None,
        profile: None,
    };

    for (key, value) in vars {
        match *key {
            "APP_HOST" => cfg.host = Some((*value).to_string()),
            "APP_PORT" => {
                if let Ok(port) = value.parse::<u16>() {
                    cfg.port = Some(port);
                }
            }
            "APP_TLS" => cfg.tls = parse_bool_like(value),
            "APP_PROFILE" => cfg.profile = Some((*value).to_string()),
            _ => {}
        }
    }

    cfg
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pc(host: Option<&str>, port: Option<u16>, tls: Option<bool>, profile: Option<&str>) -> PartialConfig {
        PartialConfig {
            host: host.map(str::to_string),
            port,
            tls,
            profile: profile.map(str::to_string),
        }
    }

    #[test]
    fn file_values_override_env_values() {
        let file = pc(Some("db.internal"), Some(7000), Some(false), Some("prod"));
        let env = pc(Some("env.example"), Some(9000), Some(true), Some("staging"));

        let merged = merge_config(file, env);

        assert_eq!(merged.host, "db.internal");
        assert_eq!(merged.port, 7000);
        assert!(!merged.tls);
        assert_eq!(merged.profile, "prod");
    }

    #[test]
    fn env_fills_only_missing_fields() {
        let file = pc(Some("file-only"), None, None, Some("custom"));
        let env = pc(Some("env-host"), Some(8123), Some(true), Some("env-profile"));

        let merged = merge_config(file, env);

        assert_eq!(merged.host, "file-only");
        assert_eq!(merged.port, 8123);
        assert!(merged.tls);
        assert_eq!(merged.profile, "custom");
    }

    #[test]
    fn defaults_fill_when_both_sources_missing() {
        let merged = merge_config(pc(None, None, None, None), pc(None, None, None, None));

        assert_eq!(merged, FinalConfig::default());
    }

    #[test]
    fn env_parser_accepts_values_and_ignores_invalid_port() {
        let env = env_config(&[
            ("APP_HOST", "svc.local"),
            ("APP_PORT", "not-a-port"),
            ("APP_TLS", "on"),
            ("APP_PROFILE", "qa"),
        ]);

        assert_eq!(env.host.as_deref(), Some("svc.local"));
        assert_eq!(env.port, None);
        assert_eq!(env.tls, Some(true));
        assert_eq!(env.profile.as_deref(), Some("qa"));
    }

    #[test]
    fn empty_file_profile_still_counts_as_explicit_override() {
        let file = pc(None, None, None, Some(""));
        let env = pc(None, None, None, Some("staging"));

        let merged = merge_config(file, env);

        assert_eq!(merged.profile, "");
    }
}
