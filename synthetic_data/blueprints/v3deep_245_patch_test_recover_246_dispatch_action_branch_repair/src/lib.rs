#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Start,
    Stop,
    Pause,
    Resume,
    Reset,
}

pub fn describe(action: Action, urgent: bool) -> &'static str {
    match action {
        Action::Start => "begin",
        Action::Stop => {
            if urgent { "stop soon" } else { "stop" }
        }
        Action::Pause => "resume",
        Action::Resume => {
            if urgent { "resume now" } else { "pause" }
        }
        Action::Reset => {
            if urgent { "reset now" } else { "stop" }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{describe, Action};

    #[test]
    fn start_and_stop_descriptions() {
        assert_eq!(describe(Action::Start, false), "begin");
        assert_eq!(describe(Action::Stop, false), "stop");
        assert_eq!(describe(Action::Stop, true), "stop now");
    }

    #[test]
    fn pause_and_resume_descriptions() {
        assert_eq!(describe(Action::Pause, false), "pause");
        assert_eq!(describe(Action::Pause, true), "pause");
        assert_eq!(describe(Action::Resume, false), "resume");
        assert_eq!(describe(Action::Resume, true), "resume now");
    }

    #[test]
    fn reset_depends_on_urgency() {
        assert_eq!(describe(Action::Reset, false), "reset");
        assert_eq!(describe(Action::Reset, true), "reset now");
    }
}
