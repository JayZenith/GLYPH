#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub timeout_ms: u32,
    pub label: Option<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub timeout_ms: Option<u32>,
    pub label: Option<Option<String>>,
}

pub fn merge_config(
    defaults: &Config,
    env: Option<&PartialConfig>,
    file: Option<&PartialConfig>,
    cli: Option<&PartialConfig>,
) -> Config {
    let mut merged = defaults.clone();

    for layer in [env, file, cli] {
        if let Some(cfg) = layer {
            if let Some(host) = &cfg.host {
                merged.host = host.clone();
            }
            if let Some(port) = cfg.port {
                merged.port = port;
            }
            if let Some(use_tls) = cfg.use_tls {
                merged.use_tls = use_tls;
            }
            if let Some(timeout_ms) = cfg.timeout_ms {
                merged.timeout_ms = timeout_ms;
            }
            if let Some(label) = &cfg.label {
                merged.label = label.clone();
            }
        }
    }

    if merged.port == 0 {
        merged.port = defaults.port;
    }
    if merged.timeout_ms == 0 {
        merged.timeout_ms = defaults.timeout_ms;
    }
    if merged.host.is_empty() {
        merged.host = defaults.host.clone();
    }
    if merged.label.is_none() {
        merged.label = defaults.label.clone();
    }

    merged
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".to_string(),
            port: 8080,
            use_tls: false,
            timeout_ms: 5000,
            label: Some("svc".to_string()),
        }
    }

    #[test]
    fn precedence_is_defaults_then_file_then_env_then_cli() {
        let file = PartialConfig {
            host: Some("file.internal".to_string()),
            port: Some(7000),
            use_tls: Some(true),
            timeout_ms: Some(3000),
            label: Some(Some("file".to_string())),
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: Some(9000),
            use_tls: Some(false),
            timeout_ms: Some(2000),
            label: Some(Some("env".to_string())),
        };
        let cli = PartialConfig {
            host: Some("cli.internal".to_string()),
            port: Some(10000),
            use_tls: Some(true),
            timeout_ms: Some(1000),
            label: Some(Some("cli".to_string())),
        };

        let merged = merge_config(&defaults(), Some(&env), Some(&file), Some(&cli));

        assert_eq!(
            merged,
            Config {
                host: "cli.internal".to_string(),
                port: 10000,
                use_tls: true,
                timeout_ms: 1000,
                label: Some("cli".to_string()),
            }
        );
    }

    #[test]
    fn zero_and_empty_values_in_overrides_are_ignored() {
        let file = PartialConfig {
            host: Some("".to_string()),
            port: Some(0),
            use_tls: Some(true),
            timeout_ms: Some(0),
            label: Some(Some("from-file".to_string())),
        };
        let merged = merge_config(&defaults(), None, Some(&file), None);

        assert_eq!(merged.host, "localhost");
        assert_eq!(merged.port, 8080);
        assert_eq!(merged.timeout_ms, 5000);
        assert!(merged.use_tls);
        assert_eq!(merged.label, Some("from-file".to_string()));
    }

    #[test]
    fn explicit_none_label_from_higher_precedence_clears_lower_value() {
        let file = PartialConfig {
            label: Some(Some("from-file".to_string())),
            ..PartialConfig::default()
        };
        let env = PartialConfig {
            label: Some(None),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), Some(&env), Some(&file), None);

        assert_eq!(merged.label, None);
    }

    #[test]
    fn env_beats_file_when_cli_missing() {
        let file = PartialConfig {
            host: Some("file.internal".to_string()),
            port: Some(7000),
            timeout_ms: Some(3000),
            ..PartialConfig::default()
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: Some(9000),
            timeout_ms: Some(2000),
            ..PartialConfig::default()
        };

        let merged = merge_config(&defaults(), Some(&env), Some(&file), None);

        assert_eq!(merged.host, "env.internal");
        assert_eq!(merged.port, 9000);
        assert_eq!(merged.timeout_ms, 2000);
    }

    #[test]
    fn defaults_are_preserved_when_layers_absent() {
        let merged = merge_config(&defaults(), None, None, None);
        assert_eq!(merged, defaults());
    }
}
