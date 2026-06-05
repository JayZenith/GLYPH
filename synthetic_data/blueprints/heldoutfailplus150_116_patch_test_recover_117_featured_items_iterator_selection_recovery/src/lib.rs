#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Item<'a> {
    pub id: &'a str,
    pub active: bool,
    pub archived: bool,
    pub hidden: bool,
    pub score: i32,
    pub tags: &'a [&'a str],
}

pub fn featured_ids(items: &[Item<'_>], tag: &str, limit: usize) -> Vec<String> {
    let mut out: Vec<String> = items
        .iter()
        .filter(|item| item.active)
        .filter(|item| !item.archived)
        .filter(|item| item.tags.iter().any(|t| *t == tag))
        .map(|item| item.id.to_string())
        .collect();

    out.sort();
    out.truncate(limit);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_items<'a>() -> Vec<Item<'a>> {
        vec![
            Item { id: "alpha", active: true, archived: false, hidden: false, score: 10, tags: &["rust", "cli"] },
            Item { id: "beta", active: true, archived: false, hidden: false, score: 15, tags: &["rust"] },
            Item { id: "gamma", active: true, archived: false, hidden: true, score: 50, tags: &["rust", "ops"] },
            Item { id: "delta", active: false, archived: false, hidden: false, score: 40, tags: &["rust"] },
            Item { id: "epsilon", active: true, archived: true, hidden: false, score: 60, tags: &["rust"] },
            Item { id: "zeta", active: true, archived: false, hidden: false, score: 0, tags: &["rust", "db"] },
            Item { id: "dup", active: true, archived: false, hidden: false, score: 7, tags: &["rust"] },
            Item { id: "dup", active: true, archived: false, hidden: false, score: 19, tags: &["rust", "cli"] },
            Item { id: "tiny", active: true, archived: false, hidden: false, score: -2, tags: &["rust"] },
            Item { id: "omega", active: true, archived: false, hidden: false, score: 15, tags: &["cli"] },
        ]
    }

    #[test]
    fn excludes_hidden_inactive_archived_and_non_positive_scores() {
        let ids = featured_ids(&sample_items(), "rust", 10);
        assert_eq!(ids, vec!["beta", "dup", "alpha"]);
    }

    #[test]
    fn sorts_by_score_desc_then_id_asc() {
        let items = vec![
            Item { id: "bbb", active: true, archived: false, hidden: false, score: 8, tags: &["rust"] },
            Item { id: "aaa", active: true, archived: false, hidden: false, score: 8, tags: &["rust"] },
            Item { id: "ccc", active: true, archived: false, hidden: false, score: 12, tags: &["rust"] },
        ];
        let ids = featured_ids(&items, "rust", 10);
        assert_eq!(ids, vec!["ccc", "aaa", "bbb"]);
    }

    #[test]
    fn deduplicates_by_id_keeping_best_scored_match() {
        let ids = featured_ids(&sample_items(), "rust", 10);
        assert_eq!(ids.iter().filter(|id| id.as_str() == "dup").count(), 1);
        assert_eq!(ids[1], "dup");
    }

    #[test]
    fn limit_is_applied_after_sorting_and_dedup() {
        let ids = featured_ids(&sample_items(), "rust", 2);
        assert_eq!(ids, vec!["beta", "dup"]);
    }

    #[test]
    fn empty_tag_matches_nothing() {
        let ids = featured_ids(&sample_items(), "", 10);
        assert!(ids.is_empty());
    }
}
