#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Method {
    Get,
    Post,
    Delete,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Auth {
    Anonymous,
    User,
    Admin,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    View,
    Create,
    Remove,
    Audit,
    Reject(&'static str),
}

pub fn decide_action(method: Method, path: &str, auth: Auth) -> Action {
    match (method, path, auth) {
        (Method::Get, "/items", Auth::Anonymous) => Action::Reject("login required"),
        (Method::Get, "/items", _) => Action::View,
        (Method::Post, "/items", Auth::Admin) => Action::Audit,
        (Method::Post, "/items", _) => Action::Create,
        (Method::Delete, "/items", Auth::Admin) => Action::Remove,
        (Method::Delete, "/items", _) => Action::Reject("admin only"),
        (Method::Get, "/admin/audit", Auth::Admin) => Action::View,
        (Method::Get, "/admin/audit", _) => Action::Reject("forbidden"),
        (_, _, Auth::Anonymous) => Action::Reject("not found"),
        _ => Action::Reject("forbidden"),
    }
}

#[cfg(test)]
mod tests {
    use super::{decide_action, Action, Auth, Method};

    #[test]
    fn items_get_allows_anonymous_view() {
        assert_eq!(decide_action(Method::Get, "/items", Auth::Anonymous), Action::View);
    }

    #[test]
    fn items_post_requires_authenticated_user_or_admin_and_creates() {
        assert_eq!(decide_action(Method::Post, "/items", Auth::User), Action::Create);
        assert_eq!(decide_action(Method::Post, "/items", Auth::Admin), Action::Create);
        assert_eq!(
            decide_action(Method::Post, "/items", Auth::Anonymous),
            Action::Reject("login required")
        );
    }

    #[test]
    fn delete_items_is_admin_only() {
        assert_eq!(decide_action(Method::Delete, "/items", Auth::Admin), Action::Remove);
        assert_eq!(
            decide_action(Method::Delete, "/items", Auth::User),
            Action::Reject("admin only")
        );
        assert_eq!(
            decide_action(Method::Delete, "/items", Auth::Anonymous),
            Action::Reject("login required")
        );
    }

    #[test]
    fn admin_audit_is_audited_only_for_admin() {
        assert_eq!(
            decide_action(Method::Get, "/admin/audit", Auth::Admin),
            Action::Audit
        );
        assert_eq!(
            decide_action(Method::Get, "/admin/audit", Auth::User),
            Action::Reject("admin only")
        );
        assert_eq!(
            decide_action(Method::Get, "/admin/audit", Auth::Anonymous),
            Action::Reject("login required")
        );
    }

    #[test]
    fn unknown_paths_are_not_found_for_authenticated_users_too() {
        assert_eq!(
            decide_action(Method::Get, "/missing", Auth::User),
            Action::Reject("not found")
        );
        assert_eq!(
            decide_action(Method::Delete, "/missing", Auth::Admin),
            Action::Reject("not found")
        );
    }

    #[test]
    fn unknown_method_path_with_anonymous_is_still_not_found() {
        assert_eq!(
            decide_action(Method::Post, "/missing", Auth::Anonymous),
            Action::Reject("not found")
        );
    }
}
