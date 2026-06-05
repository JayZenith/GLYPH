#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct AppConfig {
    pub endpoint: Option<String>,
    pub region: Option<String>,
    pub retries: Option<u32>,
    pub profile: Option<String>,
    pub color: Option<bool>,
}

impl AppConfig {
    pub fn new() -> Self {
        Self::default()
    }
}

pub fn merge_config(defaults: &AppConfig, file: &AppConfig, user: &AppConfig, env: &AppConfig) -> AppConfig {
    AppConfig {
        endpoint: pick(&defaults.endpoint, &file.endpoint, &user.endpoint, &env.endpoint),
        region: pick(&defaults.region, &file.region, &user.region, &env.region),
        retries: pick(&defaults.retries, &file.retries, &user.retries, &env.retries),
        profile: pick(&defaults.profile, &file.profile, &user.profile, &env.profile),
        color: pick(&defaults.color, &file.color, &user.color, &env.color),
    }
}

fn pick<T: Clone>(defaults: &Option<T>, file: &Option<T>, user: &Option<T>, env: &Option<T>) -> Option<T> {
    env.clone()
        .or_else(|| user.clone())
        .or_else(|| file.clone())
        .or_else(|| defaults.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> AppConfig {
        AppConfig {
            endpoint: Some("https://default.service".into()),
            region: Some("us-east-1".into()),
            retries: Some(3),
            profile: Some("default".into()),
            color: Some(true),
        }
    }

    #[test]
    fn env_only_fills_missing_user_and_file_values() {
        let file = AppConfig {
            endpoint: Some("https://file.service".into()),
            region: None,
            retries: Some(8),
            profile: None,
            color: Some(false),
        };
        let user = AppConfig {
            endpoint: None,
            region: Some("eu-west-1".into()),
            retries: None,
            profile: Some("user-profile".into()),
            color: None,
        };
        let env = AppConfig {
            endpoint: Some("https://env.service".into()),
            region: Some("ap-south-1".into()),
            retries: Some(11),
            profile: Some("env-profile".into()),
            color: Some(true),
        };

        let merged = merge_config(&defaults(), &file, &user, &env);

        assert_eq!(merged.endpoint.as_deref(), Some("https://file.service"));
        assert_eq!(merged.region.as_deref(), Some("eu-west-1"));
        assert_eq!(merged.retries, Some(8));
        assert_eq!(merged.profile.as_deref(), Some("user-profile"));
        assert_eq!(merged.color, Some(false));
    }

    #[test]
    fn env_supplies_values_when_both_user_and_file_are_missing() {
        let file = AppConfig {
            endpoint: None,
            region: None,
            retries: Some(4),
            profile: None,
            color: None,
        };
        let user = AppConfig {
            endpoint: None,
            region: None,
            retries: None,
            profile: None,
            color: None,
        };
        let env = AppConfig {
            endpoint: Some("https://env.service".into()),
            region: Some("sa-east-1".into()),
            retries: Some(9),
            profile: Some("env-profile".into()),
            color: Some(false),
        };

        let merged = merge_config(&defaults(), &file, &user, &env);

        assert_eq!(merged.endpoint.as_deref(), Some("https://env.service"));
        assert_eq!(merged.region.as_deref(), Some("sa-east-1"));
        assert_eq!(merged.retries, Some(4));
        assert_eq!(merged.profile.as_deref(), Some("env-profile"));
        assert_eq!(merged.color, Some(false));
    }

    #[test]
    fn defaults_are_used_only_after_env_file_and_user() {
        let file = AppConfig {
            endpoint: None,
            region: Some("ca-central-1".into()),
            retries: None,
            profile: None,
            color: None,
        };
        let user = AppConfig::new();
        let env = AppConfig {
            endpoint: None,
            region: None,
            retries: None,
            profile: Some("env-profile".into()),
            color: None,
        };

        let merged = merge_config(&defaults(), &file, &user, &env);

        assert_eq!(merged.endpoint.as_deref(), Some("https://default.service"));
        assert_eq!(merged.region.as_deref(), Some("ca-central-1"));
        assert_eq!(merged.retries, Some(3));
        assert_eq!(merged.profile.as_deref(), Some("env-profile"));
        assert_eq!(merged.color, Some(true));
    }

    #[test]
    fn user_beats_file_when_both_are_explicit() {
        let file = AppConfig {
            endpoint: Some("https://file.service".into()),
            region: Some("file-region".into()),
            retries: Some(5),
            profile: Some("file-profile".into()),
            color: Some(true),
        };
        let user = AppConfig {
            endpoint: Some("https://user.service".into()),
            region: Some("user-region".into()),
            retries: Some(6),
            profile: Some("user-profile".into()),
            color: Some(false),
        };
        let env = AppConfig {
            endpoint: Some("https://env.service".into()),
            region: Some("env-region".into()),
            retries: Some(7),
            profile: Some("env-profile".into()),
            color: Some(true),
        };

        let merged = merge_config(&defaults(), &file, &user, &env);

        assert_eq!(merged.endpoint.as_deref(), Some("https://user.service"));
        assert_eq!(merged.region.as_deref(), Some("user-region"));
        assert_eq!(merged.retries, Some(6));
        assert_eq!(merged.profile.as_deref(), Some("user-profile"));
        assert_eq!(merged.color, Some(false));
    }
}
