#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PartialConfig {
    pub endpoint: Option<String>,
    pub token: Option<String>,
    pub profile: Option<String>,
    pub timeout_secs: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Config {
    pub endpoint: String,
    pub token: String,
    pub profile: String,
    pub timeout_secs: u64,
}

pub fn merge_config(defaults: &Config, file_cfg: &PartialConfig, env_cfg: &PartialConfig) -> Config {
    Config {
        endpoint: pick_string(&env_cfg.endpoint, &file_cfg.endpoint, &defaults.endpoint),
        token: pick_string(&env_cfg.token, &file_cfg.token, &defaults.token),
        profile: pick_string(&env_cfg.profile, &file_cfg.profile, &defaults.profile),
        timeout_secs: pick_timeout(env_cfg.timeout_secs, file_cfg.timeout_secs, defaults.timeout_secs),
    }
}

fn pick_string(primary: &Option<String>, secondary: &Option<String>, default: &str) -> String {
    if let Some(v) = primary {
        if !v.is_empty() {
            return v.clone();
        }
    }
    if let Some(v) = secondary {
        return v.clone();
    }
    default.to_string()
}

fn pick_timeout(primary: Option<u64>, secondary: Option<u64>, default: u64) -> u64 {
    if let Some(v) = primary {
        return v;
    }
    if let Some(v) = secondary {
        if v > 0 {
            return v;
        }
    }
    default
}

#[cfg(test)]
mod tests {
    use super::*;

    fn defaults() -> Config {
        Config {
            endpoint: "https://default.service".to_string(),
            token: "default-token".to_string(),
            profile: "default".to_string(),
            timeout_secs: 30,
        }
    }

    #[test]
    fn file_values_override_env_values() {
        let file_cfg = PartialConfig {
            endpoint: Some("https://file.service".to_string()),
            token: Some("file-token".to_string()),
            profile: Some("file-profile".to_string()),
            timeout_secs: Some(15),
        };
        let env_cfg = PartialConfig {
            endpoint: Some("https://env.service".to_string()),
            token: Some("env-token".to_string()),
            profile: Some("env-profile".to_string()),
            timeout_secs: Some(90),
        };

        let merged = merge_config(&defaults(), &file_cfg, &env_cfg);
        assert_eq!(
            merged,
            Config {
                endpoint: "https://file.service".to_string(),
                token: "file-token".to_string(),
                profile: "file-profile".to_string(),
                timeout_secs: 15,
            }
        );
    }

    #[test]
    fn env_fills_only_missing_fields_from_file() {
        let file_cfg = PartialConfig {
            endpoint: Some("https://file.service".to_string()),
            token: None,
            profile: None,
            timeout_secs: None,
        };
        let env_cfg = PartialConfig {
            endpoint: Some("https://env.service".to_string()),
            token: Some("env-token".to_string()),
            profile: Some("env-profile".to_string()),
            timeout_secs: Some(45),
        };

        let merged = merge_config(&defaults(), &file_cfg, &env_cfg);
        assert_eq!(merged.endpoint, "https://file.service");
        assert_eq!(merged.token, "env-token");
        assert_eq!(merged.profile, "env-profile");
        assert_eq!(merged.timeout_secs, 45);
    }

    #[test]
    fn empty_file_string_is_still_explicit_and_blocks_env() {
        let file_cfg = PartialConfig {
            endpoint: Some("".to_string()),
            token: Some("".to_string()),
            profile: None,
            timeout_secs: None,
        };
        let env_cfg = PartialConfig {
            endpoint: Some("https://env.service".to_string()),
            token: Some("env-token".to_string()),
            profile: Some("env-profile".to_string()),
            timeout_secs: Some(12),
        };

        let merged = merge_config(&defaults(), &file_cfg, &env_cfg);
        assert_eq!(merged.endpoint, "");
        assert_eq!(merged.token, "");
        assert_eq!(merged.profile, "env-profile");
        assert_eq!(merged.timeout_secs, 12);
    }

    #[test]
    fn zero_timeout_from_file_is_explicit_and_beats_env() {
        let file_cfg = PartialConfig {
            endpoint: None,
            token: None,
            profile: None,
            timeout_secs: Some(0),
        };
        let env_cfg = PartialConfig {
            endpoint: Some("https://env.service".to_string()),
            token: None,
            profile: None,
            timeout_secs: Some(99),
        };

        let merged = merge_config(&defaults(), &file_cfg, &env_cfg);
        assert_eq!(merged.endpoint, "https://env.service");
        assert_eq!(merged.timeout_secs, 0);
    }

    #[test]
    fn defaults_are_used_only_when_both_layers_are_missing() {
        let file_cfg = PartialConfig {
            endpoint: None,
            token: None,
            profile: None,
            timeout_secs: None,
        };
        let env_cfg = PartialConfig {
            endpoint: None,
            token: None,
            profile: None,
            timeout_secs: None,
        };

        let merged = merge_config(&defaults(), &file_cfg, &env_cfg);
        assert_eq!(merged, defaults());
    }
}
