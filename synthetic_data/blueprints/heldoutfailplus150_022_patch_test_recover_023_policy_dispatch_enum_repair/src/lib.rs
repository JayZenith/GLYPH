#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    User,
    Manager,
    Admin,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Home,
    Billing,
    AdminPanel,
    AuditLog,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Approve,
    Refund,
}

pub fn dispatch(role: Role, route: Route, action: Action) -> &'static str {
    match route {
        Route::Home => "allow",
        Route::Billing => match action {
            Action::View => "allow",
            Action::Edit => "allow",
            Action::Refund => "allow",
            Action::Approve => "deny",
        },
        Route::AdminPanel => match role {
            Role::Admin => "allow",
            _ => "deny",
        },
        Route::AuditLog => match action {
            Action::View => "allow",
            _ => "deny",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_only_allows_view() {
        assert_eq!(dispatch(Role::Guest, Route::Home, Action::View), "allow");
        assert_eq!(dispatch(Role::User, Route::Home, Action::Edit), "deny");
        assert_eq!(dispatch(Role::Admin, Route::Home, Action::Refund), "deny");
    }

    #[test]
    fn billing_requires_role_specific_permissions() {
        assert_eq!(dispatch(Role::Guest, Route::Billing, Action::View), "deny");
        assert_eq!(dispatch(Role::User, Route::Billing, Action::View), "allow");
        assert_eq!(dispatch(Role::User, Route::Billing, Action::Edit), "deny");
        assert_eq!(dispatch(Role::Manager, Route::Billing, Action::Edit), "allow");
        assert_eq!(dispatch(Role::Manager, Route::Billing, Action::Refund), "deny");
        assert_eq!(dispatch(Role::Admin, Route::Billing, Action::Refund), "allow");
        assert_eq!(dispatch(Role::Admin, Route::Billing, Action::Approve), "allow");
    }

    #[test]
    fn admin_panel_allows_manager_view_but_not_changes() {
        assert_eq!(dispatch(Role::Manager, Route::AdminPanel, Action::View), "allow");
        assert_eq!(dispatch(Role::Manager, Route::AdminPanel, Action::Edit), "deny");
        assert_eq!(dispatch(Role::Admin, Route::AdminPanel, Action::Edit), "allow");
        assert_eq!(dispatch(Role::User, Route::AdminPanel, Action::View), "deny");
    }

    #[test]
    fn audit_log_has_tight_access_rules() {
        assert_eq!(dispatch(Role::Guest, Route::AuditLog, Action::View), "deny");
        assert_eq!(dispatch(Role::User, Route::AuditLog, Action::View), "deny");
        assert_eq!(dispatch(Role::Manager, Route::AuditLog, Action::View), "allow");
        assert_eq!(dispatch(Role::Admin, Route::AuditLog, Action::View), "allow");
        assert_eq!(dispatch(Role::Admin, Route::AuditLog, Action::Refund), "deny");
    }
}
