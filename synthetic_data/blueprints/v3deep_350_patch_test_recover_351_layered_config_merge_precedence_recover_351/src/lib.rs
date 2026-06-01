#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub timeout_ms: u64,
    pub retries: u8,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub timeout_ms: Option<u64>,
    pub retries: Option<u8>,
    pub tags: Option<Vec<String>>,
}

pub fn merge_config(base: &Config, env: &PartialConfig, cli: &PartialConfig) -> Config {
    let mut out = base.clone();

    out.host = env.host.clone().or_else(|| cli.host.clone()).unwrap_or_else(|| out.host.clone());
    out.port = env.port.or(cli.port).unwrap_or(out.port);
    out.tls = env.tls.or(cli.tls).unwrap_or(out.tls);
    out.timeout_ms = env.timeout_ms.or(cli.timeout_ms).unwrap_or(out.timeout_ms);
    out.retries = env.retries.or(cli.retries).unwrap_or(out.retries);

    out.tags = match (&env.tags, &cli.tags) {
        (Some(env_tags), Some(cli_tags)) => {
            let mut merged = env_tags.clone();
            merged.extend(cli_tags.clone());
            merged
        }
        (Some(env_tags), None) => env_tags.clone(),
        (None, Some(cli_tags)) => cli_tags.clone(),
        (None, None) => out.tags.clone(),
    };

    if out.tls {
        out.timeout_ms += 500;
    }

    if out.port == 0 {
        out.port = 80;
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base() -> Config {
        Config {
            host: "localhost".into(),
            port: 8080,
            tls: false,
            timeout_ms: 1000,
            retries: 2,
            tags: vec!["base".into(), "core".into()],
        }
    }

    #[test]
    fn cli_overrides_env_and_base_for_scalar_fields() {
        let env = PartialConfig {
            host: Some("env.internal".into()),
            port: Some(9000),
            tls: Some(false),
            timeout_ms: Some(2000),
            retries: Some(4),
            tags: None,
        };
        let cli = PartialConfig {
            host: Some("cli.example.com".into()),
            port: Some(9443),
            tls: Some(true),
            timeout_ms: Some(3500),
            retries: Some(1),
            tags: None,
        };

        let merged = merge_config(&base(), &env, &cli);
        assert_eq!(merged.host, "cli.example.com");
        assert_eq!(merged.port, 9443);
        assert!(merged.tls);
        assert_eq!(merged.timeout_ms, 3500);
        assert_eq!(merged.retries, 1);
    }

    #[test]
    fn tags_are_replaced_by_highest_precedence_source_without_concatenation() {
        let env = PartialConfig {
            tags: Some(vec!["env".into(), "ops".into()]),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            tags: Some(vec!["cli".into()]),
            ..PartialConfig::default()
        };

        let merged = merge_config(&base(), &env, &cli);
        assert_eq!(merged.tags, vec!["cli"]);
    }

    #[test]
    fn empty_cli_tags_intentionally_clear_lower_layers() {
        let env = PartialConfig {
            tags: Some(vec!["env".into()]),
            ..PartialConfig::default()
        };
        let cli = PartialConfig {
            tags: Some(vec![]),
            ..PartialConfig::default()
        };

        let merged = merge_config(&base(), &env, &cli);
        assert!(merged.tags.is_empty());
    }

    #[test]
    fn base_values_remain_when_no_overrides_are_present() {
        let merged = merge_config(&base(), &PartialConfig::default(), &PartialConfig::default());
        assert_eq!(merged, base());
    }

    #[test]
    fn explicit_port_zero_is_preserved_and_not_rewritten() {
        let cli = PartialConfig {
            port: Some(0),
            ..PartialConfig::default()
        };

        let merged = merge_config(&base(), &PartialConfig::default(), &cli);
        assert_eq!(merged.port, 0);
    }
}
