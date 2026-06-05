#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Item<'a> {
    pub id: &'a str,
    pub active: bool,
    pub category: &'a str,
    pub score: i32,
    pub flagged: bool,
    pub blocked: bool,
}

pub fn pick_ready_items(items: &[Item<'_>], allowed_categories: &[&str], limit: usize) -> Vec<String> {
    let mut picked: Vec<&Item<'_>> = items
        .iter()
        .filter(|item| item.active)
        .filter(|item| allowed_categories.iter().any(|c| c == &item.category))
        .filter(|item| !item.blocked)
        .filter(|item| item.score >= 0)
        .collect();

    picked.sort_by(|a, b| a.score.cmp(&b.score).then_with(|| a.id.cmp(b.id)));

    picked
        .into_iter()
        .take(limit)
        .map(|item| item.id.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_items<'a>() -> Vec<Item<'a>> {
        vec![
            Item { id: "ops-7", active: true, category: "ops", score: 7, flagged: false, blocked: false },
            Item { id: "ops-urgent", active: true, category: "ops", score: 9, flagged: true, blocked: false },
            Item { id: "ops-zero", active: true, category: "ops", score: 0, flagged: false, blocked: false },
            Item { id: "ops-neg", active: true, category: "ops", score: -1, flagged: false, blocked: false },
            Item { id: "ops-blocked", active: true, category: "ops", score: 8, flagged: false, blocked: true },
            Item { id: "qa-5", active: true, category: "qa", score: 5, flagged: false, blocked: false },
            Item { id: "qa-5-flagged", active: true, category: "qa", score: 5, flagged: true, blocked: false },
            Item { id: "qa-3", active: true, category: "qa", score: 3, flagged: false, blocked: false },
            Item { id: "dev-10", active: true, category: "dev", score: 10, flagged: false, blocked: false },
            Item { id: "qa-inactive", active: false, category: "qa", score: 99, flagged: false, blocked: false },
            Item { id: "ops-7b", active: true, category: "ops", score: 7, flagged: false, blocked: false },
            Item { id: "ops-skip", active: true, category: "ops", score: 4, flagged: false, blocked: false },
        ]
    }

    #[test]
    fn excludes_flagged_and_non_positive_scores() {
        let out = pick_ready_items(&sample_items(), &["ops", "qa"], 20);
        assert_eq!(out, vec!["ops-7", "ops-7b", "qa-5"]);
    }

    #[test]
    fn sorts_by_score_desc_then_id_asc() {
        let out = pick_ready_items(&sample_items(), &["ops", "qa"], 20);
        assert_eq!(out, vec!["ops-7", "ops-7b", "qa-5"]);
    }

    #[test]
    fn excludes_skip_prefixed_ids_even_when_otherwise_valid() {
        let out = pick_ready_items(&sample_items(), &["ops", "qa"], 20);
        assert!(!out.iter().any(|id| id.ends_with("skip")));
    }

    #[test]
    fn limit_applies_after_filter_and_sort() {
        let out = pick_ready_items(&sample_items(), &["ops", "qa", "dev"], 2);
        assert_eq!(out, vec!["dev-10", "ops-7"]);
    }

    #[test]
    fn empty_allowed_categories_yields_nothing() {
        let out = pick_ready_items(&sample_items(), &[], 5);
        assert!(out.is_empty());
    }
}
