#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Task {
    pub id: u32,
    pub title: &'static str,
    pub archived: bool,
    pub score: i32,
    pub tags: &'static [&'static str],
}

pub fn select_visible_tasks(tasks: &[Task], blocked: &[u32], required_tag: Option<&str>) -> Vec<String> {
    let mut items: Vec<(i32, u32, String)> = tasks
        .iter()
        .filter(|task| !task.archived)
        .filter(|task| !blocked.contains(&task.id))
        .filter(|task| required_tag.map_or(true, |tag| task.tags.contains(&tag)))
        .map(|task| (task.score, task.id, format!("{}:{}", task.id, task.title)))
        .collect();

    items.sort_by_key(|(score, _, _)| *score);
    items.into_iter().map(|(_, _, label)| label).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_tasks() -> Vec<Task> {
        vec![
            Task { id: 7, title: "alpha", archived: false, score: 10, tags: &["ops", "urgent"] },
            Task { id: 4, title: "beta", archived: false, score: 10, tags: &["ops"] },
            Task { id: 8, title: "gamma", archived: false, score: 5, tags: &["ops"] },
            Task { id: 3, title: "delta", archived: true, score: 50, tags: &["ops", "urgent"] },
            Task { id: 5, title: "epsilon", archived: false, score: 12, tags: &[] },
            Task { id: 9, title: "zeta", archived: false, score: 12, tags: &["ops", "hold"] },
            Task { id: 11, title: "eta", archived: false, score: 7, tags: &["hold"] },
            Task { id: 12, title: "theta", archived: false, score: 7, tags: &["ops", "hold"] },
        ]
    }

    #[test]
    fn sorts_by_score_desc_then_id_asc() {
        let got = select_visible_tasks(&sample_tasks(), &[], None);
        assert_eq!(
            got,
            vec![
                "9:zeta",
                "5:epsilon",
                "4:beta",
                "7:alpha",
                "12:theta",
                "11:eta",
                "8:gamma",
            ]
        );
    }

    #[test]
    fn respects_required_tag() {
        let got = select_visible_tasks(&sample_tasks(), &[], Some("urgent"));
        assert_eq!(got, vec!["7:alpha"]);
    }

    #[test]
    fn excludes_hold_items_unless_urgent() {
        let got = select_visible_tasks(&sample_tasks(), &[], Some("ops"));
        assert_eq!(got, vec!["4:beta", "7:alpha", "8:gamma"]);
    }

    #[test]
    fn removes_non_positive_scores() {
        let tasks = vec![
            Task { id: 1, title: "keep", archived: false, score: 2, tags: &["ops"] },
            Task { id: 2, title: "zero", archived: false, score: 0, tags: &["ops"] },
            Task { id: 3, title: "neg", archived: false, score: -3, tags: &["ops"] },
        ];
        let got = select_visible_tasks(&tasks, &[], None);
        assert_eq!(got, vec!["1:keep"]);
    }

    #[test]
    fn blocks_are_applied_after_filtering() {
        let got = select_visible_tasks(&sample_tasks(), &[7, 8], Some("ops"));
        assert_eq!(got, vec!["4:beta"]);
    }

    #[test]
    fn empty_required_tag_is_treated_as_no_filter() {
        let got = select_visible_tasks(&sample_tasks(), &[9], Some(""));
        assert_eq!(
            got,
            vec![
                "5:epsilon",
                "4:beta",
                "7:alpha",
                "12:theta",
                "11:eta",
                "8:gamma",
            ]
        );
    }

    #[test]
    fn omits_blank_titles() {
        let tasks = vec![
            Task { id: 1, title: "", archived: false, score: 9, tags: &["ops"] },
            Task { id: 2, title: "ok", archived: false, score: 8, tags: &["ops"] },
        ];
        let got = select_visible_tasks(&tasks, &[], None);
        assert_eq!(got, vec!["2:ok"]);
    }
}
