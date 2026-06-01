pub fn selected_scores(lines: &[&str], min_score: i32) -> Vec<(String, i32)> {
    lines
        .iter()
        .filter_map(|line| {
            let (tag, score_text) = line.split_once(':')?;
            let score = score_text.parse::<i32>().ok()?;
            if !tag.starts_with("keep-") {
                return None;
            }
            if score <= min_score {
                return None;
            }
            Some((tag.to_string(), score))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::selected_scores;

    #[test]
    fn keeps_trimmed_tags_and_scores_at_threshold() {
        let input = [
            " keep-alpha : 10 ",
            "drop-beta:50",
            "keep-gamma:9",
            "keep-delta:10",
            "keep-epsilon:12",
        ];

        assert_eq!(
            selected_scores(&input, 10),
            vec![
                ("keep-alpha".to_string(), 10),
                ("keep-delta".to_string(), 10),
                ("keep-epsilon".to_string(), 12),
            ]
        );
    }

    #[test]
    fn ignores_invalid_scores_and_negative_values() {
        let input = [
            "keep-a:7",
            "keep-b:-2",
            "keep-c:nope",
            "keep-d: 3",
            "skip-e:9",
        ];

        assert_eq!(
            selected_scores(&input, 0),
            vec![
                ("keep-a".to_string(), 7),
                ("keep-d".to_string(), 3),
            ]
        );
    }

    #[test]
    fn later_duplicates_replace_earlier_ones_without_reordering() {
        let input = [
            "keep-a:1",
            "keep-b:4",
            "keep-a:9",
            "keep-c:2",
            "keep-b:6",
        ];

        assert_eq!(
            selected_scores(&input, 0),
            vec![
                ("keep-a".to_string(), 9),
                ("keep-b".to_string(), 6),
                ("keep-c".to_string(), 2),
            ]
        );
    }
}
