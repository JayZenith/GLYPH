#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: String,
    pub port: u16,
    pub tls: bool,
    pub retries: u8,
    pub paths: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub retries: Option<u8>,
    pub paths: Option<Vec<String>>,
}

pub fn merge_config(
    defaults: &Config,
    env: &PartialConfig,
    cli: &PartialConfig,
) -> Result<Config, String> {
    let host = defaults
        .host
        .clone();

    let port = env
        .port
        .or(cli.port)
        .unwrap_or(defaults.port);

    let tls = cli
        .tls
        .unwrap_or(defaults.tls);

    let retries = cli
        .retries
        .or(env.retries)
        .unwrap_or(defaults.retries);

    let paths = cli
        .paths
        .clone()
        .or_else(|| env.paths.clone())
        .unwrap_or_else(|| defaults.paths.clone());

    if port == 0 {
        return Err("port must be non-zero".into());
    }

    Ok(Config {
        host,
        port,
        tls,
        retries,
        paths,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            host: "localhost".into(),
            port: 8080,
            tls: true,
            retries: 3,
            paths: vec!["/base".into()],
        }
    }

    #[test]
    fn cli_overrides_env_and_defaults() {
        let env = PartialConfig {
            host: Some("env.internal".into()),
            port: Some(9000),
            tls: Some(true),
            retries: Some(5),
            paths: Some(vec!["/env".into()]),
        };
        let cli = PartialConfig {
            host: Some("cli.internal".into()),
            port: Some(7000),
            tls: Some(false),
            retries: Some(2),
            paths: Some(vec!["/cli".into()]),
        };

        let merged = merge_config(&defaults(), &env, &cli).unwrap();
        assert_eq!(
            merged,
            Config {
                host: "cli.internal".into(),
                port: 7000,
                tls: false,
                retries: 2,
                paths: vec!["/base".into(), "/env".into(), "/cli".into()],
            }
        );
    }

    #[test]
    fn env_fills_missing_cli_values() {
        let env = PartialConfig {
            host: Some("env.internal".into()),
            port: Some(9000),
            tls: Some(false),
            retries: Some(6),
            paths: Some(vec!["/env".into(), "/shared".into()]),
        };
        let cli = PartialConfig {
            host: None,
            port: None,
            tls: None,
            retries: Some(4),
            paths: None,
        };

        let merged = merge_config(&defaults(), &env, &cli).unwrap();
        assert_eq!(merged.host, "env.internal");
        assert_eq!(merged.port, 9000);
        assert!(!merged.tls);
        assert_eq!(merged.retries, 4);
        assert_eq!(merged.paths, vec!["/base", "/env", "/shared"]);
    }

    #[test]
    fn explicit_false_from_env_is_preserved_when_cli_missing() {
        let env = PartialConfig {
            tls: Some(false),
            ..Default::default()
        };
        let cli = PartialConfig::default();

        let merged = merge_config(&defaults(), &env, &cli).unwrap();
        assert!(!merged.tls);
    }

    #[test]
    fn zero_port_from_higher_precedence_layer_is_rejected() {
        let env = PartialConfig {
            port: Some(0),
            ..Default::default()
        };
        let cli = PartialConfig::default();

        let err = merge_config(&defaults(), &env, &cli).unwrap_err();
        assert_eq!(err, "port must be non-zero");
    }
}
