#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Method {
    Get,
    Post,
    Put,
    Delete,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Auth {
    None,
    User,
    Admin,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Route {
    Home,
    Login,
    Search,
    SaveDraft,
    Publish,
    Replace,
    Remove,
    AdminPanel,
    Audit,
    NotFound,
}

pub fn resolve(method: Method, path: &str, auth: Auth) -> Route {
    match (method, path, auth) {
        (_, "/", _) => Route::Home,
        (_, "/login", _) => Route::Login,
        (_, "/search", _) => Route::Search,
        (Method::Post, "/draft", _) => Route::SaveDraft,
        (Method::Post, "/publish", Auth::User) => Route::Publish,
        (Method::Put, "/post", Auth::Admin) => Route::Replace,
        (Method::Delete, "/post", Auth::User) => Route::Remove,
        (_, "/admin", Auth::User) => Route::AdminPanel,
        (_, "/audit", Auth::Admin) => Route::Audit,
        _ => Route::NotFound,
    }
}

#[cfg(test)]
mod tests {
    use super::{resolve, Auth, Method, Route};

    #[test]
    fn public_routes_are_method_restricted() {
        assert_eq!(resolve(Method::Get, "/", Auth::None), Route::Home);
        assert_eq!(resolve(Method::Get, "/login", Auth::None), Route::Login);
        assert_eq!(resolve(Method::Get, "/search", Auth::None), Route::Search);
        assert_eq!(resolve(Method::Post, "/", Auth::None), Route::NotFound);
        assert_eq!(resolve(Method::Delete, "/login", Auth::None), Route::NotFound);
        assert_eq!(resolve(Method::Put, "/search", Auth::None), Route::NotFound);
    }

    #[test]
    fn draft_requires_auth_but_accepts_both_roles() {
        assert_eq!(resolve(Method::Post, "/draft", Auth::None), Route::NotFound);
        assert_eq!(resolve(Method::Post, "/draft", Auth::User), Route::SaveDraft);
        assert_eq!(resolve(Method::Post, "/draft", Auth::Admin), Route::SaveDraft);
    }

    #[test]
    fn publish_requires_admin_post_only() {
        assert_eq!(resolve(Method::Post, "/publish", Auth::Admin), Route::Publish);
        assert_eq!(resolve(Method::Post, "/publish", Auth::User), Route::NotFound);
        assert_eq!(resolve(Method::Get, "/publish", Auth::Admin), Route::NotFound);
    }

    #[test]
    fn post_mutations_split_by_role() {
        assert_eq!(resolve(Method::Put, "/post", Auth::Admin), Route::Replace);
        assert_eq!(resolve(Method::Put, "/post", Auth::User), Route::NotFound);
        assert_eq!(resolve(Method::Delete, "/post", Auth::Admin), Route::Remove);
        assert_eq!(resolve(Method::Delete, "/post", Auth::User), Route::NotFound);
    }

    #[test]
    fn admin_panel_is_admin_only_and_get_only() {
        assert_eq!(resolve(Method::Get, "/admin", Auth::Admin), Route::AdminPanel);
        assert_eq!(resolve(Method::Post, "/admin", Auth::Admin), Route::NotFound);
        assert_eq!(resolve(Method::Get, "/admin", Auth::User), Route::NotFound);
    }

    #[test]
    fn audit_is_admin_only_and_get_only() {
        assert_eq!(resolve(Method::Get, "/audit", Auth::Admin), Route::Audit);
        assert_eq!(resolve(Method::Delete, "/audit", Auth::Admin), Route::NotFound);
        assert_eq!(resolve(Method::Get, "/audit", Auth::User), Route::NotFound);
    }
}
