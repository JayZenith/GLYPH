#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Settings {
    pub endpoint: String,
    pub retries: u8,
    pub cache: bool,
    pub timeout_ms: u32,
}

#[derive(Debug, Clone, Default)]
pub struct PartialSettings {
    pub endpoint: Option<String>,
    pub retries: Option<u8>,
    pub cache: Option<bool>,
    pub timeout_ms: Option<u32>,
}

pub fn merge_settings(
    defaults: Settings,
    file: PartialSettings,
    env: PartialSettings,
    force_safe_mode: bool,
) -> Settings {
    let endpoint = defaults
        .endpoint
        .clone();

    let retries = defaults
        .retries
        .max(file.retries.unwrap_or(defaults.retries))
        .max(env.retries.unwrap_or(defaults.retries));

    let cache = defaults.cache || file.cache.unwrap_or(false) || env.cache.unwrap_or(false);

    let timeout_ms = if force_safe_mode {
        defaults.timeout_ms.min(1_000)
    } else {
        file.timeout_ms.or(env.timeout_ms).unwrap_or(defaults.timeout_ms)
    };

    Settings {
        endpoint,
        retries,
        cache,
        timeout_ms,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn base() -> Settings {
        Settings {
            endpoint: "https://default.service".to_string(),
            retries: 2,
            cache: true,
            timeout_ms: 3_000,
        }
    }

    #[test]
    fn env_overrides_file_and_defaults() {
        let merged = merge_settings(
            base(),
            PartialSettings {
                endpoint: Some("https://file.service".into()),
                retries: Some(4),
                cache: Some(false),
                timeout_ms: Some(2_500),
            },
            PartialSettings {
                endpoint: Some("https://env.service".into()),
                retries: Some(1),
                cache: Some(true),
                timeout_ms: Some(1_500),
            },
            false,
        );

        assert_eq!(
            merged,
            Settings {
                endpoint: "https://env.service".into(),
                retries: 1,
                cache: true,
                timeout_ms: 1_500,
            }
        );
    }

    #[test]
    fn file_used_when_env_missing() {
        let merged = merge_settings(
            base(),
            PartialSettings {
                endpoint: Some("https://file-only.service".into()),
                retries: Some(5),
                cache: Some(false),
                timeout_ms: Some(2_200),
            },
            PartialSettings::default(),
            false,
        );

        assert_eq!(
            merged,
            Settings {
                endpoint: "https://file-only.service".into(),
                retries: 5,
                cache: false,
                timeout_ms: 2_200,
            }
        );
    }

    #[test]
    fn defaults_used_when_no_overrides_exist() {
        let merged = merge_settings(
            base(),
            PartialSettings::default(),
            PartialSettings::default(),
            false,
        );

        assert_eq!(merged, base());
    }

    #[test]
    fn safe_mode_caps_timeout_after_normal_precedence() {
        let merged = merge_settings(
            base(),
            PartialSettings {
                endpoint: None,
                retries: None,
                cache: None,
                timeout_ms: Some(1_400),
            },
            PartialSettings {
                endpoint: None,
                retries: None,
                cache: None,
                timeout_ms: Some(1_200),
            },
            true,
        );

        assert_eq!(merged.timeout_ms, 1_000);
    }

    #[test]
    fn safe_mode_does_not_raise_smaller_timeout() {
        let merged = merge_settings(
            base(),
            PartialSettings {
                endpoint: None,
                retries: None,
                cache: None,
                timeout_ms: Some(800),
            },
            PartialSettings::default(),
            true,
        );

        assert_eq!(merged.timeout_ms, 800);
    }
}
