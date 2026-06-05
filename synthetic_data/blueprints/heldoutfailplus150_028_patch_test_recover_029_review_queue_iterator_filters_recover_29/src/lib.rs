#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Ticket {
    pub id: u32,
    pub team: &'static str,
    pub archived: bool,
    pub owner: Option<&'static str>,
    pub priority: u8,
    pub score: i32,
    pub tags: &'static [&'static str],
}

pub fn select_review_queue(tickets: &[Ticket], team: &str, limit: usize) -> Vec<String> {
    let mut items: Vec<&Ticket> = tickets
        .iter()
        .filter(|t| t.team == team)
        .filter(|t| !t.archived)
        .filter(|t| t.owner.is_none())
        .filter(|t| t.priority >= 2)
        .filter(|t| t.score >= 0)
        .collect();

    items.sort_by_key(|t| (t.priority, -t.score, t.id as i32));

    items
        .into_iter()
        .take(limit)
        .map(|t| format!("#{}:{}:{}", t.id, t.priority, t.score))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Ticket> {
        vec![
            Ticket { id: 10, team: "ops", archived: false, owner: None, priority: 3, score: 8, tags: &["customer"] },
            Ticket { id: 11, team: "ops", archived: false, owner: None, priority: 3, score: 8, tags: &["blocked"] },
            Ticket { id: 12, team: "ops", archived: false, owner: Some("amy"), priority: 4, score: 9, tags: &["customer"] },
            Ticket { id: 13, team: "ops", archived: true, owner: None, priority: 5, score: 10, tags: &["customer"] },
            Ticket { id: 14, team: "ops", archived: false, owner: None, priority: 1, score: 20, tags: &["customer"] },
            Ticket { id: 15, team: "ops", archived: false, owner: None, priority: 4, score: 0, tags: &["customer"] },
            Ticket { id: 16, team: "ops", archived: false, owner: None, priority: 5, score: 5, tags: &["internal"] },
            Ticket { id: 17, team: "ops", archived: false, owner: None, priority: 5, score: 7, tags: &["customer", "vip"] },
            Ticket { id: 18, team: "ops", archived: false, owner: None, priority: 5, score: 7, tags: &["customer", "stale"] },
            Ticket { id: 19, team: "app", archived: false, owner: None, priority: 5, score: 50, tags: &["customer"] },
            Ticket { id: 20, team: "ops", archived: false, owner: None, priority: 3, score: -1, tags: &["customer"] },
            Ticket { id: 21, team: "ops", archived: false, owner: None, priority: 5, score: 7, tags: &["customer"] },
        ]
    }

    #[test]
    fn orders_by_priority_then_score_then_id_desc() {
        let got = select_review_queue(&sample(), "ops", 4);
        assert_eq!(
            got,
            vec![
                "#17:5:7".to_string(),
                "#21:5:7".to_string(),
                "#10:3:8".to_string(),
                "#15:4:0".to_string(),
            ]
        );
    }

    #[test]
    fn excludes_blocked_stale_and_non_customer_even_when_other_fields_match() {
        let got = select_review_queue(&sample(), "ops", 10);
        assert!(!got.iter().any(|s| s.starts_with("#11:")), "blocked should be excluded");
        assert!(!got.iter().any(|s| s.starts_with("#16:")), "non-customer should be excluded");
        assert!(!got.iter().any(|s| s.starts_with("#18:")), "stale should be excluded");
        assert!(got.iter().any(|s| s.starts_with("#17:")));
        assert!(got.iter().any(|s| s.starts_with("#21:")));
    }

    #[test]
    fn zero_score_is_excluded_but_negative_priority_is_not_relied_on() {
        let got = select_review_queue(&sample(), "ops", 10);
        assert!(!got.iter().any(|s| s.starts_with("#15:")), "zero score should be excluded");
        assert!(!got.iter().any(|s| s.starts_with("#14:")), "priority below threshold should be excluded");
    }

    #[test]
    fn enforces_limit_after_filtering_and_sorting() {
        let got = select_review_queue(&sample(), "ops", 2);
        assert_eq!(got, vec!["#17:5:7".to_string(), "#21:5:7".to_string()]);
    }
}
