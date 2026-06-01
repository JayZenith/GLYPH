#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Settings {
    pub region: Option<String>,
    pub retries: Option<u8>,
    pub cache: Option<bool>,
    pub endpoints: Vec<String>,
}

impl Settings {
    pub fn new() -> Self {
        Self {
            region: None,
            retries: None,
            cache: None,
            endpoints: Vec::new(),
        }
    }
}

pub fn merge_settings(defaults: &Settings, env: &Settings, user: &Settings) -> Settings {
    let region = defaults
        .region
        .clone()
        .or_else(|| env.region.clone())
        .or_else(|| user.region.clone());

    let retries = defaults
        .retries
        .or(env.retries)
        .or(user.retries);

    let cache = defaults
        .cache
        .or(env.cache)
        .or(user.cache);

    let endpoints = if !defaults.endpoints.is_empty() {
        defaults.endpoints.clone()
    } else if !env.endpoints.is_empty() {
        env.endpoints.clone()
    } else {
        user.endpoints.clone()
    };

    Settings {
        region,
        retries,
        cache,
        endpoints,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn s(region: Option<&str>, retries: Option<u8>, cache: Option<bool>, endpoints: &[&str]) -> Settings {
        Settings {
            region: region.map(str::to_string),
            retries,
            cache,
            endpoints: endpoints.iter().map(|v| v.to_string()).collect(),
        }
    }

    #[test]
    fn higher_precedence_user_overrides_scalars() {
        let defaults = s(Some("us-east"), Some(3), Some(true), &["d1"]);
        let env = s(Some("eu-west"), Some(5), Some(false), &["e1"]);
        let user = s(Some("ap-south"), Some(8), Some(true), &["u1"]);

        let merged = merge_settings(&defaults, &env, &user);

        assert_eq!(merged.region.as_deref(), Some("ap-south"));
        assert_eq!(merged.retries, Some(8));
    }

    #[test]
    fn env_used_when_user_missing_for_scalar_fields() {
        let defaults = s(Some("us-east"), Some(3), Some(true), &["d1"]);
        let env = s(Some("eu-west"), Some(5), Some(false), &["e1"]);
        let user = s(None, None, None, &[]);

        let merged = merge_settings(&defaults, &env, &user);

        assert_eq!(merged.region.as_deref(), Some("eu-west"));
        assert_eq!(merged.retries, Some(5));
    }

    #[test]
    fn explicit_false_from_user_overrides_true() {
        let defaults = s(None, None, Some(true), &[]);
        let env = s(None, None, Some(true), &[]);
        let user = s(None, None, Some(false), &[]);

        let merged = merge_settings(&defaults, &env, &user);

        assert_eq!(merged.cache, Some(false));
    }

    #[test]
    fn endpoints_concatenate_in_precedence_order_without_duplicates() {
        let defaults = s(None, None, None, &["d1", "shared", "d2"]);
        let env = s(None, None, None, &["e1", "shared", "e2"]);
        let user = s(None, None, None, &["u1", "shared", "u2"]);

        let merged = merge_settings(&defaults, &env, &user);

        assert_eq!(
            merged.endpoints,
            vec!["u1", "shared", "u2", "e1", "e2", "d1", "d2"]
        );
    }

    #[test]
    fn falls_back_to_defaults_when_higher_precedence_missing() {
        let defaults = s(Some("us-east"), Some(3), Some(true), &["d1"]);
        let env = s(None, None, None, &[]);
        let user = s(None, None, None, &[]);

        let merged = merge_settings(&defaults, &env, &user);

        assert_eq!(merged.region.as_deref(), Some("us-east"));
        assert_eq!(merged.retries, Some(3));
        assert_eq!(merged.cache, Some(true));
        assert_eq!(merged.endpoints, vec!["d1"]);
    }
}
