#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub active: bool,
    pub score: i32,
    pub label: Option<&'static str>,
}

pub fn collect_labels(records: &[Record], min_score: i32) -> Vec<String> {
    let mut out: Vec<String> = records
        .iter()
        .filter(|r| r.active)
        .filter_map(|r| r.label)
        .map(|label| label.trim().to_string())
        .filter(|label| !label.is_empty())
        .collect();

    out.sort();
    out.dedup();
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_only_active_with_score_and_normalized_labels() {
        let records = vec![
            Record { active: true, score: 10, label: Some("  Alpha ") },
            Record { active: true, score: 7, label: Some("beta") },
            Record { active: true, score: 5, label: Some("  ") },
            Record { active: true, score: 11, label: Some("MiXeD") },
            Record { active: false, score: 20, label: Some("hidden") },
            Record { active: true, score: 12, label: None },
        ];

        assert_eq!(collect_labels(&records, 8), vec!["alpha", "mixed"]);
    }

    #[test]
    fn dedups_case_insensitively_and_preserves_first_seen_order() {
        let records = vec![
            Record { active: true, score: 9, label: Some(" Zebra ") },
            Record { active: true, score: 10, label: Some("apple") },
            Record { active: true, score: 11, label: Some("zebra") },
            Record { active: true, score: 12, label: Some("APPLE ") },
            Record { active: true, score: 4, label: Some("late") },
        ];

        assert_eq!(collect_labels(&records, 8), vec!["zebra", "apple"]);
    }

    #[test]
    fn empty_when_nothing_qualifies() {
        let records = vec![
            Record { active: false, score: 99, label: Some("alpha") },
            Record { active: true, score: 1, label: Some("beta") },
            Record { active: true, score: 2, label: None },
        ];

        let out = collect_labels(&records, 5);
        assert!(out.is_empty());
    }
}
