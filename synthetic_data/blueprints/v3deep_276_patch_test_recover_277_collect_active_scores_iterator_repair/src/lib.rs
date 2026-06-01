#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: &'static str,
    pub active: bool,
    pub score: Option<i32>,
}

pub fn collect_active_scores(entries: &[Entry], min_score: i32) -> Vec<String> {
    let mut out: Vec<(String, i32)> = entries
        .iter()
        .filter(|e| !e.active)
        .filter_map(|e| e.score.map(|score| (e.name.to_string(), score)))
        .filter(|(_, score)| *score >= min_score)
        .map(|(name, score)| (name.to_uppercase(), score))
        .collect();

    out.sort_by_key(|(_, score)| *score);

    out.into_iter()
        .map(|(name, score)| format!("{}:{}", name, score))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{collect_active_scores, Entry};

    #[test]
    fn keeps_only_active_with_real_scores_meeting_threshold_and_sorts() {
        let entries = [
            Entry { name: "amy", active: true, score: Some(17) },
            Entry { name: "bob", active: false, score: Some(80) },
            Entry { name: "cal", active: true, score: None },
            Entry { name: "dia", active: true, score: Some(42) },
            Entry { name: "eli", active: true, score: Some(17) },
            Entry { name: "fay", active: true, score: Some(5) },
        ];

        let got = collect_active_scores(&entries, 10);
        assert_eq!(got, vec!["dia:42", "amy:17", "eli:17"]);
    }

    #[test]
    fn tie_breaks_by_name_and_skips_negative_scores_even_if_threshold_allows_them() {
        let entries = [
            Entry { name: "zoe", active: true, score: Some(9) },
            Entry { name: "abe", active: true, score: Some(9) },
            Entry { name: "mia", active: true, score: Some(-1) },
            Entry { name: "ian", active: true, score: Some(0) },
            Entry { name: "ned", active: false, score: Some(50) },
        ];

        let got = collect_active_scores(&entries, -5);
        assert_eq!(got, vec!["abe:9", "zoe:9", "ian:0"]);
    }

    #[test]
    fn trims_names_before_output_and_dedups_by_trimmed_name_keeping_highest_score() {
        let entries = [
            Entry { name: "  kim", active: true, score: Some(12) },
            Entry { name: "kim", active: true, score: Some(20) },
            Entry { name: "lea  ", active: true, score: Some(18) },
            Entry { name: "lea", active: true, score: Some(16) },
            Entry { name: "max", active: true, score: None },
        ];

        let got = collect_active_scores(&entries, 0);
        assert_eq!(got, vec!["kim:20", "lea:18"]);
    }

    #[test]
    fn returns_empty_when_nothing_qualifies() {
        let entries = [
            Entry { name: "amy", active: false, score: Some(10) },
            Entry { name: "bob", active: true, score: None },
            Entry { name: "cal", active: true, score: Some(-3) },
        ];

        let got = collect_active_scores(&entries, 1);
        assert!(got.is_empty());
    }
}
