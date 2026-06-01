#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub tls: Option<bool>,
    pub timeout_ms: Option<u64>,
    pub retries: Option<u8>,
}

impl Config {
    pub fn new() -> Self {
        Self {
            host: None,
            port: None,
            tls: None,
            timeout_ms: None,
            retries: None,
        }
    }
}

pub fn merge_config(defaults: &Config, file: &Config, env: &Config) -> Config {
    Config {
        host: file.host.clone().or(defaults.host.clone()),
        port: defaults.port.or(file.port),
        tls: file.tls.or(env.tls).or(defaults.tls),
        timeout_ms: env.timeout_ms.or(file.timeout_ms).or(defaults.timeout_ms),
        retries: file.retries.or(env.retries).or(defaults.retries).filter(|v| *v > 0),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(
        host: Option<&str>,
        port: Option<u16>,
        tls: Option<bool>,
        timeout_ms: Option<u64>,
        retries: Option<u8>,
    ) -> Config {
        Config {
            host: host.map(str::to_string),
            port,
            tls,
            timeout_ms,
            retries,
        }
    }

    #[test]
    fn env_has_highest_precedence_for_every_field() {
        let defaults = cfg(Some("default.local"), Some(80), Some(false), Some(1000), Some(3));
        let file = cfg(Some("file.local"), Some(8080), Some(false), Some(2000), Some(4));
        let env = cfg(Some("env.local"), Some(9090), Some(true), Some(3000), Some(5));

        let merged = merge_config(&defaults, &file, &env);

        assert_eq!(merged.host.as_deref(), Some("env.local"));
        assert_eq!(merged.port, Some(9090));
        assert_eq!(merged.tls, Some(true));
        assert_eq!(merged.timeout_ms, Some(3000));
        assert_eq!(merged.retries, Some(5));
    }

    #[test]
    fn falls_back_from_env_to_file_to_defaults() {
        let defaults = cfg(Some("default.local"), Some(80), Some(true), Some(1000), Some(3));
        let file = cfg(Some("file.local"), Some(8080), None, Some(2500), Some(4));
        let env = cfg(None, None, None, None, None);

        let merged = merge_config(&defaults, &file, &env);

        assert_eq!(merged.host.as_deref(), Some("file.local"));
        assert_eq!(merged.port, Some(8080));
        assert_eq!(merged.tls, Some(true));
        assert_eq!(merged.timeout_ms, Some(2500));
        assert_eq!(merged.retries, Some(4));
    }

    #[test]
    fn zero_retries_from_higher_precedence_layer_is_respected() {
        let defaults = cfg(None, None, None, None, Some(3));
        let file = cfg(None, None, None, None, Some(1));
        let env = cfg(None, None, None, None, Some(0));

        let merged = merge_config(&defaults, &file, &env);
        assert_eq!(merged.retries, Some(0));
    }

    #[test]
    fn false_tls_from_env_overrides_true_from_lower_layers() {
        let defaults = cfg(None, None, Some(true), None, None);
        let file = cfg(None, None, Some(true), None, None);
        let env = cfg(None, None, Some(false), None, None);

        let merged = merge_config(&defaults, &file, &env);
        assert_eq!(merged.tls, Some(false));
    }
}
