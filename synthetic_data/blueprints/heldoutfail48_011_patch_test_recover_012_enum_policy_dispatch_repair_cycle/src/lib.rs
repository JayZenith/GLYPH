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
    Audit,
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
    RequireLogin,
    Deny,
    Escalate,
}

pub fn decide(role: Role, route: Route, action: Action, suspended: bool) -> Decision {
    match route {
        Route::Home => Decision::Allow,
        Route::Profile => match action {
            Action::View => Decision::Allow,
            Action::Edit => {
                if role == Role::Guest {
                    Decision::RequireLogin
                } else {
                    Decision::Allow
                }
            }
            _ => Decision::Deny,
        },
        Route::Billing => match action {
            Action::View | Action::Export => {
                if role == Role::Guest {
                    Decision::RequireLogin
                } else {
                    Decision::Allow
                }
            }
            _ => Decision::Deny,
        },
        Route::AdminPanel => match action {
            Action::View => {
                if role == Role::Admin {
                    Decision::Allow
                } else {
                    Decision::Deny
                }
            }
            Action::Edit | Action::Delete => {
                if role == Role::Admin || role == Role::Moderator {
                    Decision::Allow
                } else {
                    Decision::Deny
                }
            }
            Action::Export => Decision::Allow,
        },
        Route::Audit => match action {
            Action::View => {
                if role == Role::Admin || role == Role::Moderator {
                    Decision::Allow
                } else {
                    Decision::Deny
                }
            }
            Action::Export => {
                if role == Role::Admin {
                    Decision::Allow
                } else {
                    Decision::Deny
                }
            }
            _ => Decision::Deny,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suspended_users_are_denied_everywhere_except_home_view_requires_login_for_guest() {
        assert_eq!(decide(Role::Member, Route::Profile, Action::View, true), Decision::Deny);
        assert_eq!(decide(Role::Admin, Route::Audit, Action::Export, true), Decision::Deny);
        assert_eq!(decide(Role::Guest, Route::Home, Action::View, true), Decision::RequireLogin);
    }

    #[test]
    fn profile_view_requires_login_for_guest_but_allows_logged_in_roles() {
        assert_eq!(decide(Role::Guest, Route::Profile, Action::View, false), Decision::RequireLogin);
        assert_eq!(decide(Role::Member, Route::Profile, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Moderator, Route::Profile, Action::View, false), Decision::Allow);
    }

    #[test]
    fn billing_is_member_only_and_export_needs_admin() {
        assert_eq!(decide(Role::Guest, Route::Billing, Action::View, false), Decision::RequireLogin);
        assert_eq!(decide(Role::Member, Route::Billing, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Moderator, Route::Billing, Action::View, false), Decision::Deny);
        assert_eq!(decide(Role::Admin, Route::Billing, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Billing, Action::Export, false), Decision::Escalate);
        assert_eq!(decide(Role::Admin, Route::Billing, Action::Export, false), Decision::Allow);
    }

    #[test]
    fn admin_panel_edit_delete_is_admin_only_and_export_is_never_direct() {
        assert_eq!(decide(Role::Moderator, Route::AdminPanel, Action::Edit, false), Decision::Escalate);
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::Delete, false), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::AdminPanel, Action::Edit, false), Decision::Deny);
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::Export, false), Decision::Escalate);
    }

    #[test]
    fn audit_view_is_staff_only_and_export_escalates_for_moderator() {
        assert_eq!(decide(Role::Moderator, Route::Audit, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Audit, Action::View, false), Decision::Deny);
        assert_eq!(decide(Role::Moderator, Route::Audit, Action::Export, false), Decision::Escalate);
        assert_eq!(decide(Role::Admin, Route::Audit, Action::Export, false), Decision::Allow);
    }

    #[test]
    fn home_only_allows_view_and_never_grants_write_actions() {
        assert_eq!(decide(Role::Guest, Route::Home, Action::View, false), Decision::Allow);
        assert_eq!(decide(Role::Member, Route::Home, Action::Edit, false), Decision::Deny);
        assert_eq!(decide(Role::Admin, Route::Home, Action::Delete, false), Decision::Deny);
    }
}
