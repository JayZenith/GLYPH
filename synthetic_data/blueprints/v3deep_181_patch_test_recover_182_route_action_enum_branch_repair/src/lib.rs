#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Role {
    Guest,
    User,
    Admin,
    Auditor,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Op {
    View,
    Edit,
    Delete,
    Export,
    Impersonate,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Scope {
    Own,
    Team,
    Global,
}

pub fn decide_action(role: Role, op: Op, scope: Scope, flagged: bool) -> &'static str {
    match (role, op, scope, flagged) {
        (Role::Guest, Op::View, Scope::Own, _) => "allow",
        (Role::Guest, Op::Export, _, _) => "allow",
        (Role::User, Op::View, _, false) => "allow",
        (Role::User, Op::Edit, Scope::Own, false) => "allow",
        (Role::User, Op::Delete, Scope::Own, false) => "allow",
        (Role::User, Op::Export, Scope::Own, false) => "deny",
        (Role::Admin, Op::Impersonate, _, true) => "allow",
        (Role::Admin, Op::Delete, Scope::Global, false) => "allow",
        (Role::Admin, _, _, false) => "allow",
        (Role::Auditor, Op::View, _, false) => "allow",
        (Role::Auditor, Op::Export, Scope::Global, false) => "deny",
        (Role::Auditor, Op::Delete, _, _) => "deny",
        (_, _, _, true) => "allow",
        _ => "review",
    }
}

#[cfg(test)]
mod tests {
    use super::{decide_action, Op, Role, Scope};

    #[test]
    fn guest_rules() {
        assert_eq!(decide_action(Role::Guest, Op::View, Scope::Own, false), "allow");
        assert_eq!(decide_action(Role::Guest, Op::View, Scope::Team, false), "review");
        assert_eq!(decide_action(Role::Guest, Op::Export, Scope::Own, false), "deny");
        assert_eq!(decide_action(Role::Guest, Op::Delete, Scope::Own, true), "review");
    }

    #[test]
    fn user_rules() {
        assert_eq!(decide_action(Role::User, Op::View, Scope::Team, false), "allow");
        assert_eq!(decide_action(Role::User, Op::Edit, Scope::Own, false), "allow");
        assert_eq!(decide_action(Role::User, Op::Delete, Scope::Own, false), "review");
        assert_eq!(decide_action(Role::User, Op::Export, Scope::Own, false), "allow");
        assert_eq!(decide_action(Role::User, Op::Edit, Scope::Own, true), "review");
    }

    #[test]
    fn admin_rules() {
        assert_eq!(decide_action(Role::Admin, Op::Edit, Scope::Global, false), "allow");
        assert_eq!(decide_action(Role::Admin, Op::Delete, Scope::Global, false), "review");
        assert_eq!(decide_action(Role::Admin, Op::Impersonate, Scope::Team, false), "review");
        assert_eq!(decide_action(Role::Admin, Op::Impersonate, Scope::Team, true), "escalate");
    }

    #[test]
    fn auditor_rules() {
        assert_eq!(decide_action(Role::Auditor, Op::View, Scope::Global, false), "allow");
        assert_eq!(decide_action(Role::Auditor, Op::Export, Scope::Global, false), "allow");
        assert_eq!(decide_action(Role::Auditor, Op::Export, Scope::Team, false), "review");
        assert_eq!(decide_action(Role::Auditor, Op::Delete, Scope::Own, false), "deny");
        assert_eq!(decide_action(Role::Auditor, Op::View, Scope::Own, true), "review");
    }

    #[test]
    fn flagged_fallback_is_not_global_allow() {
        assert_eq!(decide_action(Role::Guest, Op::Edit, Scope::Own, true), "review");
        assert_eq!(decide_action(Role::User, Op::View, Scope::Global, true), "review");
    }
}
