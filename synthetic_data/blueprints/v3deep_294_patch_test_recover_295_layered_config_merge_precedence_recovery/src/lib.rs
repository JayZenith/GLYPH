#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub timeout_ms: u32,
    pub retries: u8,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub timeout_ms: Option<u32>,
    pub retries: Option<u8>,
}

impl PartialConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

pub fn resolve_config(
    defaults: &Config,
    profile: Option<&PartialConfig>,
    env: Option<&PartialConfig>,
    cli: Option<&PartialConfig>,
) -> Config {
    let mut merged = defaults.clone();

    if let Some(layer) = profile {
        apply_layer(&mut merged, layer);
    }
    if let Some(layer) = cli {
        apply_layer(&mut merged, layer);
    }
    if let Some(layer) = env {
        apply_layer(&mut merged, layer);
    }

    merged
}

fn apply_layer(target: &mut Config, layer: &PartialConfig) {
    if let Some(host) = &layer.host {
        target.host = host.clone();
    }
    if let Some(port) = layer.port {
        target.port = port;
    }
    if let Some(use_tls) = layer.use_tls {
        target.use_tls = use_tls;
    }
    if let Some(timeout_ms) = layer.timeout_ms {
        target.timeout_ms = timeout_ms;
    }
    if let Some(retries) = layer.retries {
        target.retries = retries.max(target.retries);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".to_string(),
            port: 8080,
            use_tls: false,
            timeout_ms: 1_000,
            retries: 2,
        }
    }

    #[test]
    fn precedence_is_defaults_then_profile_then_env_then_cli() {
        let profile = PartialConfig {
            host: Some("profile.internal".to_string()),
            port: Some(7000),
            use_tls: Some(true),
            timeout_ms: Some(4_000),
            retries: Some(4),
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: Some(9000),
            use_tls: Some(false),
            timeout_ms: Some(2_500),
            retries: Some(1),
        };
        let cli = PartialConfig {
            host: Some("cli.internal".to_string()),
            port: Some(9500),
            use_tls: Some(true),
            timeout_ms: Some(500),
            retries: Some(0),
        };

        let got = resolve_config(&defaults(), Some(&profile), Some(&env), Some(&cli));

        assert_eq!(
            got,
            Config {
                host: "cli.internal".to_string(),
                port: 9500,
                use_tls: true,
                timeout_ms: 500,
                retries: 0,
            }
        );
    }

    #[test]
    fn absent_fields_do_not_override_lower_layers() {
        let profile = PartialConfig {
            host: Some("profile.internal".to_string()),
            port: None,
            use_tls: Some(true),
            timeout_ms: None,
            retries: Some(5),
        };
        let env = PartialConfig {
            host: None,
            port: Some(8100),
            use_tls: None,
            timeout_ms: Some(2_000),
            retries: None,
        };
        let cli = PartialConfig {
            host: None,
            port: None,
            use_tls: None,
            timeout_ms: Some(250),
            retries: None,
        };

        let got = resolve_config(&defaults(), Some(&profile), Some(&env), Some(&cli));

        assert_eq!(got.host, "profile.internal");
        assert_eq!(got.port, 8100);
        assert!(got.use_tls);
        assert_eq!(got.timeout_ms, 250);
        assert_eq!(got.retries, 5);
    }

    #[test]
    fn later_layers_can_lower_numeric_values_and_disable_features() {
        let profile = PartialConfig {
            host: None,
            port: Some(8200),
            use_tls: Some(true),
            timeout_ms: Some(5_000),
            retries: Some(8),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            use_tls: Some(false),
            timeout_ms: Some(300),
            retries: Some(1),
        };

        let got = resolve_config(&defaults(), Some(&profile), Some(&env), None);

        assert_eq!(got.port, 8200);
        assert!(!got.use_tls);
        assert_eq!(got.timeout_ms, 300);
        assert_eq!(got.retries, 1);
    }
}
