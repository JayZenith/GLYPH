#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Candidate<'a> {
    pub id: &'a str,
    pub region: &'a str,
    pub active: bool,
    pub deprecated: bool,
    pub score: i32,
    pub tags: &'a [&'a str],
}

pub fn visible_candidate_ids(candidates: &[Candidate<'_>], region: &str, limit: usize) -> Vec<String> {
    let mut picked: Vec<&Candidate<'_>> = candidates
        .iter()
        .filter(|c| c.active)
        .filter(|c| c.region == region)
        .filter(|c| c.score >= 0)
        .collect();

    picked.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.id.cmp(b.id)));

    picked
        .into_iter()
        .take(limit)
        .map(|c| c.id.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{visible_candidate_ids, Candidate};

    fn c<'a>(
        id: &'a str,
        region: &'a str,
        active: bool,
        deprecated: bool,
        score: i32,
        tags: &'a [&'a str],
    ) -> Candidate<'a> {
        Candidate {
            id,
            region,
            active,
            deprecated,
            score,
            tags,
        }
    }

    #[test]
    fn excludes_deprecated_and_internal_even_if_score_is_high() {
        let candidates = vec![
            c("aa-live", "us", true, false, 8, &["public"]),
            c("ab-old", "us", true, true, 99, &["public"]),
            c("ac-hidden", "us", true, false, 50, &["internal"]),
            c("ad-live", "us", true, false, 5, &["beta"]),
        ];

        assert_eq!(
            visible_candidate_ids(&candidates, "us", 10),
            vec!["aa-live", "ad-live"]
        );
    }

    #[test]
    fn requires_public_or_beta_tag_and_rejects_blocked_ids() {
        let candidates = vec![
            c("svc-good", "eu", true, false, 7, &["public"]),
            c("svc-beta", "eu", true, false, 6, &["beta"]),
            c("svc-ops", "eu", true, false, 12, &["ops"]),
            c("tmp-shadow", "eu", true, false, 30, &["public"]),
            c("svc-bad", "eu", true, false, -1, &["public"]),
        ];

        assert_eq!(
            visible_candidate_ids(&candidates, "eu", 10),
            vec!["svc-good", "svc-beta"]
        );
    }

    #[test]
    fn sorts_by_score_then_prefers_public_then_id() {
        let candidates = vec![
            c("svc-b", "ap", true, false, 10, &["beta"]),
            c("svc-a", "ap", true, false, 10, &["public"]),
            c("svc-c", "ap", true, false, 10, &["public", "beta"]),
            c("svc-d", "ap", true, false, 9, &["public"]),
        ];

        assert_eq!(
            visible_candidate_ids(&candidates, "ap", 10),
            vec!["svc-a", "svc-c", "svc-b", "svc-d"]
        );
    }

    #[test]
    fn zero_limit_and_empty_region_results_are_empty() {
        let candidates = vec![
            c("svc-a", "us", true, false, 3, &["public"]),
            c("svc-b", "eu", true, false, 4, &["beta"]),
        ];

        assert!(visible_candidate_ids(&candidates, "us", 0).is_empty());
        assert!(visible_candidate_ids(&candidates, "sa", 5).is_empty());
    }

    #[test]
    fn internal_tag_is_excluded_even_when_combined_with_public() {
        let candidates = vec![
            c("svc-safe", "us", true, false, 4, &["public"]),
            c("svc-mixed", "us", true, false, 20, &["public", "internal"]),
            c("svc-beta", "us", true, false, 3, &["beta"]),
        ];

        assert_eq!(
            visible_candidate_ids(&candidates, "us", 10),
            vec!["svc-safe", "svc-beta"]
        );
    }
}
