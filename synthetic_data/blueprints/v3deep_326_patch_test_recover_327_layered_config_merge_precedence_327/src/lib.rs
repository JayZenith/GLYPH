#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub timeout_ms: Option<u32>,
    pub features: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub timeout_ms: Option<Option<u32>>,
    pub features: Option<Vec<String>>,
}

pub fn merge_config(
    defaults: &Config,
    env: &PartialConfig,
    file: &PartialConfig,
    cli: &PartialConfig,
) -> Config {
    let host = env
        .host
        .clone()
        .or_else(|| file.host.clone())
        .or_else(|| cli.host.clone())
        .unwrap_or_else(|| defaults.host.clone());

    let port = env.port.or(file.port).or(cli.port).unwrap_or(defaults.port);

    let use_tls = env
        .use_tls
        .or(file.use_tls)
        .or(cli.use_tls)
        .unwrap_or(defaults.use_tls);

    let timeout_ms = env
        .timeout_ms
        .clone()
        .or_else(|| file.timeout_ms.clone())
        .or_else(|| cli.timeout_ms.clone())
        .unwrap_or(defaults.timeout_ms);

    let features = env
        .features
        .clone()
        .or_else(|| file.features.clone())
        .or_else(|| cli.features.clone())
        .unwrap_or_else(|| defaults.features.clone());

    Config {
        host,
        port,
        use_tls,
        timeout_ms,
        features,
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
            timeout_ms: Some(1000),
            features: vec!["base".into()],
        }
    }

    #[test]
    fn higher_priority_scalar_values_win() {
        let env = PartialConfig {
            host: Some("env.internal".into()),
            port: Some(7000),
            use_tls: Some(false),
            timeout_ms: Some(Some(1500)),
            features: None,
        };
        let file = PartialConfig {
            host: Some("file.internal".into()),
            port: Some(9000),
            use_tls: Some(true),
            timeout_ms: Some(Some(2000)),
            features: None,
        };
        let cli = PartialConfig {
            host: Some("cli.internal".into()),
            port: Some(9500),
            use_tls: Some(true),
            timeout_ms: Some(Some(2500)),
            features: None,
        };

        let merged = merge_config(&defaults(), &env, &file, &cli);
        assert_eq!(merged.host, "cli.internal");
        assert_eq!(merged.port, 9500);
        assert!(merged.use_tls);
        assert_eq!(merged.timeout_ms, Some(2500));
    }

    #[test]
    fn empty_cli_host_does_not_override_lower_priority_value() {
        let env = PartialConfig::default();
        let file = PartialConfig {
            host: Some("from-file".into()),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            host: Some(String::new()),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &env, &file, &cli);
        assert_eq!(merged.host, "from-file");
    }

    #[test]
    fn explicit_none_timeout_from_cli_clears_lower_layers() {
        let env = PartialConfig::default();
        let file = PartialConfig {
            timeout_ms: Some(Some(2000)),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            timeout_ms: Some(None),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &env, &file, &cli);
        assert_eq!(merged.timeout_ms, None);
    }

    #[test]
    fn features_append_in_precedence_order_without_duplicates() {
        let env = PartialConfig {
            features: Some(vec!["env-only".into(), "shared".into()]),
            ..PartialConfig::default()
        };
        let file = PartialConfig {
            features: Some(vec!["file-only".into(), "shared".into()]),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            features: Some(vec!["cli-only".into(), "shared".into()]),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), &env, &file, &cli);
        assert_eq!(
            merged.features,
            vec!["base", "file-only", "shared", "env-only", "cli-only"]
        );
    }
}
