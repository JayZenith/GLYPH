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
    Billing,
    Reports,
    AdminPanel,
    ApiKeys,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Export,
}

pub fn is_allowed(role: Role, route: Route, action: Action, suspended: bool, internal_ip: bool) -> bool {
    if suspended {
        return false;
    }

    match route {
        Route::Home => match action {
            Action::View => true,
            _ => false,
        },
        Route::Billing => match role {
            Role::Admin => true,
            Role::Member => matches!(action, Action::View),
            _ => false,
        },
        Route::Reports => match action {
            Action::View => !matches!(role, Role::Guest),
            Action::Export => matches!(role, Role::Admin | Role::Moderator),
            _ => false,
        },
        Route::AdminPanel => matches!(role, Role::Admin),
        Route::ApiKeys => matches!(role, Role::Admin) && internal_ip,
    }
}

#[cfg(test)]
mod tests {
    use super::{is_allowed, Action::*, Role::*, Route::*};

    #[test]
    fn guest_home_is_view_only() {
        assert!(is_allowed(Guest, Home, View, false, false));
        assert!(!is_allowed(Guest, Home, Edit, false, false));
    }

    #[test]
    fn suspended_admin_is_still_allowed_home_view_only() {
        assert!(is_allowed(Admin, Home, View, true, false));
        assert!(!is_allowed(Admin, Billing, View, true, false));
    }

    #[test]
    fn member_billing_can_edit_but_not_delete() {
        assert!(is_allowed(Member, Billing, View, false, false));
        assert!(is_allowed(Member, Billing, Edit, false, false));
        assert!(!is_allowed(Member, Billing, Delete, false, false));
    }

    #[test]
    fn moderator_can_view_and_export_reports_but_not_delete_them() {
        assert!(is_allowed(Moderator, Reports, View, false, false));
        assert!(is_allowed(Moderator, Reports, Export, false, false));
        assert!(!is_allowed(Moderator, Reports, Delete, false, false));
    }

    #[test]
    fn member_can_export_reports_but_guest_cannot_view() {
        assert!(is_allowed(Member, Reports, Export, false, false));
        assert!(!is_allowed(Guest, Reports, View, false, false));
    }

    #[test]
    fn admin_panel_requires_admin_and_view_action() {
        assert!(is_allowed(Admin, AdminPanel, View, false, false));
        assert!(!is_allowed(Admin, AdminPanel, Delete, false, false));
        assert!(!is_allowed(Moderator, AdminPanel, View, false, false));
    }

    #[test]
    fn api_keys_rules_depend_on_internal_network_and_action() {
        assert!(is_allowed(Admin, ApiKeys, View, false, true));
        assert!(is_allowed(Admin, ApiKeys, Edit, false, true));
        assert!(!is_allowed(Admin, ApiKeys, Delete, false, true));
        assert!(!is_allowed(Admin, ApiKeys, View, false, false));
        assert!(!is_allowed(Member, ApiKeys, View, false, true));
    }
}
