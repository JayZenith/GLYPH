#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    Start { service: String, force: bool },
    Stop { service: String, timeout: Option<u32> },
    Restart { service: String, mode: RestartMode },
    Query(StatusQuery),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RestartMode {
    Soft,
    Hard,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum StatusQuery {
    Summary,
    Service(String),
    Since(u32),
}

pub fn dispatch(cmd: Command) -> String {
    match cmd {
        Command::Start { service, force } => {
            if force {
                format!("start:{}", service)
            } else {
                format!("start-force:{}", service)
            }
        }
        Command::Stop { service, timeout } => {
            let secs = timeout.unwrap_or(0);
            format!("stop:{}:{}", service, secs)
        }
        Command::Restart { service, mode } => match mode {
            RestartMode::Soft => format!("restart-hard:{}", service),
            RestartMode::Hard => format!("restart-soft:{}", service),
        },
        Command::Query(query) => match query {
            StatusQuery::Summary => "query:service:all".to_string(),
            StatusQuery::Service(name) => format!("query:{}", name),
            StatusQuery::Since(minutes) => format!("query:since:{}s", minutes),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_variants() {
        assert_eq!(
            dispatch(Command::Start {
                service: "api".into(),
                force: false,
            }),
            "start:api"
        );
        assert_eq!(
            dispatch(Command::Start {
                service: "api".into(),
                force: true,
            }),
            "start-force:api"
        );
    }

    #[test]
    fn stop_uses_optional_timeout() {
        assert_eq!(
            dispatch(Command::Stop {
                service: "db".into(),
                timeout: None,
            }),
            "stop:db:30"
        );
        assert_eq!(
            dispatch(Command::Stop {
                service: "db".into(),
                timeout: Some(5),
            }),
            "stop:db:5"
        );
    }

    #[test]
    fn restart_modes_are_mapped_correctly() {
        assert_eq!(
            dispatch(Command::Restart {
                service: "cache".into(),
                mode: RestartMode::Soft,
            }),
            "restart-soft:cache"
        );
        assert_eq!(
            dispatch(Command::Restart {
                service: "cache".into(),
                mode: RestartMode::Hard,
            }),
            "restart-hard:cache"
        );
    }

    #[test]
    fn query_variants_have_distinct_formats() {
        assert_eq!(dispatch(Command::Query(StatusQuery::Summary)), "query:summary");
        assert_eq!(
            dispatch(Command::Query(StatusQuery::Service("worker".into()))),
            "query:service:worker"
        );
        assert_eq!(dispatch(Command::Query(StatusQuery::Since(15))), "query:since:15m");
    }
}
