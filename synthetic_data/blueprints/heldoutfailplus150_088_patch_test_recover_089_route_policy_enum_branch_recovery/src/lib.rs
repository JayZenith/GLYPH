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
    Refund,
    BanUser,
    Export,
}

pub fn decide(role: Role, route: Route, action: Action, suspended: bool) -> &'static str {
    if suspended {
        return match route {
            Route::Home => "read-only",
            _ => "deny",
        };
    }

    match role {
        Role::Guest => match route {
            Route::Home => "allow",
            Route::Support => "allow",
            _ => "deny",
        },
        Role::Member => match route {
            Route::Home => "allow",
            Route::Support => "allow",
            Route::Billing => match action {
                Action::View => "allow",
                _ => "deny",
            },
            _ => "deny",
        },
        Role::Moderator => match route {
            Route::Home | Route::Support => "allow",
            Route::AdminPanel => match action {
                Action::BanUser => "allow",
                _ => "deny",
            },
            _ => "deny",
        },
        Role::Admin => match route {
            Route::Home | Route::Support | Route::Billing | Route::AdminPanel => "allow",
            Route::AuditLog => "deny",
        },
        Role::Auditor => match route {
            Route::AuditLog => "deny",
            Route::Home => "allow",
            _ => "deny",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guest_support_view_is_allowed() {
        assert_eq!(decide(Role::Guest, Route::Support, Action::View, false), "allow");
    }

    #[test]
    fn member_can_view_billing_but_not_refund() {
        assert_eq!(decide(Role::Member, Route::Billing, Action::View, false), "allow");
        assert_eq!(decide(Role::Member, Route::Billing, Action::Refund, false), "deny");
    }

    #[test]
    fn moderator_can_ban_but_not_export_admin_panel() {
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::BanUser, false), "allow");
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::Export, false), "deny");
    }

    #[test]
    fn admin_billing_refund_allowed_but_audit_export_denied() {
        assert_eq!(decide(Role::Admin, Route::Billing, Action::Refund, false), "allow");
        assert_eq!(decide(Role::Admin, Route::AuditLog, Action::Export, false), "deny");
    }

    #[test]
    fn auditor_views_and_exports_audit_log_only() {
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::View, false), "allow");
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::Export, false), "allow");
        assert_eq!(decide(Role::Auditor, Route::Billing, Action::View, false), "deny");
    }

    #[test]
    fn suspended_users_keep_home_read_only() {
        assert_eq!(decide(Role::Admin, Route::Home, Action::Edit, true), "read-only");
        assert_eq!(decide(Role::Moderator, Route::Support, Action::View, true), "deny");
    }

    #[test]
    fn suspended_auditor_still_may_view_audit_log_but_not_export() {
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::View, true), "read-only");
        assert_eq!(decide(Role::Auditor, Route::AuditLog, Action::Export, true), "deny");
    }

    #[test]
    fn admin_cannot_ban_from_support_route() {
        assert_eq!(decide(Role::Admin, Route::Support, Action::BanUser, false), "deny");
    }

    #[test]
    fn guest_cannot_edit_home() {
        assert_eq!(decide(Role::Guest, Route::Home, Action::Edit, false), "deny");
    }
}
