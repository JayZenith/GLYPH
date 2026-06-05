#[derive(Clone, Debug)]
pub struct Task<'a> {
    pub id: u32,
    pub title: &'a str,
    pub done: bool,
    pub archived: bool,
    pub blocked_by: Option<u32>,
    pub priority: u8,
    pub estimate: Option<u32>,
    pub tags: &'a [&'a str],
}

pub fn select_visible_tasks(tasks: &[Task<'_>], blocked: bool, limit: usize) -> Vec<String> {
    let mut rows: Vec<(u8, u32, String)> = tasks
        .iter()
        .filter(|t| !t.done)
        .filter(|t| blocked || t.blocked_by.is_none())
        .map(|t| {
            let mut label = format!("#{} {}", t.id, t.title);
            if t.priority >= 3 {
                label.push_str(" !");
            }
            (t.priority, t.id, label)
        })
        .collect();

    rows.sort_by_key(|(priority, id, _)| (*priority, *id));
    rows.into_iter().take(limit).map(|(_, _, s)| s).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_tasks<'a>() -> Vec<Task<'a>> {
        vec![
            Task { id: 10, title: "ship", done: false, archived: false, blocked_by: None, estimate: Some(2), priority: 4, tags: &["work"] },
            Task { id: 11, title: "draft", done: false, archived: false, blocked_by: Some(10), estimate: Some(1), priority: 5, tags: &["work", "focus"] },
            Task { id: 12, title: "sweep", done: true, archived: false, blocked_by: None, estimate: Some(1), priority: 2, tags: &["home"] },
            Task { id: 13, title: "archive-me", done: false, archived: true, blocked_by: None, estimate: Some(1), priority: 5, tags: &["work"] },
            Task { id: 14, title: "someday", done: false, archived: false, blocked_by: None, estimate: None, priority: 5, tags: &["idea"] },
            Task { id: 15, title: "deep", done: false, archived: false, blocked_by: None, estimate: Some(4), priority: 5, tags: &["focus"] },
            Task { id: 16, title: "quick", done: false, archived: false, blocked_by: None, estimate: Some(1), priority: 5, tags: &["ops"] },
            Task { id: 17, title: "tiny", done: false, archived: false, blocked_by: Some(99), estimate: Some(0), priority: 5, tags: &["focus"] },
            Task { id: 18, title: "glue", done: false, archived: false, blocked_by: None, estimate: Some(2), priority: 4, tags: &["ops", "focus"] },
        ]
    }

    #[test]
    fn excludes_done_archived_and_missing_estimate() {
        let got = select_visible_tasks(&sample_tasks(), false, 10);
        let ids: Vec<u32> = got
            .iter()
            .map(|s| s[1..].split(' ').next().unwrap().parse::<u32>().unwrap())
            .collect();
        assert!(!ids.contains(&12), "done tasks must be excluded");
        assert!(!ids.contains(&13), "archived tasks must be excluded");
        assert!(!ids.contains(&14), "tasks without estimate must be excluded");
    }

    #[test]
    fn blocked_mode_only_keeps_blocked_focus_tasks() {
        let got = select_visible_tasks(&sample_tasks(), true, 10);
        assert_eq!(got, vec!["#17 tiny [0] !".to_string(), "#11 draft [1] !".to_string()]);
    }

    #[test]
    fn unblocked_mode_orders_by_priority_then_estimate_then_id() {
        let got = select_visible_tasks(&sample_tasks(), false, 10);
        assert_eq!(
            got,
            vec![
                "#16 quick [1] !".to_string(),
                "#15 deep [4] !".to_string(),
                "#18 glue [2]".to_string(),
                "#10 ship [2]".to_string(),
            ]
        );
    }

    #[test]
    fn limit_is_applied_after_filtering_and_sorting() {
        let got = select_visible_tasks(&sample_tasks(), false, 2);
        assert_eq!(got, vec!["#16 quick [1] !".to_string(), "#15 deep [4] !".to_string()]);
    }

    #[test]
    fn label_marks_only_priority_five_focus_items() {
        let got = select_visible_tasks(&sample_tasks(), false, 10);
        assert!(got.contains(&"#15 deep [4] !".to_string()));
        assert!(!got.contains(&"#10 ship [2] !".to_string()));
        assert!(!got.contains(&"#18 glue [2] !".to_string()));
    }

    #[test]
    fn zero_limit_returns_empty() {
        let got = select_visible_tasks(&sample_tasks(), false, 0);
        assert!(got.is_empty());
    }
}
