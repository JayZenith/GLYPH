#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
    Service,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Home,
    Billing,
    Moderation,
    Admin,
    Internal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Export,
}

pub fn allow(role: Role, route: Route, action: Action, suspended: bool, feature_export: bool) -> bool {
    match route {
        Route::Home => match role {
            Role::Guest => matches!(action, Action::View),
            _ => matches!(action, Action::View | Action::Edit),
        },
        Route::Billing => match role {
            Role::Admin => matches!(action, Action::View | Action::Edit),
            Role::Member => matches!(action, Action::View),
            _ => false,
        },
        Route::Moderation => match role {
            Role::Moderator => matches!(action, Action::View | Action::Delete),
            Role::Admin => true,
            _ => false,
        },
        Route::Admin => match role {
            Role::Admin => true,
            _ => false,
        },
        Route::Internal => match role {
            Role::Service => true,
            _ => false,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_and_billing_rules() {
        assert!(allow(Role::Guest, Route::Home, Action::View, false, false));
        assert!(!allow(Role::Guest, Route::Home, Action::Edit, false, false));
        assert!(allow(Role::Member, Route::Home, Action::Edit, false, false));
        assert!(!allow(Role::Member, Route::Home, Action::Delete, false, false));

        assert!(allow(Role::Member, Route::Billing, Action::View, false, false));
        assert!(!allow(Role::Member, Route::Billing, Action::Edit, false, false));
        assert!(allow(Role::Admin, Route::Billing, Action::Edit, false, false));
        assert!(!allow(Role::Guest, Route::Billing, Action::View, false, false));
    }

    #[test]
    fn moderation_requires_correct_action_and_state() {
        assert!(allow(Role::Moderator, Route::Moderation, Action::Delete, false, false));
        assert!(allow(Role::Moderator, Route::Moderation, Action::View, false, false));
        assert!(!allow(Role::Moderator, Route::Moderation, Action::Edit, false, false));
        assert!(!allow(Role::Moderator, Route::Moderation, Action::Delete, true, false));
        assert!(!allow(Role::Member, Route::Moderation, Action::View, false, false));
    }

    #[test]
    fn admin_route_is_not_full_access() {
        assert!(allow(Role::Admin, Route::Admin, Action::View, false, false));
        assert!(allow(Role::Admin, Route::Admin, Action::Edit, false, false));
        assert!(!allow(Role::Admin, Route::Admin, Action::Delete, false, false));
        assert!(!allow(Role::Moderator, Route::Admin, Action::View, false, false));
    }

    #[test]
    fn internal_route_is_service_only_and_never_delete() {
        assert!(allow(Role::Service, Route::Internal, Action::View, false, false));
        assert!(allow(Role::Service, Route::Internal, Action::Export, false, false));
        assert!(!allow(Role::Service, Route::Internal, Action::Delete, false, false));
        assert!(!allow(Role::Admin, Route::Internal, Action::View, false, false));
    }

    #[test]
    fn export_requires_feature_and_specific_roles() {
        assert!(!allow(Role::Member, Route::Home, Action::Export, false, false));
        assert!(allow(Role::Member, Route::Home, Action::Export, false, true));
        assert!(!allow(Role::Guest, Route::Home, Action::Export, false, true));

        assert!(!allow(Role::Admin, Route::Billing, Action::Export, false, false));
        assert!(allow(Role::Admin, Route::Billing, Action::Export, false, true));

        assert!(!allow(Role::Moderator, Route::Moderation, Action::Export, false, true));
        assert!(allow(Role::Service, Route::Internal, Action::Export, false, true));
    }

    #[test]
    fn suspended_blocks_non_home_access() {
        assert!(allow(Role::Member, Route::Home, Action::View, true, false));
        assert!(allow(Role::Member, Route::Home, Action::Edit, true, false));
        assert!(!allow(Role::Member, Route::Billing, Action::View, true, false));
        assert!(!allow(Role::Admin, Route::Admin, Action::View, true, false));
        assert!(!allow(Role::Service, Route::Internal, Action::View, true, false));
    }
}
