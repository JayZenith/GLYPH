#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub tags: Option<Vec<String>>,
}

pub fn merge_config(
    defaults: Config,
    file: PartialConfig,
    env: PartialConfig,
    cli: PartialConfig,
) -> Config {
    let host = defaults.host;
    let mut port = defaults.port;
    let mut tls = defaults.tls;
    let mut tags = defaults.tags;

    if let Some(p) = cli.port.or(env.port).or(file.port) {
        port = p;
    }

    if let Some(t) = cli.tls.or(env.tls).or(file.tls) {
        tls = t;
    }

    if let Some(file_tags) = file.tags {
        if !file_tags.is_empty() {
            tags = file_tags;
        }
    }
    if let Some(env_tags) = env.tags {
        if !env_tags.is_empty() {
            tags.extend(env_tags);
        }
    }
    if let Some(cli_tags) = cli.tags {
        if !cli_tags.is_empty() {
            tags = cli_tags;
        }
    }

    Config {
        host,
        port,
        tls,
        tags,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".to_string(),
            port: 8080,
            tls: false,
            tags: vec!["base".to_string()],
        }
    }

    #[test]
    fn later_layers_override_scalar_values() {
        let file = PartialConfig {
            host: Some("file.internal".to_string()),
            port: Some(7000),
            tls: Some(true),
            tags: None,
        };
        let env = PartialConfig {
            host: Some("env.internal".to_string()),
            port: None,
            tls: Some(false),
            tags: None,
        };
        let cli = PartialConfig {
            host: Some("cli.internal".to_string()),
            port: Some(9000),
            tls: None,
            tags: None,
        };

        let merged = merge_config(defaults(), file, env, cli);
        assert_eq!(merged.host, "cli.internal");
        assert_eq!(merged.port, 9000);
        assert!(!merged.tls);
    }

    #[test]
    fn env_tags_append_and_dedup_after_file_layer() {
        let file = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["file".to_string(), "shared".to_string()]),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["env".to_string(), "shared".to_string()]),
        };

        let merged = merge_config(defaults(), file, env, PartialConfig::default());
        assert_eq!(merged.tags, vec!["file", "shared", "env"]);
    }

    #[test]
    fn cli_tags_replace_previous_layers() {
        let file = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["file".to_string()]),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["env".to_string()]),
        };
        let cli = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["cli".to_string(), "picked".to_string()]),
        };

        let merged = merge_config(defaults(), file, env, cli);
        assert_eq!(merged.tags, vec!["cli", "picked"]);
    }

    #[test]
    fn empty_cli_tags_clear_all_previous_tags() {
        let file = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["file".to_string()]),
        };
        let env = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec!["env".to_string()]),
        };
        let cli = PartialConfig {
            host: None,
            port: None,
            tls: None,
            tags: Some(vec![]),
        };

        let merged = merge_config(defaults(), file, env, cli);
        assert!(merged.tags.is_empty());
    }
}
