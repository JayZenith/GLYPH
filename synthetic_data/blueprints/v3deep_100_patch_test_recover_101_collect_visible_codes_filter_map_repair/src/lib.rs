#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Record {
    pub code: Option<String>,
    pub visible: bool,
    pub score: i32,
}

pub fn collect_visible_codes(records: &[Record], min_score: i32) -> Vec<String> {
    records
        .iter()
        .filter(|r| r.visible || r.score >= min_score)
        .filter_map(|r| r.code.as_ref())
        .map(|code| code.trim().to_string())
        .filter(|code| !code.is_empty())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{collect_visible_codes, Record};

    fn rec(code: Option<&str>, visible: bool, score: i32) -> Record {
        Record {
            code: code.map(str::to_string),
            visible,
            score,
        }
    }

    #[test]
    fn keeps_only_visible_with_required_score() {
        let rows = vec![
            rec(Some("A1"), true, 10),
            rec(Some("B2"), false, 15),
            rec(Some("C3"), true, 4),
            rec(Some("D4"), true, 5),
        ];

        assert_eq!(collect_visible_codes(&rows, 5), vec!["A1", "D4"]);
    }

    #[test]
    fn normalizes_case_and_deduplicates_after_trimming() {
        let rows = vec![
            rec(Some(" aa "), true, 7),
            rec(Some("AA"), true, 9),
            rec(Some("Bb"), true, 6),
            rec(Some("bb "), true, 6),
        ];

        assert_eq!(collect_visible_codes(&rows, 5), vec!["AA", "BB"]);
    }

    #[test]
    fn drops_blank_and_missing_codes() {
        let rows = vec![
            rec(None, true, 9),
            rec(Some("   "), true, 9),
            rec(Some("ok"), true, 9),
        ];

        assert_eq!(collect_visible_codes(&rows, 5), vec!["OK"]);
    }

    #[test]
    fn preserves_first_seen_order_of_unique_codes() {
        let rows = vec![
            rec(Some("z9"), true, 5),
            rec(Some("A1"), true, 8),
            rec(Some("Z9"), true, 7),
            rec(Some("a1"), true, 6),
            rec(Some("m3"), true, 9),
        ];

        assert_eq!(collect_visible_codes(&rows, 5), vec!["Z9", "A1", "M3"]);
    }
}
