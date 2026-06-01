pub fn collect_scores(rows: &[&str], min_score: i32) -> Vec<(String, i32)> {
    rows.iter()
        .filter_map(|row| row.split_once(':'))
        .map(|(name, score)| (name.trim(), score.trim()))
        .filter_map(|(name, score)| score.parse::<i32>().ok().map(|value| (name.to_string(), value)))
        .filter(|(_, score)| *score > min_score)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_scores;

    #[test]
    fn keeps_only_valid_non_archived_unique_scores_at_or_above_min() {
        let rows = [
            "alice:10",
            "bob:7",
            "alice:12",
            " archived:50",
            "carol:-2",
            "dave:bad",
            "eve : 7 ",
            "frank:7:extra",
            "grace:9",
            "  :11",
        ];

        assert_eq!(
            collect_scores(&rows, 7),
            vec![
                ("alice".to_string(), 10),
                ("bob".to_string(), 7),
                ("eve".to_string(), 7),
                ("grace".to_string(), 9),
            ]
        );
    }

    #[test]
    fn ignores_blank_names_and_preserves_first_seen_order() {
        let rows = ["zoe:3", "mia:8", "zoe:4", "   :5", "ivy:8", "mia:10"];
        assert_eq!(
            collect_scores(&rows, 3),
            vec![("zoe".to_string(), 3), ("mia".to_string(), 8), ("ivy".to_string(), 8)]
        );
    }
}
