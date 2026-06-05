#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Settings {
    pub endpoint: Option<String>,
    pub profile: Option<String>,
    pub retries: Option<u8>,
    pub timeout_ms: Option<u64>,
}

impl Settings {
    pub fn new(
        endpoint: Option<&str>,
        profile: Option<&str>,
        retries: Option<u8>,
        timeout_ms: Option<u64>,
    ) -> Self {
        Self {
            endpoint: endpoint.map(str::to_string),
            profile: profile.map(str::to_string),
            retries,
            timeout_ms,
        }
    }
}

pub fn merge_settings(file: &Settings, env: &Settings, user: &Settings) -> Settings {
    let mut merged = file.clone();

    if let Some(v) = &env.endpoint {
        merged.endpoint = Some(v.clone());
    }
    if let Some(v) = &env.profile {
        merged.profile = Some(v.clone());
    }
    if env.retries.is_some() {
        merged.retries = env.retries;
    }
    if env.timeout_ms.is_some() {
        merged.timeout_ms = env.timeout_ms;
    }

    if let Some(v) = &user.endpoint {
        merged.endpoint = Some(v.clone());
    }
    if let Some(v) = &user.profile {
        merged.profile = Some(v.clone());
    }
    if user.retries.is_some() {
        merged.retries = user.retries;
    }
    if user.timeout_ms.is_some() {
        merged.timeout_ms = user.timeout_ms;
    }

    merged
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_fills_missing_fields_from_file() {
        let file = Settings::new(Some("https://file"), None, Some(3), None);
        let env = Settings::new(None, Some("staging"), Some(9), Some(800));
        let user = Settings::default();

        let merged = merge_settings(&file, &env, &user);

        assert_eq!(
            merged,
            Settings::new(Some("https://file"), Some("staging"), Some(3), Some(800))
        );
    }

    #[test]
    fn file_values_beat_env_when_both_present() {
        let file = Settings::new(Some("https://file"), Some("prod"), Some(2), Some(1500));
        let env = Settings::new(Some("https://env"), Some("dev"), Some(7), Some(900));
        let user = Settings::default();

        let merged = merge_settings(&file, &env, &user);

        assert_eq!(
            merged,
            Settings::new(Some("https://file"), Some("prod"), Some(2), Some(1500))
        );
    }

    #[test]
    fn user_overrides_both_file_and_env() {
        let file = Settings::new(Some("https://file"), Some("prod"), Some(2), None);
        let env = Settings::new(Some("https://env"), Some("dev"), Some(7), Some(900));
        let user = Settings::new(None, Some("cli"), Some(1), Some(3000));

        let merged = merge_settings(&file, &env, &user);

        assert_eq!(
            merged,
            Settings::new(Some("https://file"), Some("cli"), Some(1), Some(3000))
        );
    }

    #[test]
    fn mixed_precedence_is_applied_per_field() {
        let file = Settings::new(None, Some("file-profile"), None, Some(1200));
        let env = Settings::new(Some("https://env"), Some("env-profile"), Some(4), Some(400));
        let user = Settings::new(Some("https://user"), None, None, None);

        let merged = merge_settings(&file, &env, &user);

        assert_eq!(merged.endpoint.as_deref(), Some("https://user"));
        assert_eq!(merged.profile.as_deref(), Some("file-profile"));
        assert_eq!(merged.retries, Some(4));
        assert_eq!(merged.timeout_ms, Some(1200));
    }
}
