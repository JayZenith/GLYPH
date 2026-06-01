#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Action {
    View,
    Comment { flagged: bool },
    Delete { own_post: bool },
    BanUser { temporary: bool },
    Audit,
}

pub fn permission_level(role: Role, action: Action) -> u8 {
    match (role, action) {
        (Role::Guest, Action::View) => 1,
        (Role::Guest, Action::Comment { .. }) => 1,
        (Role::Member, Action::View) => 2,
        (Role::Member, Action::Comment { .. }) => 2,
        (Role::Member, Action::Delete { .. }) => 3,
        (Role::Moderator, Action::View) => 3,
        (Role::Moderator, Action::Comment { .. }) => 3,
        (Role::Moderator, Action::Delete { .. }) => 3,
        (Role::Moderator, Action::BanUser { .. }) => 4,
        (Role::Admin, Action::View) => 4,
        (Role::Admin, Action::Comment { .. }) => 4,
        (Role::Admin, Action::Delete { .. }) => 4,
        (Role::Admin, Action::BanUser { .. }) => 4,
        (Role::Admin, Action::Audit) => 5,
        _ => 0,
    }
}

pub fn route_action(role: Role, action: Action) -> &'static str {
    match action {
        Action::View => "public-feed",
        Action::Comment { .. } => {
            if permission_level(role, Action::Comment { flagged: false }) >= 2 {
                "comment-queue"
            } else {
                "denied"
            }
        }
        Action::Delete { .. } => {
            if permission_level(role, Action::Delete { own_post: false }) >= 3 {
                "delete-any"
            } else {
                "denied"
            }
        }
        Action::BanUser { .. } => {
            if permission_level(role, Action::BanUser { temporary: false }) >= 4 {
                "ban-temp"
            } else {
                "denied"
            }
        }
        Action::Audit => {
            if permission_level(role, Action::Audit) >= 5 {
                "audit-log"
            } else {
                "denied"
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guests_cannot_comment_but_can_view() {
        assert_eq!(route_action(Role::Guest, Action::View), "public-feed");
        assert_eq!(route_action(Role::Guest, Action::Comment { flagged: false }), "denied");
    }

    #[test]
    fn member_delete_depends_on_ownership() {
        assert_eq!(route_action(Role::Member, Action::Delete { own_post: true }), "delete-own");
        assert_eq!(route_action(Role::Member, Action::Delete { own_post: false }), "denied");
    }

    #[test]
    fn moderator_flagged_comments_go_to_review() {
        assert_eq!(route_action(Role::Moderator, Action::Comment { flagged: true }), "review-queue");
        assert_eq!(route_action(Role::Moderator, Action::Comment { flagged: false }), "comment-queue");
    }

    #[test]
    fn moderator_ban_routing_respects_temporary_flag() {
        assert_eq!(route_action(Role::Moderator, Action::BanUser { temporary: true }), "ban-temp");
        assert_eq!(route_action(Role::Moderator, Action::BanUser { temporary: false }), "ban-perm");
    }

    #[test]
    fn admin_delete_and_audit_have_dedicated_routes() {
        assert_eq!(route_action(Role::Admin, Action::Delete { own_post: false }), "delete-any");
        assert_eq!(route_action(Role::Admin, Action::Audit), "audit-log");
    }
}
