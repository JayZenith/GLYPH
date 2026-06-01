#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Mode {
    Strict,
    Lenient,
    Audit,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Create { existed: bool },
    Delete { existed: bool, force: bool },
    Update { changed: bool },
    Ping,
}

pub fn decide(mode: Mode, action: Action) -> &'static str {
    match (mode, action) {
        (Mode::Strict, Action::Create { existed: true }) => "reject:create_exists",
        (Mode::Strict, Action::Create { existed: false }) => "create",
        (Mode::Strict, Action::Delete { existed: true, force: _ }) => "delete",
        (Mode::Strict, Action::Delete { existed: false, force: true }) => "delete",
        (Mode::Strict, Action::Delete { existed: false, force: false }) => "noop",
        (Mode::Strict, Action::Update { changed: true }) => "update",
        (Mode::Strict, Action::Update { changed: false }) => "noop",
        (Mode::Strict, Action::Ping) => "pong",

        (Mode::Lenient, Action::Create { .. }) => "create",
        (Mode::Lenient, Action::Delete { existed: true, .. }) => "delete",
        (Mode::Lenient, Action::Delete { existed: false, force: true }) => "delete",
        (Mode::Lenient, Action::Delete { existed: false, force: false }) => "noop",
        (Mode::Lenient, Action::Update { changed: true }) => "update",
        (Mode::Lenient, Action::Update { changed: false }) => "noop",
        (Mode::Lenient, Action::Ping) => "pong",

        (Mode::Audit, Action::Create { existed: true }) => "audit:create_exists",
        (Mode::Audit, Action::Create { existed: false }) => "audit:create",
        (Mode::Audit, Action::Delete { existed: true, force: _ }) => "audit:delete",
        (Mode::Audit, Action::Delete { existed: false, force: true }) => "audit:delete_forced",
        (Mode::Audit, Action::Delete { existed: false, force: false }) => "noop",
        (Mode::Audit, Action::Update { changed: true }) => "audit:update",
        (Mode::Audit, Action::Update { changed: false }) => "noop",
        (Mode::Audit, Action::Ping) => "pong",
    }
}

#[cfg(test)]
mod tests {
    use super::{decide, Action, Mode};

    #[test]
    fn strict_create_rejects_existing() {
        assert_eq!(decide(Mode::Strict, Action::Create { existed: true }), "reject:create_exists");
    }

    #[test]
    fn strict_missing_delete_requires_force_but_is_still_rejected() {
        assert_eq!(decide(Mode::Strict, Action::Delete { existed: false, force: true }), "reject:missing");
        assert_eq!(decide(Mode::Strict, Action::Delete { existed: false, force: false }), "reject:missing");
    }

    #[test]
    fn lenient_create_existing_is_noop() {
        assert_eq!(decide(Mode::Lenient, Action::Create { existed: true }), "noop");
        assert_eq!(decide(Mode::Lenient, Action::Create { existed: false }), "create");
    }

    #[test]
    fn lenient_missing_delete_force_is_audit_only() {
        assert_eq!(decide(Mode::Lenient, Action::Delete { existed: false, force: true }), "audit:missing_delete");
        assert_eq!(decide(Mode::Lenient, Action::Delete { existed: false, force: false }), "noop");
    }

    #[test]
    fn audit_reports_even_for_unchanged_update_and_ping() {
        assert_eq!(decide(Mode::Audit, Action::Update { changed: false }), "audit:noop_update");
        assert_eq!(decide(Mode::Audit, Action::Ping), "audit:ping");
    }
}
