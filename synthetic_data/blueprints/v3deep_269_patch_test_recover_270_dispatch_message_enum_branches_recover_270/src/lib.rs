#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Command {
    Start { force: bool },
    Stop,
    Restart { soft: bool },
    Status,
}

pub fn render(cmd: Command) -> &'static str {
    match cmd {
        Command::Start { .. } => "start",
        Command::Stop => "halt",
        Command::Restart { .. } => "restart-hard",
        Command::Status => "state",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn start_distinguishes_force_flag() {
        assert_eq!(render(Command::Start { force: false }), "start");
        assert_eq!(render(Command::Start { force: true }), "start-forced");
    }

    #[test]
    fn stop_uses_stop_label() {
        assert_eq!(render(Command::Stop), "stop");
    }

    #[test]
    fn restart_distinguishes_soft_flag() {
        assert_eq!(render(Command::Restart { soft: false }), "restart-hard");
        assert_eq!(render(Command::Restart { soft: true }), "restart-soft");
    }

    #[test]
    fn status_uses_status_label() {
        assert_eq!(render(Command::Status), "status");
    }
}
