use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct AppConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub log_level: Option<String>,
    pub cache_enabled: Option<bool>,
}

fn parse_bool(raw: &str) -> Option<bool> {
    match raw {
        "1" | "true" | "TRUE" | "yes" | "on" => Some(true),
        "0" | "false" | "FALSE" | "no" | "off" => Some(false),
        _ => None,
    }
}

pub fn merge_config(file: AppConfig, env: &HashMap<String, String>) -> AppConfig {
    AppConfig {
        host: env.get("APP_HOST").cloned().or(file.host),
        port: env
            .get("APP_PORT")
            .and_then(|v| v.parse::<u16>().ok())
            .or(file.port),
        log_level: env.get("APP_LOG").cloned().or(file.log_level),
        cache_enabled: env
            .get("APP_CACHE")
            .and_then(|v| parse_bool(v))
            .or(file.cache_enabled),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn env(pairs: &[(&str, &str)]) -> HashMap<String, String> {
        let mut m = HashMap::new();
        for (k, v) in pairs {
            m.insert((*k).to_string(), (*v).to_string());
        }
        m
    }

    #[test]
    fn env_fills_missing_fields() {
        let file = AppConfig {
            host: None,
            port: None,
            log_level: None,
            cache_enabled: None,
        };
        let merged = merge_config(
            file,
            &env(&[
                ("APP_HOST", "env.example"),
                ("APP_PORT", "7000"),
                ("APP_LOG", "debug"),
                ("APP_CACHE", "yes"),
            ]),
        );
        assert_eq!(
            merged,
            AppConfig {
                host: Some("env.example".to_string()),
                port: Some(7000),
                log_level: Some("debug".to_string()),
                cache_enabled: Some(true),
            }
        );
    }

    #[test]
    fn file_values_beat_env_values_for_all_fields() {
        let file = AppConfig {
            host: Some("file.example".to_string()),
            port: Some(8080),
            log_level: Some("warn".to_string()),
            cache_enabled: Some(false),
        };
        let merged = merge_config(
            file,
            &env(&[
                ("APP_HOST", "env.example"),
                ("APP_PORT", "7000"),
                ("APP_LOG", "debug"),
                ("APP_CACHE", "yes"),
            ]),
        );
        assert_eq!(
            merged,
            AppConfig {
                host: Some("file.example".to_string()),
                port: Some(8080),
                log_level: Some("warn".to_string()),
                cache_enabled: Some(false),
            }
        );
    }

    #[test]
    fn invalid_env_values_do_not_block_file_values() {
        let file = AppConfig {
            host: Some("file.example".to_string()),
            port: Some(9000),
            log_level: Some("info".to_string()),
            cache_enabled: Some(true),
        };
        let merged = merge_config(
            file,
            &env(&[("APP_PORT", "not-a-number"), ("APP_CACHE", "maybe")]),
        );
        assert_eq!(merged.port, Some(9000));
        assert_eq!(merged.cache_enabled, Some(true));
        assert_eq!(merged.host, Some("file.example".to_string()));
        assert_eq!(merged.log_level, Some("info".to_string()));
    }

    #[test]
    fn merge_is_field_by_field_not_all_or_nothing() {
        let file = AppConfig {
            host: Some("file.example".to_string()),
            port: None,
            log_level: Some("error".to_string()),
            cache_enabled: None,
        };
        let merged = merge_config(
            file,
            &env(&[
                ("APP_HOST", "env.example"),
                ("APP_PORT", "7001"),
                ("APP_LOG", "debug"),
                ("APP_CACHE", "off"),
            ]),
        );
        assert_eq!(
            merged,
            AppConfig {
                host: Some("file.example".to_string()),
                port: Some(7001),
                log_level: Some("error".to_string()),
                cache_enabled: Some(false),
            }
        );
    }
}
