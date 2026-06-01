pub struct Item<'a> {
    pub active: bool,
    pub priority: u8,
    pub label: Option<&'a str>,
}

pub fn collect_active_labels(items: &[Item<'_>]) -> Vec<String> {
    items
        .iter()
        .filter(|item| item.priority >= 2)
        .filter_map(|item| item.label)
        .map(|label| label.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{collect_active_labels, Item};

    #[test]
    fn keeps_only_active_nonblank_labels_with_min_priority() {
        let items = vec![
            Item { active: true, priority: 3, label: Some(" alpha ") },
            Item { active: false, priority: 5, label: Some("hidden") },
            Item { active: true, priority: 1, label: Some("low") },
            Item { active: true, priority: 2, label: Some("   ") },
            Item { active: true, priority: 4, label: None },
            Item { active: true, priority: 2, label: Some("beta") },
        ];

        assert_eq!(collect_active_labels(&items), vec!["alpha", "beta"]);
    }

    #[test]
    fn preserves_input_order_after_filtering() {
        let items = vec![
            Item { active: true, priority: 2, label: Some(" second ") },
            Item { active: true, priority: 4, label: Some("first") },
            Item { active: false, priority: 9, label: Some("skip") },
            Item { active: true, priority: 2, label: Some(" third") },
        ];

        assert_eq!(collect_active_labels(&items), vec!["second", "first", "third"]);
    }

    #[test]
    fn drops_missing_and_whitespace_only_labels() {
        let items = vec![
            Item { active: true, priority: 2, label: None },
            Item { active: true, priority: 2, label: Some("") },
            Item { active: true, priority: 2, label: Some("  ok  ") },
            Item { active: true, priority: 2, label: Some("   ") },
        ];

        assert_eq!(collect_active_labels(&items), vec!["ok"]);
    }
}
