#[derive(Clone, Debug)]
pub struct Task {
    pub id: u32,
    pub title: &'static str,
    pub priority: u8,
    pub due_in_days: Option<i32>,
    pub archived: bool,
    pub blocked: bool,
    pub starred: bool,
}

pub fn visible_task_titles(tasks: &[Task], include_blocked: bool, limit: usize) -> Vec<String> {
    let mut items: Vec<&Task> = tasks
        .iter()
        .filter(|t| !t.archived)
        .filter(|t| include_blocked || !t.blocked)
        .filter(|t| t.priority >= 2 || t.starred)
        .collect();

    items.sort_by_key(|t| (t.priority, t.due_in_days.unwrap_or(i32::MAX), t.id));

    items
        .into_iter()
        .take(limit)
        .map(|t| t.title.to_string())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_tasks() -> Vec<Task> {
        vec![
            Task { id: 1, title: "alpha", priority: 3, due_in_days: Some(3), archived: false, blocked: false, starred: false },
            Task { id: 2, title: "beta", priority: 1, due_in_days: Some(1), archived: false, blocked: false, starred: true },
            Task { id: 3, title: "gamma", priority: 5, due_in_days: None, archived: false, blocked: false, starred: false },
            Task { id: 4, title: "delta", priority: 4, due_in_days: Some(-1), archived: false, blocked: false, starred: false },
            Task { id: 5, title: "epsilon", priority: 4, due_in_days: Some(1), archived: true, blocked: false, starred: false },
            Task { id: 6, title: "zeta", priority: 2, due_in_days: Some(0), archived: false, blocked: true, starred: false },
            Task { id: 7, title: "eta", priority: 2, due_in_days: None, archived: false, blocked: false, starred: false },
            Task { id: 8, title: "beta", priority: 4, due_in_days: Some(2), archived: false, blocked: false, starred: false },
            Task { id: 9, title: "theta", priority: 4, due_in_days: Some(2), archived: false, blocked: true, starred: true },
            Task { id: 10, title: "iota", priority: 2, due_in_days: Some(-2), archived: false, blocked: false, starred: false },
            Task { id: 11, title: "kappa", priority: 1, due_in_days: Some(4), archived: false, blocked: false, starred: false },
            Task { id: 12, title: "lambda", priority: 3, due_in_days: Some(0), archived: false, blocked: false, starred: false },
        ]
    }

    #[test]
    fn excludes_archived_and_blocked_by_default_and_orders_by_due_then_priority() {
        let got = visible_task_titles(&sample_tasks(), false, 10);
        assert_eq!(got, vec!["iota", "lambda", "beta", "alpha", "gamma", "eta"]);
    }

    #[test]
    fn includes_blocked_when_requested_and_keeps_overdue_items_out() {
        let got = visible_task_titles(&sample_tasks(), true, 10);
        assert_eq!(got, vec!["zeta", "lambda", "beta", "theta", "alpha", "gamma", "eta"]);
    }

    #[test]
    fn removes_duplicate_titles_after_sorting_and_applies_limit() {
        let got = visible_task_titles(&sample_tasks(), false, 4);
        assert_eq!(got, vec!["iota", "lambda", "beta", "alpha"]);
    }

    #[test]
    fn ignores_low_priority_unstarred_items_even_if_due_soon() {
        let got = visible_task_titles(&sample_tasks(), false, 20);
        assert!(!got.iter().any(|t| t == "kappa"));
    }
}
