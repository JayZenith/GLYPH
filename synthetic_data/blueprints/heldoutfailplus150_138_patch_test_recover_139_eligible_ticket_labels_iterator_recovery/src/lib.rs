#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ticket {
    pub id: u32,
    pub team: &'static str,
    pub state: &'static str,
    pub priority: u8,
    pub score: i32,
    pub archived: bool,
    pub tags: &'static [&'static str],
}

pub fn select_ticket_labels(tickets: &[Ticket], team: &str, min_score: i32) -> Vec<String> {
    let mut out: Vec<_> = tickets
        .iter()
        .filter(|t| t.team == team)
        .filter(|t| t.state != "closed")
        .filter(|t| t.score >= min_score)
        .filter(|t| !t.tags.iter().any(|tag| *tag == "blocked"))
        .map(|t| format!("{}:{}:{}", t.priority, t.id, t.state))
        .collect();
    out.sort();
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Ticket> {
        vec![
            Ticket { id: 14, team: "ops", state: "open", priority: 2, score: 9, archived: false, tags: &["infra"] },
            Ticket { id: 3, team: "ops", state: "open", priority: 1, score: 9, archived: false, tags: &["customer"] },
            Ticket { id: 21, team: "ops", state: "open", priority: 1, score: 9, archived: false, tags: &["blocked"] },
            Ticket { id: 4, team: "ops", state: "closed", priority: 1, score: 20, archived: false, tags: &["customer"] },
            Ticket { id: 5, team: "ops", state: "review", priority: 2, score: 7, archived: true, tags: &["customer"] },
            Ticket { id: 6, team: "ops", state: "review", priority: 2, score: 7, archived: false, tags: &["skip"] },
            Ticket { id: 7, team: "ops", state: "review", priority: 3, score: 10, archived: false, tags: &[] },
            Ticket { id: 8, team: "web", state: "open", priority: 1, score: 50, archived: false, tags: &["customer"] },
            Ticket { id: 9, team: "ops", state: "open", priority: 2, score: 7, archived: false, tags: &["customer", "vip"] },
            Ticket { id: 10, team: "ops", state: "review", priority: 2, score: 7, archived: false, tags: &["customer"] },
            Ticket { id: 11, team: "ops", state: "review", priority: 2, score: 7, archived: false, tags: &["customer"] },
            Ticket { id: 12, team: "ops", state: "open", priority: 3, score: 7, archived: false, tags: &["customer"] },
        ]
    }

    #[test]
    fn filters_and_orders_primary_selection() {
        let got = select_ticket_labels(&sample(), "ops", 7);
        assert_eq!(
            got,
            vec![
                "P1-3-open".to_string(),
                "P2-9-open".to_string(),
                "P2-10-review".to_string(),
                "P2-11-review".to_string(),
                "P2-14-open".to_string(),
                "P3-7-review".to_string(),
            ]
        );
    }

    #[test]
    fn excludes_archived_skip_and_exact_threshold() {
        let got = select_ticket_labels(&sample(), "ops", 9);
        assert_eq!(
            got,
            vec![
                "P1-3-open".to_string(),
                "P2-14-open".to_string(),
                "P3-7-review".to_string(),
            ]
        );
        assert!(!got.iter().any(|s| s.contains("21")));
        assert!(!got.iter().any(|s| s.contains("4")));
        assert!(!got.iter().any(|s| s.contains("5")));
        assert!(!got.iter().any(|s| s.contains("6")));
    }

    #[test]
    fn customer_or_vip_only_and_no_priority_three_open() {
        let got = select_ticket_labels(&sample(), "ops", 7);
        assert!(got.contains(&"P2-9-open".to_string()));
        assert!(!got.iter().any(|s| s == "P3-12-open"));
        assert_eq!(got.iter().filter(|s| s.starts_with("P2-")).count(), 4);
    }
}
