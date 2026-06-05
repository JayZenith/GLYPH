#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Settings {
    pub endpoint: String,
    pub timeout_ms: u32,
    pub retries: u8,
    pub profile: String,
}

#[derive(Debug, Clone, Default)]
pub struct PartialSettings {
    pub endpoint: Option<String>,
    pub timeout_ms: Option<u32>,
    pub retries: Option<u8>,
    pub profile: Option<String>,
}

pub fn merge_settings(file: Option<PartialSettings>, env: Option<PartialSettings>) -> Settings {
    let file = file.unwrap_or_default();
    let env = env.unwrap_or_default();

    Settings {
        endpoint: env
            .endpoint
            .or(file.endpoint)
            .unwrap_or_else(|| "https://default.service".to_string()),
        timeout_ms: env.timeout_ms.or(file.timeout_ms).unwrap_or(1000),
        retries: env.retries.or(file.retries).unwrap_or(3),
        profile: file
            .profile
            .or(env.profile)
            .unwrap_or_else(|| "default".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ps(
        endpoint: Option<&str>,
        timeout_ms: Option<u32>,
        retries: Option<u8>,
        profile: Option<&str>,
    ) -> PartialSettings {
        PartialSettings {
            endpoint: endpoint.map(str::to_string),
            timeout_ms,
            retries,
            profile: profile.map(str::to_string),
        }
    }

    #[test]
    fn file_values_beat_env_values() {
        let file = ps(
            Some("https://file.service"),
            Some(2500),
            Some(7),
            Some("file-profile"),
        );
        let env = ps(
            Some("https://env.service"),
            Some(9000),
            Some(1),
            Some("env-profile"),
        );

        let merged = merge_settings(Some(file), Some(env));

        assert_eq!(
            merged,
            Settings {
                endpoint: "https://file.service".to_string(),
                timeout_ms: 2500,
                retries: 7,
                profile: "file-profile".to_string(),
            }
        );
    }

    #[test]
    fn env_fills_only_missing_file_values() {
        let file = ps(Some("https://file.service"), None, Some(4), None);
        let env = ps(None, Some(8000), Some(9), Some("env-profile"));

        let merged = merge_settings(Some(file), Some(env));

        assert_eq!(merged.endpoint, "https://file.service");
        assert_eq!(merged.timeout_ms, 8000);
        assert_eq!(merged.retries, 4);
        assert_eq!(merged.profile, "env-profile");
    }

    #[test]
    fn defaults_apply_when_both_sources_missing() {
        let merged = merge_settings(None, None);

        assert_eq!(
            merged,
            Settings {
                endpoint: "https://default.service".to_string(),
                timeout_ms: 1000,
                retries: 3,
                profile: "default".to_string(),
            }
        );
    }

    #[test]
    fn env_used_when_file_struct_absent() {
        let env = ps(
            Some("https://env-only.service"),
            Some(1200),
            Some(2),
            Some("env-only"),
        );

        let merged = merge_settings(None, Some(env));

        assert_eq!(
            merged,
            Settings {
                endpoint: "https://env-only.service".to_string(),
                timeout_ms: 1200,
                retries: 2,
                profile: "env-only".to_string(),
            }
        );
    }

    #[test]
    fn precedence_is_checked_per_field_not_per_source() {
        let file = ps(None, Some(3333), None, Some("file-profile"));
        let env = ps(Some("https://env.service"), Some(9999), Some(6), Some("env-profile"));

        let merged = merge_settings(Some(file), Some(env));

        assert_eq!(merged.endpoint, "https://env.service");
        assert_eq!(merged.timeout_ms, 3333);
        assert_eq!(merged.retries, 6);
        assert_eq!(merged.profile, "file-profile");
    }
}
