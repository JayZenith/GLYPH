#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Role {
    Guest,
    Member,
    Moderator,
    Admin,
    Suspended,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Env {
    Prod,
    Staging,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Request {
    ViewPage,
    EditPage,
    DeletePage,
    ViewAudit,
    ExportData,
    BanUser,
}

pub fn route(role: Role, env: Env, req: Request) -> &'static str {
    match req {
        Request::ViewPage => "public-cdn",
        Request::EditPage => match role {
            Role::Member | Role::Moderator | Role::Admin => "editor",
            _ => "deny",
        },
        Request::DeletePage => match role {
            Role::Moderator | Role::Admin => "danger-zone",
            _ => "deny",
        },
        Request::ViewAudit => match role {
            Role::Admin => "audit-log",
            _ => "deny",
        },
        Request::ExportData => match role {
            Role::Member | Role::Moderator | Role::Admin => "exporter",
            _ => "deny",
        },
        Request::BanUser => match role {
            Role::Admin => "moderation",
            _ => "deny",
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suspended_is_denied_everywhere() {
        let reqs = [
            Request::ViewPage,
            Request::EditPage,
            Request::DeletePage,
            Request::ViewAudit,
            Request::ExportData,
            Request::BanUser,
        ];
        for env in [Env::Prod, Env::Staging] {
            for req in reqs {
                assert_eq!(route(Role::Suspended, env, req), "deny", "env={env:?} req={req:?}");
            }
        }
    }

    #[test]
    fn audit_access_depends_on_environment() {
        assert_eq!(route(Role::Moderator, Env::Staging, Request::ViewAudit), "audit-log");
        assert_eq!(route(Role::Moderator, Env::Prod, Request::ViewAudit), "deny");
        assert_eq!(route(Role::Admin, Env::Prod, Request::ViewAudit), "audit-log");
    }

    #[test]
    fn export_is_restricted_in_prod_but_open_in_staging_for_members() {
        assert_eq!(route(Role::Member, Env::Staging, Request::ExportData), "exporter");
        assert_eq!(route(Role::Member, Env::Prod, Request::ExportData), "deny");
        assert_eq!(route(Role::Moderator, Env::Prod, Request::ExportData), "exporter");
        assert_eq!(route(Role::Admin, Env::Prod, Request::ExportData), "exporter");
    }

    #[test]
    fn destructive_routes_use_different_backends() {
        assert_eq!(route(Role::Moderator, Env::Prod, Request::DeletePage), "review-delete");
        assert_eq!(route(Role::Admin, Env::Prod, Request::DeletePage), "hard-delete");
        assert_eq!(route(Role::Admin, Env::Prod, Request::BanUser), "banhammer");
        assert_eq!(route(Role::Moderator, Env::Prod, Request::BanUser), "banhammer");
        assert_eq!(route(Role::Member, Env::Prod, Request::BanUser), "deny");
    }

    #[test]
    fn view_page_is_not_public_for_signed_in_users() {
        assert_eq!(route(Role::Guest, Env::Prod, Request::ViewPage), "public-cdn");
        assert_eq!(route(Role::Member, Env::Prod, Request::ViewPage), "member-app");
        assert_eq!(route(Role::Moderator, Env::Prod, Request::ViewPage), "member-app");
        assert_eq!(route(Role::Admin, Env::Prod, Request::ViewPage), "member-app");
    }
}
