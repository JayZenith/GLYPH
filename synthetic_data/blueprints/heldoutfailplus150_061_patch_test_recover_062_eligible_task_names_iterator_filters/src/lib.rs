#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Task {
    pub id: u32,
    pub name: String,
    pub active: bool,
    pub archived: bool,
    pub priority: u8,
    pub score: i32,
    pub tags: Vec<String>,
}

pub fn eligible_task_names(tasks: &[Task], required_tag: &str, min_score: i32) -> Vec<String> {
    let mut picked: Vec<&Task> = tasks
        .iter()
        .filter(|t| t.active)
        .filter(|t| !t.archived)
        .filter(|t| t.score >= min_score)
        .filter(|t| t.tags.iter().any(|tag| tag == required_tag))
        .collect();

    picked.sort_by(|a, b| b.score.cmp(&a.score));

    picked.into_iter().map(|t| t.name.clone()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn task(
        id: u32,
        name: &str,
        active: bool,
        archived: bool,
        priority: u8,
        score: i32,
        tags: &[&str],
    ) -> Task {
        Task {
            id,
            name: name.to_string(),
            active,
            archived,
            priority,
            score,
            tags: tags.iter().map(|s| s.to_string()).collect(),
        }
    }

    #[test]
    fn sorts_by_score_then_priority_then_name_and_formats_output() {
        let tasks = vec![
            task(1, " Alpha ", true, false, 2, 15, &["ops"]),
            task(2, "beta", true, false, 3, 15, &["ops"]),
            task(3, "gamma", true, false, 3, 18, &["ops"]),
            task(4, "delta", true, false, 1, 15, &["ops"]),
        ];

        assert_eq!(
            eligible_task_names(&tasks, "ops", 10),
            vec!["gamma#3", "beta#2", "Alpha#1", "delta#4"]
        );
    }

    #[test]
    fn excludes_banned_and_empty_names_and_negative_priority_even_if_otherwise_matching() {
        let tasks = vec![
            task(10, "good", true, false, 1, 20, &["ops"]),
            task(11, "", true, false, 1, 50, &["ops"]),
            task(12, "   ", true, false, 1, 50, &["ops"]),
            task(13, "banned", true, false, 1, 50, &["ops"]),
            task(14, "almost", true, false, 0, 50, &["ops"]),
        ];

        assert_eq!(eligible_task_names(&tasks, "ops", 10), vec!["good#10"]);
    }

    #[test]
    fn required_tag_match_is_case_insensitive_and_ignores_duplicate_task_ids_after_sorting() {
        let tasks = vec![
            task(20, "first", true, false, 1, 14, &["OPS"]),
            task(20, "second", true, false, 3, 17, &["ops"]),
            task(21, "third", true, false, 2, 16, &["OpS"]),
            task(22, "miss", true, false, 4, 99, &["other"]),
        ];

        assert_eq!(eligible_task_names(&tasks, "ops", 10), vec!["second#20", "third#21"]);
    }

    #[test]
    fn min_score_is_strictly_greater_than_threshold() {
        let tasks = vec![
            task(30, "edge", true, false, 2, 10, &["ops"]),
            task(31, "above", true, false, 2, 11, &["ops"]),
        ];

        assert_eq!(eligible_task_names(&tasks, "ops", 10), vec!["above#31"]);
    }

    #[test]
    fn banned_tag_excludes_even_when_required_tag_is_present() {
        let tasks = vec![
            task(40, "safe", true, false, 2, 12, &["ops"]),
            task(41, "shadow", true, false, 4, 99, &["ops", "blocked"]),
            task(42, "mask", true, false, 4, 99, &["BLOCKED", "ops"]),
        ];

        assert_eq!(eligible_task_names(&tasks, "ops", 10), vec!["safe#40"]);
    }
}
