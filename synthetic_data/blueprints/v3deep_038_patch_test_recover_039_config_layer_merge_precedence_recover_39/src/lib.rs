#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppConfig {
    pub host: String,
    pub port: u16,
    pub use_tls: bool,
    pub retries: u8,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone, Default)]
pub struct PartialConfig {
    pub host: Option<String>,
    pub port: Option<u16>,
    pub use_tls: Option<bool>,
    pub retries: Option<u8>,
    pub tags: Option<Vec<String>>,
}

pub fn merge_config(
    defaults: &AppConfig,
    profile: Option<&PartialConfig>,
    runtime: Option<&PartialConfig>,
) -> AppConfig {
    let mut merged = defaults.clone();

    if let Some(p) = profile {
        if let Some(v) = &p.host {
            merged.host = v.clone();
        }
        if let Some(v) = p.port {
            merged.port = v;
        }
        if let Some(v) = p.use_tls {
            merged.use_tls = v;
        }
        if let Some(v) = p.retries {
            merged.retries = v;
        }
        if let Some(v) = &p.tags {
            merged.tags = v.clone();
        }
    }

    if let Some(r) = runtime {
        if let Some(v) = &r.host {
            merged.host = v.clone();
        }
        if let Some(v) = r.port {
            merged.port = v;
        }
        if let Some(v) = r.use_tls {
            merged.use_tls = v;
        }
        if let Some(v) = r.retries {
            merged.retries = v;
        }
        if let Some(v) = &r.tags {
            merged.tags.extend(v.clone());
        }
    }

    merged
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base() -> AppConfig {
        AppConfig {
            host: "localhost".into(),
            port: 8080,
            use_tls: false,
            retries: 3,
            tags: vec!["base".into()],
        }
    }

    #[test]
    fn runtime_overrides_profile_and_defaults() {
        let profile = PartialConfig {
            host: Some("profile.internal".into()),
            port: Some(9000),
            use_tls: Some(true),
            retries: Some(5),
            tags: Some(vec!["profile".into()]),
        };
        let runtime = PartialConfig {
            host: Some("cli.example.com".into()),
            port: Some(7000),
            use_tls: Some(false),
            retries: Some(1),
            tags: Some(vec!["runtime".into()]),
        };

        let merged = merge_config(&base(), Some(&profile), Some(&runtime));
        assert_eq!(merged.host, "cli.example.com");
        assert_eq!(merged.port, 7000);
        assert!(!merged.use_tls);
        assert_eq!(merged.retries, 1);
        assert_eq!(merged.tags, vec!["runtime"]);
    }

    #[test]
    fn empty_runtime_host_does_not_clear_profile_host() {
        let profile = PartialConfig {
            host: Some("profile.internal".into()),
            port: None,
            use_tls: None,
            retries: None,
            tags: None,
        };
        let runtime = PartialConfig {
            host: Some(String::new()),
            port: None,
            use_tls: None,
            retries: None,
            tags: None,
        };

        let merged = merge_config(&base(), Some(&profile), Some(&runtime));
        assert_eq!(merged.host, "profile.internal");
    }

    #[test]
    fn zero_runtime_port_keeps_lower_layer_port() {
        let profile = PartialConfig {
            host: None,
            port: Some(9090),
            use_tls: None,
            retries: None,
            tags: None,
        };
        let runtime = PartialConfig {
            host: None,
            port: Some(0),
            use_tls: None,
            retries: None,
            tags: None,
        };

        let merged = merge_config(&base(), Some(&profile), Some(&runtime));
        assert_eq!(merged.port, 9090);
    }

    #[test]
    fn zero_runtime_retries_keeps_lower_layer_retries() {
        let profile = PartialConfig {
            host: None,
            port: None,
            use_tls: None,
            retries: Some(4),
            tags: None,
        };
        let runtime = PartialConfig {
            host: None,
            port: None,
            use_tls: None,
            retries: Some(0),
            tags: None,
        };

        let merged = merge_config(&base(), Some(&profile), Some(&runtime));
        assert_eq!(merged.retries, 4);
    }

    #[test]
    fn empty_runtime_tags_clear_lower_layer_tags() {
        let profile = PartialConfig {
            host: None,
            port: None,
            use_tls: None,
            retries: None,
            tags: Some(vec!["profile".into(), "extra".into()]),
        };
        let runtime = PartialConfig {
            host: None,
            port: None,
            use_tls: None,
            retries: None,
            tags: Some(vec![]),
        };

        let merged = merge_config(&base(), Some(&profile), Some(&runtime));
        assert!(merged.tags.is_empty());
    }
}
