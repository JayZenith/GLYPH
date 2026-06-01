#[derive(Clone, Debug)]
struct Config {
    timeout: Option<u32>,
    region: Option<&'static str>,
    retries: Option<u8>,
    tags: Option<Vec<&'static str>>,
}

#[derive(Clone, Debug)]
struct Profile {
    name: &'static str,
    enabled: bool,
    cfg: Config,
}

fn merge(base: &Config, overlay: &Config) -> Config {
    Config {
        timeout: base.timeout.or(overlay.timeout),
        region: base.region.or(overlay.region),
        retries: base.retries.or(overlay.retries),
        tags: base.tags.clone().or(overlay.tags.clone()),
    }
}

fn selected_profile<'a>(profiles: &'a [Profile], active: &str) -> Option<&'a Profile> {
    profiles.iter().find(|p| p.name == active)
}

fn format_tags(tags: Option<&Vec<&'static str>>) -> String {
    match tags {
        Some(v) if !v.is_empty() => v.join(","),
        _ => "(none)".to_string(),
    }
}

fn main() {
    let defaults = Config {
        timeout: Some(30),
        region: Some("us-east"),
        retries: Some(2),
        tags: Some(vec!["base", "stable"]),
    };

    let env_cfg = Config {
        timeout: Some(15),
        region: None,
        retries: Some(4),
        tags: Some(vec!["env"]),
    };

    let profiles = vec![
        Profile {
            name: "blue",
            enabled: false,
            cfg: Config {
                timeout: Some(20),
                region: Some("ap-south"),
                retries: Some(9),
                tags: Some(vec!["blue"]),
            },
        },
        Profile {
            name: "green",
            enabled: true,
            cfg: Config {
                timeout: None,
                region: Some("eu-west"),
                retries: None,
                tags: Some(vec!["green", "canary"]),
            },
        },
    ];

    let active_profile = "green";

    let cli_cfg = Config {
        timeout: None,
        region: None,
        retries: Some(5),
        tags: Some(vec![]),
    };

    let mut effective = defaults.clone();
    effective = merge(&env_cfg, &effective);
    if let Some(profile) = selected_profile(&profiles, active_profile) {
        effective = merge(&profile.cfg, &effective);
    }
    effective = merge(&cli_cfg, &effective);

    println!("timeout={}", effective.timeout.unwrap_or(0));
    println!("region={}", effective.region.unwrap_or("unset"));
    println!("retries={}", effective.retries.unwrap_or(0));
    println!("tags={}", format_tags(effective.tags.as_ref()));
}
