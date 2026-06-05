#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Config {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub retries: Option<u32>,
    pub verbose: Option<bool>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedConfig {
    pub endpoint: String,
    pub token: String,
    pub profile: String,
    pub retries: u32,
    pub verbose: bool,
}

pub fn merge_config(file: Option<Config>, env: Option<Config>) -> ResolvedConfig {
    let file = file.unwrap_or_default();
    let env = env.unwrap_or_default();

    ResolvedConfig {
        endpoint: env
            .endpoint
            .or(file.endpoint)
            .unwrap_or_else(|| "https://api.default.local".to_string()),
        token: env
            .token
            .or(file.token)
            .unwrap_or_else(|| "anonymous".to_string()),
        profile: env
            .profile
            .or(file.profile)
            .unwrap_or_else(|| "default".to_string()),
        retries: env.retries.or(file.retries).unwrap_or(3),
        verbose: env.verbose.or(file.verbose).unwrap_or(false),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(
        endpoint: Option<&str>,
        token: Option<&str>,
        profile: Option<&str>,
        retries: Option<u32>,
        verbose: Option<bool>,
    ) -> Config {
        Config {
            endpoint: endpoint.map(str::to_string),
            token: token.map(str::to_string),
            profile: profile.map(str::to_string),
            retries,
            verbose,
        }
    }

    #[test]
    fn file_values_beat_env_values_for_all_fields() {
        let file = cfg(
            Some("https://file.service"),
            Some("file-token"),
            Some("file-profile"),
            Some(7),
            Some(false),
        );
        let env = cfg(
            Some("https://env.service"),
            Some("env-token"),
            Some("env-profile"),
            Some(2),
            Some(true),
        );

        let merged = merge_config(Some(file), Some(env));

        assert_eq!(merged.endpoint, "https://file.service");
        assert_eq!(merged.token, "file-token");
        assert_eq!(merged.profile, "file-profile");
        assert_eq!(merged.retries, 7);
        assert!(!merged.verbose);
    }

    #[test]
    fn env_only_fills_missing_file_values() {
        let file = cfg(Some("https://file.service"), None, Some("file-profile"), None, None);
        let env = cfg(None, Some("env-token"), Some("env-profile"), Some(8), Some(true));

        let merged = merge_config(Some(file), Some(env));

        assert_eq!(merged.endpoint, "https://file.service");
        assert_eq!(merged.token, "env-token");
        assert_eq!(merged.profile, "file-profile");
        assert_eq!(merged.retries, 8);
        assert!(merged.verbose);
    }

    #[test]
    fn defaults_apply_only_when_both_layers_are_missing() {
        let file = cfg(None, None, None, None, None);
        let env = cfg(None, None, None, None, None);

        let merged = merge_config(Some(file), Some(env));

        assert_eq!(merged.endpoint, "https://api.default.local");
        assert_eq!(merged.token, "anonymous");
        assert_eq!(merged.profile, "default");
        assert_eq!(merged.retries, 3);
        assert!(!merged.verbose);
    }

    #[test]
    fn none_inputs_are_treated_like_empty_layers() {
        let merged = merge_config(
            None,
            Some(cfg(Some("https://env.service"), None, None, Some(4), Some(true))),
        );

        assert_eq!(merged.endpoint, "https://env.service");
        assert_eq!(merged.token, "anonymous");
        assert_eq!(merged.profile, "default");
        assert_eq!(merged.retries, 4);
        assert!(merged.verbose);
    }

    #[test]
    fn false_in_file_is_still_an_explicit_override() {
        let file = cfg(None, None, None, None, Some(false));
        let env = cfg(None, None, None, None, Some(true));

        let merged = merge_config(Some(file), Some(env));

        assert!(!merged.verbose);
    }
}
