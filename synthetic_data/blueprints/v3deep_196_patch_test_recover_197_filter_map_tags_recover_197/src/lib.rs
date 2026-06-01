pub fn collect_priority_tags(input: &[&str]) -> Vec<String> {
    input
        .iter()
        .filter_map(|item| {
            let (tag, score) = item.split_once(':')?;
            let score: i32 = score.parse().ok()?;
            if score >= 10 {
                Some(tag.to_string())
            } else {
                None
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_priority_tags;

    #[test]
    fn keeps_high_scores_only() {
        let input = ["alpha:12", "beta:9", "gamma:10", "delta:3"];
        assert_eq!(collect_priority_tags(&input), vec!["alpha", "gamma"]);
    }

    #[test]
    fn trims_and_normalizes_case() {
        let input = ["  Alpha :12", "BETA:11", " gamma :10 "];
        assert_eq!(collect_priority_tags(&input), vec!["alpha", "beta", "gamma"]);
    }

    #[test]
    fn skips_empty_tags_and_invalid_scores() {
        let input = [" :12", "ok:foo", "valid:15", "missingcolon", "also_valid:10"];
        assert_eq!(collect_priority_tags(&input), vec!["valid", "also_valid"]);
    }

    #[test]
    fn deduplicates_preserving_first_accepted_order() {
        let input = ["Alpha:12", "alpha:15", "beta:10", "BETA:13", "gamma:9"];
        assert_eq!(collect_priority_tags(&input), vec!["alpha", "beta"]);
    }

    #[test]
    fn rejects_scores_above_cap() {
        let input = ["alpha:101", "beta:100", "gamma:10"];
        assert_eq!(collect_priority_tags(&input), vec!["beta", "gamma"]);
    }
}
