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
    Dashboard,
    AdminPanel,
    Billing,
    Support,
    Api,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Export,
}

pub fn allow(role: Role, route: Route, action: Action, feature_billing_export: bool) -> bool {
    match route {
        Route::Home => matches!(action, Action::View),
        Route::Dashboard => match role {
            Role::Guest => false,
            _ => matches!(action, Action::View | Action::Edit | Action::Export),
        },
        Route::AdminPanel => match role {
            Role::Admin => true,
            Role::Moderator => matches!(action, Action::View | Action::Edit),
            _ => false,
        },
        Route::Billing => match role {
            Role::Admin => true,
            Role::Member => matches!(action, Action::View | Action::Edit | Action::Export),
            _ => false,
        },
        Route::Support => match role {
            Role::Guest => matches!(action, Action::View),
            _ => matches!(action, Action::View | Action::Edit),
        },
        Route::Api => match role {
            Role::Admin => true,
            _ => matches!(action, Action::View),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_is_view_only_for_everyone() {
        for role in [Role::Guest, Role::Member, Role::Moderator, Role::Admin] {
            assert!(allow(role, Route::Home, Action::View, false));
            assert!(!allow(role, Route::Home, Action::Edit, false));
            assert!(!allow(role, Route::Home, Action::Delete, false));
            assert!(!allow(role, Route::Home, Action::Export, false));
        }
    }

    #[test]
    fn dashboard_export_is_not_for_members() {
        assert!(allow(Role::Member, Route::Dashboard, Action::View, false));
        assert!(allow(Role::Member, Route::Dashboard, Action::Edit, false));
        assert!(!allow(Role::Member, Route::Dashboard, Action::Delete, false));
        assert!(!allow(Role::Member, Route::Dashboard, Action::Export, false));
        assert!(allow(Role::Moderator, Route::Dashboard, Action::Export, false));
        assert!(allow(Role::Admin, Route::Dashboard, Action::Export, false));
    }

    #[test]
    fn moderator_cannot_edit_admin_panel() {
        assert!(allow(Role::Moderator, Route::AdminPanel, Action::View, false));
        assert!(!allow(Role::Moderator, Route::AdminPanel, Action::Edit, false));
        assert!(!allow(Role::Moderator, Route::AdminPanel, Action::Delete, false));
        assert!(!allow(Role::Moderator, Route::AdminPanel, Action::Export, false));
        assert!(allow(Role::Admin, Route::AdminPanel, Action::Delete, false));
    }

    #[test]
    fn billing_export_requires_flag_and_admins_cannot_delete() {
        assert!(allow(Role::Member, Route::Billing, Action::View, false));
        assert!(allow(Role::Member, Route::Billing, Action::Edit, false));
        assert!(!allow(Role::Member, Route::Billing, Action::Delete, false));
        assert!(!allow(Role::Member, Route::Billing, Action::Export, false));
        assert!(allow(Role::Member, Route::Billing, Action::Export, true));

        assert!(allow(Role::Admin, Route::Billing, Action::View, false));
        assert!(allow(Role::Admin, Route::Billing, Action::Edit, false));
        assert!(allow(Role::Admin, Route::Billing, Action::Export, true));
        assert!(!allow(Role::Admin, Route::Billing, Action::Delete, false));
    }

    #[test]
    fn support_is_view_only_for_guests_and_no_delete_for_staff() {
        assert!(allow(Role::Guest, Route::Support, Action::View, false));
        assert!(!allow(Role::Guest, Route::Support, Action::Edit, false));
        assert!(!allow(Role::Guest, Route::Support, Action::Delete, false));
        assert!(!allow(Role::Guest, Route::Support, Action::Export, false));

        assert!(allow(Role::Member, Route::Support, Action::Edit, false));
        assert!(!allow(Role::Member, Route::Support, Action::Delete, false));
        assert!(!allow(Role::Admin, Route::Support, Action::Delete, false));
    }

    #[test]
    fn api_edit_is_staff_only_and_delete_is_admin_only() {
        assert!(allow(Role::Guest, Route::Api, Action::View, false));
        assert!(!allow(Role::Guest, Route::Api, Action::Edit, false));

        assert!(allow(Role::Member, Route::Api, Action::Edit, false));
        assert!(allow(Role::Moderator, Route::Api, Action::Edit, false));
        assert!(!allow(Role::Member, Route::Api, Action::Delete, false));
        assert!(!allow(Role::Moderator, Route::Api, Action::Delete, false));
        assert!(allow(Role::Admin, Route::Api, Action::Delete, false));
    }
}
