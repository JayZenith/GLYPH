#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct AppConfig {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub region: Option<String>,
    pub retries: Option<u32>,
    pub verbose: Option<bool>,
}

fn clean_text(v: &str) -> Option<String> {
    let t = v.trim();
    if t.is_empty() { None } else { Some(t.to_string()) }
}

fn parse_u32(v: &str) -> Option<u32> {
    v.trim().parse().ok()
}

fn parse_bool(v: &str) -> Option<bool> {
    match v.trim() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

pub fn merge_config(file_cfg: AppConfig, env: &[(&str, &str)]) -> AppConfig {
    let mut merged = file_cfg.clone();

    for (key, value) in env {
        match *key {
            "APP_ENDPOINT" => merged.endpoint = clean_text(value),
            "APP_TOKEN" => merged.token = clean_text(value),
            "APP_REGION" => merged.region = clean_text(value),
            "APP_RETRIES" => merged.retries = parse_u32(value),
            "APP_VERBOSE" => merged.verbose = parse_bool(value),
            _ => {}
        }
    }

    merged
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_fills_missing_fields() {
        let file_cfg = AppConfig {
            endpoint: None,
            token: None,
            region: Some("eu-west-1".into()),
            retries: None,
            verbose: None,
        };

        let merged = merge_config(
            file_cfg,
            &[
                ("APP_ENDPOINT", "https://env.example"),
                ("APP_TOKEN", "env-token"),
                ("APP_REGION", "us-east-1"),
                ("APP_RETRIES", "5"),
                ("APP_VERBOSE", "true"),
            ],
        );

        assert_eq!(merged.endpoint.as_deref(), Some("https://env.example"));
        assert_eq!(merged.token.as_deref(), Some("env-token"));
        assert_eq!(merged.region.as_deref(), Some("eu-west-1"));
        assert_eq!(merged.retries, Some(5));
        assert_eq!(merged.verbose, Some(true));
    }

    #[test]
    fn file_values_win_over_env_values() {
        let file_cfg = AppConfig {
            endpoint: Some("https://file.example".into()),
            token: Some("file-token".into()),
            region: Some("ap-south-1".into()),
            retries: Some(2),
            verbose: Some(false),
        };

        let merged = merge_config(
            file_cfg,
            &[
                ("APP_ENDPOINT", "https://env.example"),
                ("APP_TOKEN", "env-token"),
                ("APP_REGION", "us-east-1"),
                ("APP_RETRIES", "8"),
                ("APP_VERBOSE", "true"),
            ],
        );

        assert_eq!(merged.endpoint.as_deref(), Some("https://file.example"));
        assert_eq!(merged.token.as_deref(), Some("file-token"));
        assert_eq!(merged.region.as_deref(), Some("ap-south-1"));
        assert_eq!(merged.retries, Some(2));
        assert_eq!(merged.verbose, Some(false));
    }

    #[test]
    fn invalid_env_values_do_not_clear_or_override_existing_file_values() {
        let file_cfg = AppConfig {
            endpoint: Some("https://file.example".into()),
            token: Some("file-token".into()),
            region: Some("eu-central-1".into()),
            retries: Some(4),
            verbose: Some(true),
        };

        let merged = merge_config(
            file_cfg,
            &[
                ("APP_ENDPOINT", "   "),
                ("APP_TOKEN", ""),
                ("APP_REGION", "   "),
                ("APP_RETRIES", "not-a-number"),
                ("APP_VERBOSE", "maybe"),
            ],
        );

        assert_eq!(merged.endpoint.as_deref(), Some("https://file.example"));
        assert_eq!(merged.token.as_deref(), Some("file-token"));
        assert_eq!(merged.region.as_deref(), Some("eu-central-1"));
        assert_eq!(merged.retries, Some(4));
        assert_eq!(merged.verbose, Some(true));
    }

    #[test]
    fn invalid_env_values_leave_missing_fields_missing() {
        let file_cfg = AppConfig::default();

        let merged = merge_config(
            file_cfg,
            &[
                ("APP_ENDPOINT", " "),
                ("APP_TOKEN", ""),
                ("APP_REGION", "   "),
                ("APP_RETRIES", "x"),
                ("APP_VERBOSE", "sometimes"),
            ],
        );

        assert_eq!(merged.endpoint, None);
        assert_eq!(merged.token, None);
        assert_eq!(merged.region, None);
        assert_eq!(merged.retries, None);
        assert_eq!(merged.verbose, None);
    }

    #[test]
    fn mixed_sources_merge_per_field() {
        let file_cfg = AppConfig {
            endpoint: Some("https://file.example".into()),
            token: None,
            region: None,
            retries: Some(7),
            verbose: None,
        };

        let merged = merge_config(
            file_cfg,
            &[
                ("APP_ENDPOINT", "https://env.example"),
                ("APP_TOKEN", "env-token"),
                ("APP_REGION", "sa-east-1"),
                ("APP_RETRIES", "3"),
                ("APP_VERBOSE", "off"),
            ],
        );

        assert_eq!(merged.endpoint.as_deref(), Some("https://file.example"));
        assert_eq!(merged.token.as_deref(), Some("env-token"));
        assert_eq!(merged.region.as_deref(), Some("sa-east-1"));
        assert_eq!(merged.retries, Some(7));
        assert_eq!(merged.verbose, Some(false));
    }
}
