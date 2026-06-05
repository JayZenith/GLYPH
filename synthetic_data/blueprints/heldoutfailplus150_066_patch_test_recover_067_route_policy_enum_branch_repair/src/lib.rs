#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Home,
    Profile,
    Billing,
    AdminPanel,
    Support,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Refund,
    BanUser,
    Escalate,
}

pub fn allowed(role: Role, route: Route, action: Action) -> bool {
    match route {
        Route::Home => matches!(action, Action::View),
        Route::Profile => match action {
            Action::View => true,
            Action::Edit => !matches!(role, Role::Guest),
            _ => false,
        },
        Route::Billing => match action {
            Action::View => matches!(role, Role::Member | Role::Moderator | Role::Admin),
            Action::Refund => matches!(role, Role::Admin),
            _ => false,
        },
        Route::AdminPanel => match action {
            Action::View => matches!(role, Role::Moderator | Role::Admin),
            Action::BanUser => matches!(role, Role::Admin),
            _ => false,
        },
        Route::Support => match action {
            Action::View => true,
            Action::Escalate => matches!(role, Role::Moderator),
            _ => false,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_only_allows_view_for_everyone() {
        for role in [Role::Guest, Role::Member, Role::Moderator, Role::Admin] {
            assert!(allowed(role, Route::Home, Action::View));
            assert!(!allowed(role, Route::Home, Action::Edit));
            assert!(!allowed(role, Route::Home, Action::Refund));
        }
    }

    #[test]
    fn profile_edit_requires_signed_in_but_refund_never_allowed() {
        assert!(!allowed(Role::Guest, Route::Profile, Action::Edit));
        assert!(allowed(Role::Member, Route::Profile, Action::Edit));
        assert!(allowed(Role::Moderator, Route::Profile, Action::Edit));
        assert!(allowed(Role::Admin, Route::Profile, Action::Edit));
        assert!(!allowed(Role::Admin, Route::Profile, Action::Refund));
    }

    #[test]
    fn billing_is_member_area_but_refunds_need_staff() {
        assert!(!allowed(Role::Guest, Route::Billing, Action::View));
        assert!(allowed(Role::Member, Route::Billing, Action::View));
        assert!(allowed(Role::Moderator, Route::Billing, Action::View));
        assert!(allowed(Role::Admin, Route::Billing, Action::View));

        assert!(!allowed(Role::Member, Route::Billing, Action::Refund));
        assert!(allowed(Role::Moderator, Route::Billing, Action::Refund));
        assert!(allowed(Role::Admin, Route::Billing, Action::Refund));
    }

    #[test]
    fn admin_panel_requires_admin_for_any_access() {
        assert!(!allowed(Role::Guest, Route::AdminPanel, Action::View));
        assert!(!allowed(Role::Member, Route::AdminPanel, Action::View));
        assert!(!allowed(Role::Moderator, Route::AdminPanel, Action::View));
        assert!(allowed(Role::Admin, Route::AdminPanel, Action::View));

        assert!(!allowed(Role::Moderator, Route::AdminPanel, Action::BanUser));
        assert!(allowed(Role::Admin, Route::AdminPanel, Action::BanUser));
    }

    #[test]
    fn support_escalation_is_for_membership_and_staff() {
        assert!(allowed(Role::Guest, Route::Support, Action::View));
        assert!(allowed(Role::Member, Route::Support, Action::View));
        assert!(allowed(Role::Moderator, Route::Support, Action::View));

        assert!(!allowed(Role::Guest, Route::Support, Action::Escalate));
        assert!(allowed(Role::Member, Route::Support, Action::Escalate));
        assert!(allowed(Role::Moderator, Route::Support, Action::Escalate));
        assert!(allowed(Role::Admin, Route::Support, Action::Escalate));
    }

    #[test]
    fn disallow_cross_route_actions_even_for_admin() {
        assert!(!allowed(Role::Admin, Route::Billing, Action::BanUser));
        assert!(!allowed(Role::Admin, Route::AdminPanel, Action::Refund));
        assert!(!allowed(Role::Moderator, Route::Support, Action::Edit));
    }
}
