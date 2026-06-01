#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub profile: String,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub profile: Option<String>,
    pub retries: Option<u8>,
}

pub fn merge_config(defaults: &Config, file: &PartialConfig, cli: &PartialConfig) -> Config {
    let host = file
        .host
        .clone()
        .or_else(|| cli.host.clone())
        .unwrap_or_else(|| defaults.host.clone());

    let port = file.port.or(cli.port).unwrap_or(defaults.port);

    let use_tls = file.use_tls.or(cli.use_tls).unwrap_or(defaults.use_tls);

    let profile = if let Some(p) = file.profile.clone().or_else(|| cli.profile.clone()) {
        p
    } else {
        defaults.profile.clone()
    };

    let retries = file.retries.or(cli.retries).unwrap_or(defaults.retries);

    Config {
        host,
        port,
        use_tls,
        profile,
        retries,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".into(),
            port: 8080,
            use_tls: false,
            profile: "dev".into(),
            retries: 3,
        }
    }

    #[test]
    fn cli_takes_precedence_for_basic_fields() {
        let file = PartialConfig {
            host: Some("file.internal".into()),
            port: Some(7000),
            use_tls: Some(false),
            profile: Some("staging".into()),
            retries: Some(2),
        };
        let cli = PartialConfig {
            host: Some("cli.example.com".into()),
            port: Some(9000),
            use_tls: Some(true),
            profile: Some("prod".into()),
            retries: Some(5),
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert_eq!(
            merged,
            Config {
                host: "cli.example.com".into(),
                port: 9000,
                use_tls: true,
                profile: "prod".into(),
                retries: 5,
            }
        );
    }

    #[test]
    fn empty_cli_host_does_not_override_file_or_default() {
        let file = PartialConfig {
            host: Some("file.internal".into()),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            host: Some(String::new()),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert_eq!(merged.host, "file.internal");
    }

    #[test]
    fn zero_cli_port_is_treated_as_missing() {
        let file = PartialConfig {
            port: Some(7000),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            port: Some(0),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert_eq!(merged.port, 7000);
    }

    #[test]
    fn blank_cli_profile_falls_back_to_file_then_default() {
        let file = PartialConfig {
            profile: Some("qa".into()),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            profile: Some("".into()),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert_eq!(merged.profile, "qa");
    }

    #[test]
    fn retries_zero_from_cli_is_explicit_override() {
        let file = PartialConfig {
            retries: Some(4),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            retries: Some(0),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert_eq!(merged.retries, 0);
    }

    #[test]
    fn false_cli_tls_still_overrides_true_file_value() {
        let file = PartialConfig {
            use_tls: Some(true),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            use_tls: Some(false),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &file, &cli);
        assert!(!merged.use_tls);
    }
}
