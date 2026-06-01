pub fn selected_scores(input: &[&str], min_score: i32) -> Vec<(String, i32)> {
    input
        .iter()
        .filter_map(|line| {
            let (name, score_text) = line.split_once(':')?;
            let score = score_text.parse::<i32>().ok()?;
            if score <= min_score {
                return None;
            }
            Some((name.to_string(), score))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::selected_scores;

    #[test]
    fn keeps_valid_entries_at_or_above_threshold_sorted_desc_then_name() {
        let input = ["alice:10", "bob:7", "carol:10", "dave:3"];
        assert_eq!(
            selected_scores(&input, 7),
            vec![
                ("alice".to_string(), 10),
                ("carol".to_string(), 10),
                ("bob".to_string(), 7),
            ]
        );
    }

    #[test]
    fn trims_fields_and_skips_invalid_blank_and_negative_scores() {
        let input = [
            "  zoe : 8 ",
            "bad",
            "mia:-2",
            "   : 9",
            "ian:xyz",
            " ava : 8",
        ];
        assert_eq!(
            selected_scores(&input, 0),
            vec![("ava".to_string(), 8), ("zoe".to_string(), 8)]
        );
    }

    #[test]
    fn keeps_duplicates_and_allows_zero_threshold() {
        let input = ["ann:0", "bob:0", "ann:2", "bob:2"];
        assert_eq!(
            selected_scores(&input, 0),
            vec![("ann".to_string(), 2), ("bob".to_string(), 2), ("ann".to_string(), 0), ("bob".to_string(), 0)]
        );
    }
}
