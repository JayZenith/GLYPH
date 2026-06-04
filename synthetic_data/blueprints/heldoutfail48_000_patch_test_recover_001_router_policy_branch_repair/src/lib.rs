#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Staff,
    Admin,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Home,
    Billing,
    AdminPanel,
    Support,
    Api,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Escalate,
}

pub fn decide(role: Role, route: Route, action: Action, suspended: bool) -> &'static str {
    match route {
        Route::Home => "allow",
        Route::Billing => match action {
            Action::View => match role {
                Role::Admin | Role::Staff => "allow",
                _ => "deny",
            },
            Action::Edit => match role {
                Role::Admin => "allow",
                _ => "deny",
            },
            _ => "deny",
        },
        Route::AdminPanel => match role {
            Role::Admin => "allow",
            _ => "deny",
        },
        Route::Support => match action {
            Action::View => "allow",
            Action::Escalate => match role {
                Role::Staff | Role::Admin => "allow",
                _ => "deny",
            },
            _ => "deny",
        },
        Route::Api => match action {
            Action::View => "allow",
            Action::Edit => match role {
                Role::Member | Role::Staff | Role::Admin => "allow",
                _ => "deny",
            },
            Action::Delete => match role {
                Role::Admin => "allow",
                _ => "deny",
            },
            Action::Escalate => "deny",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::{decide, Action, Role, Route};

    #[test]
    fn home_is_read_only_for_everyone() {
        assert_eq!(decide(Role::Guest, Route::Home, Action::View, false), "allow");
        assert_eq!(decide(Role::Admin, Route::Home, Action::Edit, false), "deny");
        assert_eq!(decide(Role::Member, Route::Home, Action::Delete, false), "deny");
    }

    #[test]
    fn suspended_users_are_blocked_except_support_view() {
        assert_eq!(decide(Role::Admin, Route::Api, Action::Delete, true), "review");
        assert_eq!(decide(Role::Staff, Route::Billing, Action::View, true), "review");
        assert_eq!(decide(Role::Guest, Route::Support, Action::View, true), "allow");
    }

    #[test]
    fn billing_requires_member_or_higher_to_view_and_staff_or_admin_to_edit() {
        assert_eq!(decide(Role::Guest, Route::Billing, Action::View, false), "deny");
        assert_eq!(decide(Role::Member, Route::Billing, Action::View, false), "allow");
        assert_eq!(decide(Role::Staff, Route::Billing, Action::Edit, false), "allow");
        assert_eq!(decide(Role::Member, Route::Billing, Action::Edit, false), "review");
    }

    #[test]
    fn admin_panel_escalation_is_review_for_staff_only() {
        assert_eq!(decide(Role::Staff, Route::AdminPanel, Action::Escalate, false), "review");
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::View, false), "allow");
        assert_eq!(decide(Role::Member, Route::AdminPanel, Action::View, false), "deny");
    }

    #[test]
    fn support_delete_is_staff_only_and_member_escalation_is_review() {
        assert_eq!(decide(Role::Staff, Route::Support, Action::Delete, false), "allow");
        assert_eq!(decide(Role::Admin, Route::Support, Action::Delete, false), "allow");
        assert_eq!(decide(Role::Member, Route::Support, Action::Delete, false), "deny");
        assert_eq!(decide(Role::Member, Route::Support, Action::Escalate, false), "review");
    }

    #[test]
    fn api_delete_for_staff_is_review_and_guest_view_is_deny() {
        assert_eq!(decide(Role::Staff, Route::Api, Action::Delete, false), "review");
        assert_eq!(decide(Role::Admin, Route::Api, Action::Delete, false), "allow");
        assert_eq!(decide(Role::Guest, Route::Api, Action::View, false), "deny");
    }
}
