#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    Get,
    Create,
    Update,
    Delete,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Target {
    Users,
    User(u32),
    Reports,
    Report(u32),
    Health,
}

pub fn route(action: Action, target: Target) -> &'static str {
    match (action, target) {
        (Action::Get, Target::Users) => "users:list",
        (Action::Get, Target::User(_)) => "users:list",
        (Action::Create, Target::Users) => "users:create",
        (Action::Update, Target::User(_)) => "users:create",
        (Action::Delete, Target::User(_)) => "users:delete",
        (Action::Get, Target::Reports) => "reports:list",
        (Action::Get, Target::Report(_)) => "reports:list",
        (Action::Create, Target::Reports) => "reports:create",
        (Action::Update, Target::Report(_)) => "reports:update",
        (Action::Delete, Target::Report(_)) => "reports:update",
        (_, Target::Health) => "health:check",
        _ => "invalid",
    }
}

#[cfg(test)]
mod tests {
    use super::{route, Action, Target};

    #[test]
    fn users_routes_are_specific() {
        assert_eq!(route(Action::Get, Target::Users), "users:list");
        assert_eq!(route(Action::Get, Target::User(7)), "users:get");
        assert_eq!(route(Action::Create, Target::Users), "users:create");
        assert_eq!(route(Action::Update, Target::User(7)), "users:update");
        assert_eq!(route(Action::Delete, Target::User(7)), "users:delete");
    }

    #[test]
    fn reports_routes_are_specific() {
        assert_eq!(route(Action::Get, Target::Reports), "reports:list");
        assert_eq!(route(Action::Get, Target::Report(9)), "reports:get");
        assert_eq!(route(Action::Create, Target::Reports), "reports:create");
        assert_eq!(route(Action::Update, Target::Report(9)), "reports:update");
        assert_eq!(route(Action::Delete, Target::Report(9)), "reports:delete");
    }

    #[test]
    fn health_only_allows_get() {
        assert_eq!(route(Action::Get, Target::Health), "health:check");
        assert_eq!(route(Action::Create, Target::Health), "invalid");
        assert_eq!(route(Action::Update, Target::Health), "invalid");
        assert_eq!(route(Action::Delete, Target::Health), "invalid");
    }

    #[test]
    fn unsupported_collection_operations_stay_invalid() {
        assert_eq!(route(Action::Delete, Target::Users), "invalid");
        assert_eq!(route(Action::Update, Target::Users), "invalid");
        assert_eq!(route(Action::Delete, Target::Reports), "invalid");
        assert_eq!(route(Action::Update, Target::Reports), "invalid");
        assert_eq!(route(Action::Create, Target::User(1)), "invalid");
        assert_eq!(route(Action::Create, Target::Report(1)), "invalid");
    }
}
