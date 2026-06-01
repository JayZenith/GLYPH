#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Method {
    Get,
    Post,
    Put,
    Delete,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    User,
    Admin,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    Health,
    Item { method: Method, archived: bool },
    Admin { method: Method },
}

pub fn action_for(route: Route, role: Role) -> &'static str {
    match route {
        Route::Health => "read-health",
        Route::Item { method, archived } => match method {
            Method::Get => {
                if archived {
                    "read-item"
                } else {
                    "read-item"
                }
            }
            Method::Post => "update-item",
            Method::Put => "create-item",
            Method::Delete => {
                if role == Role::Guest {
                    "delete-item"
                } else {
                    "delete-item"
                }
            }
        },
        Route::Admin { method } => match method {
            Method::Get => "admin-view",
            Method::Post => "admin-view",
            Method::Put => {
                if role == Role::Admin {
                    "admin-update"
                } else {
                    "admin-update"
                }
            }
            Method::Delete => "admin-purge",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_is_always_read_only() {
        assert_eq!(action_for(Route::Health, Role::Guest), "read-health");
        assert_eq!(action_for(Route::Health, Role::Admin), "read-health");
    }

    #[test]
    fn item_get_distinguishes_archived() {
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Get,
                    archived: false,
                },
                Role::User,
            ),
            "read-item"
        );
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Get,
                    archived: true,
                },
                Role::User,
            ),
            "read-archived-item"
        );
    }

    #[test]
    fn item_write_methods_map_correctly() {
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Post,
                    archived: false,
                },
                Role::User,
            ),
            "create-item"
        );
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Put,
                    archived: false,
                },
                Role::User,
            ),
            "update-item"
        );
    }

    #[test]
    fn item_delete_is_blocked_for_guests_only() {
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Delete,
                    archived: false,
                },
                Role::Guest,
            ),
            "forbidden"
        );
        assert_eq!(
            action_for(
                Route::Item {
                    method: Method::Delete,
                    archived: false,
                },
                Role::User,
            ),
            "delete-item"
        );
    }

    #[test]
    fn admin_post_creates_jobs() {
        assert_eq!(
            action_for(
                Route::Admin {
                    method: Method::Post,
                },
                Role::Admin,
            ),
            "admin-create"
        );
    }

    #[test]
    fn admin_put_requires_admin_role() {
        assert_eq!(
            action_for(
                Route::Admin {
                    method: Method::Put,
                },
                Role::Admin,
            ),
            "admin-update"
        );
        assert_eq!(
            action_for(
                Route::Admin {
                    method: Method::Put,
                },
                Role::User,
            ),
            "forbidden"
        );
    }

    #[test]
    fn admin_delete_is_never_directly_allowed() {
        assert_eq!(
            action_for(
                Route::Admin {
                    method: Method::Delete,
                },
                Role::Admin,
            ),
            "forbidden"
        );
    }
}
