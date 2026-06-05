#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Config {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub timeout_secs: Option<u64>,
    pub retries: Option<u8>,
    pub use_tls: Option<bool>,
}

impl Config {
    pub fn with_endpoint(mut self, v: &str) -> Self {
        self.endpoint = Some(v.to_string());
        self
    }
    pub fn with_token(mut self, v: &str) -> Self {
        self.token = Some(v.to_string());
        self
    }
    pub fn with_profile(mut self, v: &str) -> Self {
        self.profile = Some(v.to_string());
        self
    }
    pub fn with_timeout(mut self, v: u64) -> Self {
        self.timeout_secs = Some(v);
        self
    }
    pub fn with_retries(mut self, v: u8) -> Self {
        self.retries = Some(v);
        self
    }
    pub fn with_tls(mut self, v: bool) -> Self {
        self.use_tls = Some(v);
        self
    }
}

pub fn merge_config(defaults: Config, file: Config, env: Config, user: Config) -> Config {
    Config {
        endpoint: user.endpoint.or(env.endpoint).or(file.endpoint).or(defaults.endpoint),
        token: user.token.or(env.token).or(file.token).or(defaults.token),
        profile: user.profile.or(env.profile).or(file.profile).or(defaults.profile),
        timeout_secs: user.timeout_secs.or(env.timeout_secs).or(file.timeout_secs).or(defaults.timeout_secs),
        retries: user.retries.or(env.retries).or(file.retries).or(defaults.retries),
        use_tls: user.use_tls.or(env.use_tls).or(file.use_tls).or(defaults.use_tls),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config::default()
            .with_endpoint("https://default.service")
            .with_profile("default")
            .with_timeout(30)
            .with_retries(2)
            .with_tls(true)
    }

    #[test]
    fn explicit_file_and_user_values_beat_env() {
        let file = Config::default()
            .with_endpoint("https://file.service")
            .with_timeout(45)
            .with_tls(false);
        let env = Config::default()
            .with_endpoint("https://env.service")
            .with_timeout(60)
            .with_tls(true)
            .with_profile("env-profile");
        let user = Config::default()
            .with_endpoint("https://user.service")
            .with_timeout(15);

        let merged = merge_config(defaults(), file, env, user);

        assert_eq!(merged.endpoint.as_deref(), Some("https://user.service"));
        assert_eq!(merged.timeout_secs, Some(15));
        assert_eq!(merged.use_tls, Some(false));
        assert_eq!(merged.profile.as_deref(), Some("env-profile"));
    }

    #[test]
    fn env_fills_missing_fields_without_overriding_file() {
        let file = Config::default().with_profile("from-file");
        let env = Config::default()
            .with_token("env-token")
            .with_profile("from-env")
            .with_retries(9);
        let user = Config::default();

        let merged = merge_config(defaults(), file, env, user);

        assert_eq!(merged.token.as_deref(), Some("env-token"));
        assert_eq!(merged.profile.as_deref(), Some("from-file"));
        assert_eq!(merged.retries, Some(9));
        assert_eq!(merged.endpoint.as_deref(), Some("https://default.service"));
    }

    #[test]
    fn false_and_zero_like_values_are_still_explicit() {
        let file = Config::default().with_retries(0).with_tls(false);
        let env = Config::default().with_retries(7).with_tls(true);
        let user = Config::default();

        let merged = merge_config(defaults(), file, env, user);

        assert_eq!(merged.retries, Some(0));
        assert_eq!(merged.use_tls, Some(false));
    }

    #[test]
    fn defaults_only_apply_after_other_sources_are_missing() {
        let file = Config::default();
        let env = Config::default().with_token("env-token");
        let user = Config::default();

        let merged = merge_config(defaults(), file, env, user);

        assert_eq!(merged.endpoint.as_deref(), Some("https://default.service"));
        assert_eq!(merged.token.as_deref(), Some("env-token"));
        assert_eq!(merged.profile.as_deref(), Some("default"));
        assert_eq!(merged.timeout_secs, Some(30));
        assert_eq!(merged.retries, Some(2));
        assert_eq!(merged.use_tls, Some(true));
    }
}
