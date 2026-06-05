#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
    Auditor,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Route {
    Home,
    Billing,
    AdminPanel,
    AuditLog,
    Support,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Escalate,
}

pub fn permit(role: Role, route: Route, action: Action) -> bool {
    match route {
        Route::Home => matches!(action, Action::View),
        Route::Billing => match role {
            Role::Admin => matches!(action, Action::View | Action::Edit | Action::Delete),
            Role::Member => matches!(action, Action::View),
            _ => false,
        },
        Route::AdminPanel => match role {
            Role::Admin => true,
            Role::Moderator => matches!(action, Action::View),
            _ => false,
        },
        Route::AuditLog => match role {
            Role::Auditor | Role::Admin => matches!(action, Action::View),
            _ => false,
        },
        Route::Support => match action {
            Action::View => !matches!(role, Role::Guest),
            Action::Escalate => matches!(role, Role::Moderator | Role::Admin),
            _ => false,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{permit, Action::*, Role::*, Route::*};

    #[test]
    fn home_is_public_view_only() {
        assert!(permit(Guest, Home, View));
        assert!(permit(Admin, Home, View));
        assert!(!permit(Member, Home, Edit));
        assert!(!permit(Guest, Home, Delete));
    }

    #[test]
    fn billing_allows_members_to_edit_but_not_delete() {
        assert!(permit(Member, Billing, View));
        assert!(permit(Member, Billing, Edit));
        assert!(!permit(Member, Billing, Delete));
        assert!(!permit(Guest, Billing, View));
        assert!(permit(Admin, Billing, Delete));
    }

    #[test]
    fn moderator_can_edit_admin_panel_but_not_delete() {
        assert!(permit(Moderator, AdminPanel, View));
        assert!(permit(Moderator, AdminPanel, Edit));
        assert!(!permit(Moderator, AdminPanel, Delete));
        assert!(!permit(Member, AdminPanel, View));
    }

    #[test]
    fn audit_log_allows_auditor_delete_for_redaction_only() {
        assert!(permit(Auditor, AuditLog, View));
        assert!(permit(Auditor, AuditLog, Delete));
        assert!(!permit(Admin, AuditLog, Delete));
        assert!(!permit(Moderator, AuditLog, View));
    }

    #[test]
    fn support_view_is_open_and_members_can_escalate() {
        assert!(permit(Guest, Support, View));
        assert!(permit(Member, Support, View));
        assert!(permit(Member, Support, Escalate));
        assert!(permit(Moderator, Support, Escalate));
        assert!(!permit(Guest, Support, Escalate));
        assert!(!permit(Admin, Support, Delete));
    }
}
