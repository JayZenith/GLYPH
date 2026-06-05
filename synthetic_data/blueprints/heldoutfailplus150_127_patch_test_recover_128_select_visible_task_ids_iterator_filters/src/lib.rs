#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Task {
    pub id: &'static str,
    pub owner: &'static str,
    pub archived: bool,
    pub blocked: bool,
    pub priority: u8,
    pub score: i32,
    pub tags: &'static [&'static str],
}

pub fn select_visible_task_ids(tasks: &[Task], owner: &str, limit: usize) -> Vec<&'static str> {
    let mut rows: Vec<&Task> = tasks
        .iter()
        .filter(|t| t.owner == owner)
        .filter(|t| !t.archived)
        .filter(|t| t.score >= 0)
        .collect();

    rows.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.id.cmp(b.id)));

    rows.into_iter().take(limit).map(|t| t.id).collect()
}

#[cfg(test)]
mod tests {
    use super::{select_visible_task_ids, Task};

    #[test]
    fn skips_archived_blocked_low_priority_and_system_tag() {
        let tasks = vec![
            Task { id: "ok-high", owner: "ann", archived: false, blocked: false, priority: 3, score: 8, tags: &["client"] },
            Task { id: "archived", owner: "ann", archived: true, blocked: false, priority: 5, score: 99, tags: &["client"] },
            Task { id: "blocked", owner: "ann", archived: false, blocked: true, priority: 5, score: 50, tags: &["client"] },
            Task { id: "low-pri", owner: "ann", archived: false, blocked: false, priority: 1, score: 40, tags: &["client"] },
            Task { id: "system", owner: "ann", archived: false, blocked: false, priority: 4, score: 35, tags: &["system"] },
            Task { id: "other-owner", owner: "bob", archived: false, blocked: false, priority: 5, score: 70, tags: &["client"] },
        ];

        assert_eq!(select_visible_task_ids(&tasks, "ann", 10), vec!["ok-high"]);
    }

    #[test]
    fn excludes_negative_score_and_empty_ids_and_sorts_by_score_priority_then_id() {
        let tasks = vec![
            Task { id: "", owner: "ann", archived: false, blocked: false, priority: 5, score: 100, tags: &["client"] },
            Task { id: "neg", owner: "ann", archived: false, blocked: false, priority: 5, score: -1, tags: &["client"] },
            Task { id: "beta", owner: "ann", archived: false, blocked: false, priority: 2, score: 10, tags: &["client"] },
            Task { id: "alpha", owner: "ann", archived: false, blocked: false, priority: 3, score: 10, tags: &["client"] },
            Task { id: "gamma", owner: "ann", archived: false, blocked: false, priority: 3, score: 10, tags: &["client"] },
        ];

        assert_eq!(select_visible_task_ids(&tasks, "ann", 10), vec!["alpha", "gamma", "beta"]);
    }

    #[test]
    fn deduplicates_by_id_keeping_best_visible_variant() {
        let tasks = vec![
            Task { id: "dup", owner: "ann", archived: false, blocked: false, priority: 2, score: 5, tags: &["client"] },
            Task { id: "dup", owner: "ann", archived: false, blocked: false, priority: 4, score: 5, tags: &["client"] },
            Task { id: "dup", owner: "ann", archived: false, blocked: false, priority: 4, score: 8, tags: &["client"] },
            Task { id: "solo", owner: "ann", archived: false, blocked: false, priority: 3, score: 7, tags: &["client"] },
        ];

        assert_eq!(select_visible_task_ids(&tasks, "ann", 10), vec!["dup", "solo"]);
    }

    #[test]
    fn applies_limit_after_filtering_sorting_and_dedup() {
        let tasks = vec![
            Task { id: "t1", owner: "ann", archived: false, blocked: false, priority: 2, score: 15, tags: &["client"] },
            Task { id: "t2", owner: "ann", archived: false, blocked: false, priority: 4, score: 15, tags: &["client"] },
            Task { id: "t2", owner: "ann", archived: false, blocked: false, priority: 1, score: 99, tags: &["client"] },
            Task { id: "t3", owner: "ann", archived: false, blocked: false, priority: 5, score: 14, tags: &["client"] },
            Task { id: "t4", owner: "ann", archived: false, blocked: false, priority: 4, score: 15, tags: &["system"] },
            Task { id: "t5", owner: "ann", archived: false, blocked: true, priority: 5, score: 30, tags: &["client"] },
        ];

        assert_eq!(select_visible_task_ids(&tasks, "ann", 2), vec!["t2", "t1"]);
    }

    #[test]
    fn zero_limit_returns_empty() {
        let tasks = vec![
            Task { id: "x", owner: "ann", archived: false, blocked: false, priority: 4, score: 10, tags: &["client"] },
        ];

        assert!(select_visible_task_ids(&tasks, "ann", 0).is_empty());
    }
}
