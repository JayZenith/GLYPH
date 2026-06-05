#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate<'a> {
    pub id: &'a str,
    pub active: bool,
    pub muted: bool,
    pub role: &'a str,
    pub team: Option<&'a str>,
    pub nickname: Option<&'a str>,
}

pub fn select_visible_recipients(candidates: &[Candidate<'_>], team: Option<&str>) -> Vec<String> {
    let mut out: Vec<String> = candidates
        .iter()
        .filter(|c| c.active)
        .filter(|c| !c.muted)
        .filter(|c| team.map_or(true, |wanted| c.team == Some(wanted)))
        .map(|c| c.nickname.unwrap_or(c.id).to_string())
        .collect();
    out.sort();
    out.dedup();
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn c<'a>(
        id: &'a str,
        active: bool,
        muted: bool,
        role: &'a str,
        team: Option<&'a str>,
        nickname: Option<&'a str>,
    ) -> Candidate<'a> {
        Candidate { id, active, muted, role, team, nickname }
    }

    #[test]
    fn team_filter_excludes_muted_inactive_guests_and_blank_names() {
        let items = vec![
            c("u1", true, false, "member", Some("ops"), Some("Zed")),
            c("u2", true, true, "member", Some("ops"), Some("Amy")),
            c("u3", false, false, "member", Some("ops"), Some("Kai")),
            c("u4", true, false, "guest", Some("ops"), Some("Moe")),
            c("u5", true, false, "member", Some("sales"), Some("Nia")),
            c("u6", true, false, "member", Some("ops"), Some("")),
            c("u7", true, false, "member", Some("ops"), None),
        ];
        assert_eq!(select_visible_recipients(&items, Some("ops")), vec!["u7", "Zed"]);
    }

    #[test]
    fn global_selection_allows_none_team_but_still_excludes_admin_and_support() {
        let items = vec![
            c("a1", true, false, "member", None, Some("Orion")),
            c("a2", true, false, "admin", Some("ops"), Some("Root")),
            c("a3", true, false, "support", Some("ops"), Some("Desk")),
            c("a4", true, false, "member", Some("ops"), None),
            c("a5", true, false, "member", Some("ops"), Some("  ")),
        ];
        assert_eq!(select_visible_recipients(&items, None), vec!["a4", "Orion"]);
    }

    #[test]
    fn dedups_case_insensitively_prefers_earliest_display_and_sorts_ascii_case_insensitive() {
        let items = vec![
            c("id1", true, false, "member", Some("ops"), Some("zoe")),
            c("id2", true, false, "member", Some("ops"), Some("Amy")),
            c("id3", true, false, "member", Some("ops"), Some("ZOE")),
            c("id4", true, false, "member", Some("ops"), Some("bob")),
            c("id5", true, false, "member", Some("ops"), Some("amy")),
        ];
        assert_eq!(select_visible_recipients(&items, Some("ops")), vec!["Amy", "bob", "zoe"]);
    }

    #[test]
    fn fallback_id_is_used_when_nickname_missing_but_not_when_blank() {
        let items = vec![
            c("m1", true, false, "member", Some("eng"), None),
            c("m2", true, false, "member", Some("eng"), Some("")),
            c("m3", true, false, "member", Some("eng"), Some("Eve")),
        ];
        assert_eq!(select_visible_recipients(&items, Some("eng")), vec!["Eve", "m1"]);
    }
}
