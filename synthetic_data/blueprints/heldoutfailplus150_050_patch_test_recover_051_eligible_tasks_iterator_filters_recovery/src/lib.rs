#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Task {
    pub id: u32,
    pub title: &'static str,
    pub active: bool,
    pub archived: bool,
    pub owner: Option<&'static str>,
    pub tags: &'static [&'static str],
    pub estimate: u8,
    pub priority: u8,
}

pub fn select_task_titles(tasks: &[Task], owner: &str, limit: usize) -> Vec<&'static str> {
    let mut items: Vec<&Task> = tasks
        .iter()
        .filter(|t| t.active)
        .filter(|t| !t.archived)
        .filter(|t| t.owner == Some(owner))
        .filter(|t| t.estimate <= 8)
        .collect();

    items.sort_by_key(|t| t.priority);

    items
        .into_iter()
        .take(limit)
        .map(|t| t.title)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_tasks() -> Vec<Task> {
        vec![
            Task { id: 1, title: "Alpha", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 3, priority: 2 },
            Task { id: 2, title: "Beta", active: true, archived: false, owner: Some("sam"), tags: &["wip"], estimate: 2, priority: 0 },
            Task { id: 3, title: "Gamma", active: true, archived: false, owner: Some("sam"), tags: &["core", "urgent"], estimate: 5, priority: 0 },
            Task { id: 4, title: "Delta", active: true, archived: false, owner: Some("sam"), tags: &["blocked"], estimate: 1, priority: 0 },
            Task { id: 5, title: "Epsilon", active: false, archived: false, owner: Some("sam"), tags: &["core"], estimate: 1, priority: 0 },
            Task { id: 6, title: "Zeta", active: true, archived: true, owner: Some("sam"), tags: &["core"], estimate: 1, priority: 0 },
            Task { id: 7, title: "Eta", active: true, archived: false, owner: Some("lee"), tags: &["core"], estimate: 1, priority: 0 },
            Task { id: 8, title: "Theta", active: true, archived: false, owner: None, tags: &["core"], estimate: 1, priority: 0 },
            Task { id: 9, title: "Iota", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 8, priority: 3 },
            Task { id: 10, title: "Kappa", active: true, archived: false, owner: Some("sam"), tags: &["urgent"], estimate: 0, priority: 1 },
            Task { id: 11, title: "Lambda", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 13, priority: 0 },
            Task { id: 12, title: "Mu", active: true, archived: false, owner: Some("sam"), tags: &["maintenance"], estimate: 2, priority: 1 },
            Task { id: 13, title: "Nu", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 2, priority: 1 },
            Task { id: 14, title: "Xi", active: true, archived: false, owner: Some("sam"), tags: &["core", "wip"], estimate: 1, priority: 1 },
        ]
    }

    #[test]
    fn excludes_disallowed_tags_and_zero_estimate() {
        let got = select_task_titles(&sample_tasks(), "sam", 10);
        assert_eq!(got, vec!["Gamma", "Nu", "Alpha", "Iota"]);
    }

    #[test]
    fn respects_limit_after_filtering_and_sorting() {
        let got = select_task_titles(&sample_tasks(), "sam", 2);
        assert_eq!(got, vec!["Gamma", "Nu"]);
    }

    #[test]
    fn sorts_by_priority_then_estimate_then_title_then_id() {
        let tasks = vec![
            Task { id: 21, title: "Zulu", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 3, priority: 1 },
            Task { id: 20, title: "Able", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 3, priority: 1 },
            Task { id: 19, title: "Baker", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 1, priority: 1 },
            Task { id: 18, title: "Charlie", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 1, priority: 0 },
        ];
        let got = select_task_titles(&tasks, "sam", 10);
        assert_eq!(got, vec!["Charlie", "Baker", "Able", "Zulu"]);
    }

    #[test]
    fn owner_match_is_case_insensitive() {
        let tasks = vec![
            Task { id: 31, title: "One", active: true, archived: false, owner: Some("Sam"), tags: &["core"], estimate: 2, priority: 0 },
            Task { id: 32, title: "Two", active: true, archived: false, owner: Some("SAM"), tags: &["core"], estimate: 1, priority: 0 },
            Task { id: 33, title: "Three", active: true, archived: false, owner: Some("sAm"), tags: &["core"], estimate: 3, priority: 0 },
        ];
        let got = select_task_titles(&tasks, "sam", 10);
        assert_eq!(got, vec!["Two", "One", "Three"]);
    }

    #[test]
    fn urgent_requires_small_estimate() {
        let tasks = vec![
            Task { id: 41, title: "QuickFix", active: true, archived: false, owner: Some("sam"), tags: &["urgent"], estimate: 4, priority: 0 },
            Task { id: 42, title: "BigFire", active: true, archived: false, owner: Some("sam"), tags: &["urgent"], estimate: 5, priority: 0 },
            Task { id: 43, title: "Routine", active: true, archived: false, owner: Some("sam"), tags: &["core"], estimate: 5, priority: 0 },
        ];
        let got = select_task_titles(&tasks, "sam", 10);
        assert_eq!(got, vec!["QuickFix", "Routine"]);
    }

    #[test]
    fn empty_limit_returns_empty_even_with_matches() {
        let got = select_task_titles(&sample_tasks(), "sam", 0);
        assert!(got.is_empty());
    }
}
