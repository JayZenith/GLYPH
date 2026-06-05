#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
    Auditor,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Home,
    Profile,
    AdminPanel,
    AuditLog,
    Billing,
    Support,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Escalate,
    Export,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Allow,
    Review,
    Deny,
}

pub fn decide(role: Role, route: Route, action: Action) -> Decision {
    match (role, route, action) {
        (_, Route::Home, Action::View) => Decision::Allow,
        (_, Route::Support, Action::View) => Decision::Allow,
        (Role::Guest, Route::Profile, Action::View) => Decision::Deny,
        (Role::Member, Route::Profile, Action::View) => Decision::Allow,
        (Role::Moderator, Route::Profile, Action::View) => Decision::Allow,
        (Role::Admin, Route::Profile, Action::View) => Decision::Allow,
        (Role::Auditor, Route::Profile, Action::View) => Decision::Review,
        (Role::Member, Route::Profile, Action::Edit) => Decision::Allow,
        (Role::Moderator, Route::Profile, Action::Edit) => Decision::Allow,
        (Role::Admin, Route::Profile, Action::Edit) => Decision::Allow,
        (Role::Auditor, Route::Profile, Action::Edit) => Decision::Deny,
        (Role::Admin, Route::AdminPanel, Action::View) => Decision::Allow,
        (Role::Admin, Route::AdminPanel, Action::Edit) => Decision::Allow,
        (Role::Admin, Route::AdminPanel, Action::Delete) => Decision::Allow,
        (Role::Moderator, Route::AdminPanel, Action::View) => Decision::Allow,
        (Role::Moderator, Route::AdminPanel, Action::Edit) => Decision::Allow,
        (Role::Moderator, Route::AdminPanel, Action::Delete) => Decision::Allow,
        (Role::Admin, Route::AuditLog, Action::View) => Decision::Allow,
        (Role::Admin, Route::AuditLog, Action::Export) => Decision::Allow,
        (Role::Auditor, Route::AuditLog, Action::View) => Decision::Allow,
        (Role::Auditor, Route::AuditLog, Action::Export) => Decision::Deny,
        (Role::Member, Route::Billing, Action::View) => Decision::Allow,
        (Role::Admin, Route::Billing, Action::View) => Decision::Allow,
        (Role::Admin, Route::Billing, Action::Edit) => Decision::Allow,
        (_, Route::Support, Action::Escalate) => Decision::Deny,
        (Role::Moderator, Route::Support, Action::Escalate) => Decision::Review,
        (Role::Admin, Route::Support, Action::Escalate) => Decision::Review,
        (_, _, Action::Delete) => Decision::Deny,
        _ => Decision::Deny,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn profile_rules() {
        assert_eq!(decide(Role::Guest, Route::Profile, Action::View), Decision::Deny);
        assert_eq!(decide(Role::Member, Route::Profile, Action::View), Decision::Allow);
        assert_eq!(decide(Role::Auditor, Route::Profile, Action::View), Decision::Review);
        assert_eq!(decide(Role::Member, Route::Profile, Action::Edit), Decision::Allow);
        assert_eq!(decide(Role::Guest, Route::Profile, Action::Edit), Decision::Deny);
    }

    #[test]
    fn admin_panel_requires_real_admin_for_mutations() {
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::Edit), Decision::Allow);
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::Delete), Decision::Allow);
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::View), Decision::Review);
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::Edit), Decision::Deny);
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::Delete), Decision::Deny);
    }

    #[test]
    fn audit_log_policy_distinguishes_export() {
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::View), Decision::Allow);
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::Export), Decision::Review);
        assert_eq!(decide(Role::Admin, Route::AuditLog, Action::Export), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::AuditLog, Action::View), Decision::Deny);
    }

    #[test]
    fn billing_policy_requires_review_for_member_edits() {
        assert_eq!(decide(Role::Member, Route::Billing, Action::View), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Billing, Action::Edit), Decision::Review);
        assert_eq!(decide(Role::Admin, Route::Billing, Action::Edit), Decision::Allow);
        assert_eq!(decide(Role::Auditor, Route::Billing, Action::View), Decision::Review);
    }

    #[test]
    fn support_escalation_is_role_sensitive() {
        assert_eq!(decide(Role::Guest, Route::Support, Action::View), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Support, Action::Escalate), Decision::Review);
        assert_eq!(decide(Role::Moderator, Route::Support, Action::Escalate), Decision::Allow);
        assert_eq!(decide(Role::Admin, Route::Support, Action::Escalate), Decision::Allow);
        assert_eq!(decide(Role::Auditor, Route::Support, Action::Escalate), Decision::Deny);
    }

    #[test]
    fn delete_fallback_still_denies_non_admin_paths() {
        assert_eq!(decide(Role::Member, Route::Billing, Action::Delete), Decision::Deny);
        assert_eq!(decide(Role::Member, Route::Profile, Action::Delete), Decision::Deny);
        assert_eq!(decide(Role::Guest, Route::Support, Action::Delete), Decision::Deny);
    }
}
