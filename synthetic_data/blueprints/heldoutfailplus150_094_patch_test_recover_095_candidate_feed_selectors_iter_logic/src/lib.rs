#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate<'a> {
    pub id: &'a str,
    pub region: &'a str,
    pub active: bool,
    pub score: i32,
    pub tags: &'a [&'a str],
}

pub fn pick_candidate_ids(candidates: &[Candidate<'_>], region: &str, required_tag: &str) -> Vec<String> {
    let mut picked: Vec<&Candidate<'_>> = candidates
        .iter()
        .filter(|c| c.active)
        .filter(|c| c.region == region)
        .filter(|c| c.tags.iter().any(|t| *t == required_tag))
        .collect();

    picked.sort_by_key(|c| c.score);

    picked
        .into_iter()
        .take(3)
        .map(|c| c.id.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn picks_top_three_descending_with_id_tiebreak() {
        let items = vec![
            Candidate { id: "delta", region: "us", active: true, score: 82, tags: &["core"] },
            Candidate { id: "beta", region: "us", active: true, score: 97, tags: &["core", "fast"] },
            Candidate { id: "gamma", region: "us", active: true, score: 97, tags: &["core"] },
            Candidate { id: "alpha", region: "us", active: true, score: 91, tags: &["core"] },
            Candidate { id: "omega", region: "us", active: true, score: 70, tags: &["core"] },
        ];

        assert_eq!(pick_candidate_ids(&items, "us", "core"), vec!["beta", "gamma", "alpha"]);
    }

    #[test]
    fn excludes_blocked_and_zero_score_and_blank_ids() {
        let items = vec![
            Candidate { id: "ok-1", region: "eu", active: true, score: 5, tags: &["core"] },
            Candidate { id: "", region: "eu", active: true, score: 99, tags: &["core"] },
            Candidate { id: "blocked-1", region: "eu", active: true, score: 120, tags: &["core", "blocked"] },
            Candidate { id: "zero", region: "eu", active: true, score: 0, tags: &["core"] },
            Candidate { id: "ok-2", region: "eu", active: true, score: 8, tags: &["core", "new"] },
        ];

        assert_eq!(pick_candidate_ids(&items, "eu", "core"), vec!["ok-2", "ok-1"]);
    }

    #[test]
    fn dedups_by_id_keeping_highest_score_then_sorts() {
        let items = vec![
            Candidate { id: "dup", region: "ap", active: true, score: 10, tags: &["core"] },
            Candidate { id: "dup", region: "ap", active: true, score: 50, tags: &["core", "fast"] },
            Candidate { id: "solo", region: "ap", active: true, score: 40, tags: &["core"] },
            Candidate { id: "other", region: "ap", active: true, score: 50, tags: &["core"] },
        ];

        assert_eq!(pick_candidate_ids(&items, "ap", "core"), vec!["dup", "other", "solo"]);
    }

    #[test]
    fn region_and_required_tag_must_both_match_exactly() {
        let items = vec![
            Candidate { id: "wrong-region", region: "ca", active: true, score: 80, tags: &["core"] },
            Candidate { id: "wrong-tag", region: "us", active: true, score: 90, tags: &["edge"] },
            Candidate { id: "inactive", region: "us", active: false, score: 100, tags: &["core"] },
            Candidate { id: "good", region: "us", active: true, score: 70, tags: &["core", "edge"] },
        ];

        assert_eq!(pick_candidate_ids(&items, "us", "core"), vec!["good"]);
    }

    #[test]
    fn less_than_three_results_are_returned_without_fillers() {
        let items = vec![
            Candidate { id: "one", region: "me", active: true, score: 2, tags: &["core"] },
            Candidate { id: "two", region: "me", active: true, score: 1, tags: &["blocked", "core"] },
        ];

        assert_eq!(pick_candidate_ids(&items, "me", "core"), vec!["one"]);
    }
}
