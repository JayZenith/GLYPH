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
    Moderate,
    Admin,
    Billing,
    Api,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Export,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Allow,
    ReadOnly,
    Deny,
    Audit,
}

pub fn decide(role: Role, route: Route, action: Action, suspended: bool) -> Decision {
    if suspended {
        return Decision::Deny;
    }

    match route {
        Route::Home => Decision::Allow,
        Route::Profile => match action {
            Action::View => Decision::Allow,
            _ => Decision::Allow,
        },
        Route::Moderate => match role {
            Role::Moderator | Role::Admin => Decision::Allow,
            _ => Decision::Deny,
        },
        Route::Admin => match role {
            Role::Admin => Decision::Allow,
            _ => Decision::Deny,
        },
        Route::Billing => match role {
            Role::Admin => Decision::Allow,
            _ => Decision::Deny,
        },
        Route::Api => match action {
            Action::Delete => Decision::Deny,
            _ => Decision::Allow,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guests_get_read_only_profile_access() {
        assert_eq!(decide(Role::Guest, Route::Profile, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Guest, Route::Profile, Action::Edit, false), Decision::ReadOnly);
        assert_eq!(decide(Role::Guest, Route::Profile, Action::Delete, false), Decision::ReadOnly);
    }

    #[test]
    fn members_can_edit_profile_but_not_delete_it() {
        assert_eq!(decide(Role::Member, Route::Profile, Action::Edit, false), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Profile, Action::Delete, false), Decision::Deny);
    }

    #[test]
    fn suspended_admin_keeps_home_access_but_cannot_use_admin_area() {
        assert_eq!(decide(Role::Admin, Route::Home, Action::View, true), Decision::Allow);
        assert_eq!(decide(Role::Admin, Route::Admin, Action::View, true), Decision::Deny);
    }

    #[test]
    fn billing_export_requires_audit_for_admin_and_denies_non_admin() {
        assert_eq!(decide(Role::Admin, Route::Billing, Action::Export, false), Decision::Audit);
        assert_eq!(decide(Role::Admin, Route::Billing, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Moderator, Route::Billing, Action::View, false), Decision::Deny);
    }

    #[test]
    fn api_delete_is_audited_for_moderators_and_admins_only() {
        assert_eq!(decide(Role::Moderator, Route::Api, Action::Delete, false), Decision::Audit);
        assert_eq!(decide(Role::Admin, Route::Api, Action::Delete, false), Decision::Audit);
        assert_eq!(decide(Role::Member, Route::Api, Action::Delete, false), Decision::Deny);
    }

    #[test]
    fn moderators_have_read_only_admin_dashboard() {
        assert_eq!(decide(Role::Moderator, Route::Admin, Action::View, false), Decision::ReadOnly);
        assert_eq!(decide(Role::Moderator, Route::Admin, Action::Edit, false), Decision::Deny);
    }
}
