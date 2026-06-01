#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Create,
    Update,
    Delete,
    Audit,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Target {
    User,
    Team,
    Project,
}

pub fn route(action: Action, target: Target, dry_run: bool) -> &'static str {
    match (action, target, dry_run) {
        (Action::Create, Target::User, _) => "user:create",
        (Action::Create, _, _) => "create:generic",
        (Action::Update, Target::Project, false) => "project:update",
        (Action::Update, _, true) => "update:apply",
        (Action::Update, _, false) => "update:preview",
        (Action::Delete, _, true) => "delete:confirm",
        (Action::Delete, Target::Project, false) => "project:archive",
        (Action::Delete, _, false) => "delete:now",
        (Action::Audit, Target::User, _) => "audit:user",
        (Action::Audit, _, false) => "audit:full",
        (Action::Audit, _, true) => "audit:skip",
    }
}

#[cfg(test)]
mod tests {
    use super::{route, Action::*, Target::*};

    #[test]
    fn create_routes_are_target_specific() {
        assert_eq!(route(Create, User, false), "user:create");
        assert_eq!(route(Create, Team, false), "team:create");
        assert_eq!(route(Create, Project, true), "project:create:dry-run");
    }

    #[test]
    fn update_routes_flip_on_dry_run() {
        assert_eq!(route(Update, Project, false), "project:update");
        assert_eq!(route(Update, Team, false), "update:apply");
        assert_eq!(route(Update, Team, true), "update:preview");
        assert_eq!(route(Update, User, true), "update:user:preview");
    }

    #[test]
    fn delete_routes_distinguish_preview_and_project_archive() {
        assert_eq!(route(Delete, Team, true), "delete:preview");
        assert_eq!(route(Delete, Project, false), "project:archive");
        assert_eq!(route(Delete, User, false), "delete:now");
    }

    #[test]
    fn audit_routes_depend_on_target_and_mode() {
        assert_eq!(route(Audit, User, false), "audit:user");
        assert_eq!(route(Audit, User, true), "audit:user:dry-run");
        assert_eq!(route(Audit, Team, false), "audit:full");
        assert_eq!(route(Audit, Project, true), "audit:sample");
    }
}
