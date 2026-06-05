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
    AdminPanel,
    Support,
    ModerationQueue,
    Api,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    View,
    Edit,
    Delete,
    Escalate,
    Export,
}

pub fn decide(role: Role, route: Route, action: Action, suspended: bool) -> &'static str {
    match route {
        Route::Home => "allow",
        Route::Billing => match role {
            Role::Admin => "allow",
            _ => "deny",
        },
        Route::AdminPanel => match role {
            Role::Admin => "allow",
            Role::Moderator => "review",
            _ => "deny",
        },
        Route::Support => match action {
            Action::View => "allow",
            Action::Escalate => "allow",
            _ => "deny",
        },
        Route::ModerationQueue => match role {
            Role::Moderator | Role::Admin => "allow",
            _ => "deny",
        },
        Route::Api => {
            if suspended {
                "deny"
            } else {
                match action {
                    Action::View => "allow",
                    Action::Export => "allow",
                    _ => "deny",
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn home_is_read_only_for_guests() {
        assert_eq!(decide(Role::Guest, Route::Home, Action::View, false), "allow");
        assert_eq!(decide(Role::Guest, Route::Home, Action::Edit, false), "deny");
    }

    #[test]
    fn billing_allows_members_to_view_but_not_edit() {
        assert_eq!(decide(Role::Member, Route::Billing, Action::View, false), "allow");
        assert_eq!(decide(Role::Member, Route::Billing, Action::Edit, false), "deny");
    }

    #[test]
    fn suspended_admin_cannot_use_admin_panel() {
        assert_eq!(decide(Role::Admin, Route::AdminPanel, Action::View, true), "deny");
    }

    #[test]
    fn support_escalation_requires_staff() {
        assert_eq!(decide(Role::Member, Route::Support, Action::Escalate, false), "review");
        assert_eq!(decide(Role::Moderator, Route::Support, Action::Escalate, false), "allow");
    }

    #[test]
    fn moderation_queue_delete_needs_admin() {
        assert_eq!(decide(Role::Moderator, Route::ModerationQueue, Action::Delete, false), "review");
        assert_eq!(decide(Role::Admin, Route::ModerationQueue, Action::Delete, false), "allow");
    }

    #[test]
    fn api_export_requires_admin_and_edit_is_member_plus() {
        assert_eq!(decide(Role::Member, Route::Api, Action::Edit, false), "allow");
        assert_eq!(decide(Role::Guest, Route::Api, Action::Edit, false), "deny");
        assert_eq!(decide(Role::Moderator, Route::Api, Action::Export, false), "review");
        assert_eq!(decide(Role::Admin, Route::Api, Action::Export, false), "allow");
    }
}
