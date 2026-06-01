pub struct User<'a> {
    pub id: u32,
    pub name: &'a str,
    pub active: bool,
    pub score: Option<i32>,
}

pub fn summarize_active_users(users: &[User<'_>], min_score: i32) -> Vec<String> {
    let mut rows: Vec<(i32, String)> = users
        .iter()
        .filter(|u| u.score.unwrap_or(0) >= min_score)
        .map(|u| {
            let score = u.score.unwrap_or(0);
            (score, format!("{}:{}", u.id, u.name.to_lowercase()))
        })
        .collect();

    rows.sort_by(|a, b| a.0.cmp(&b.0));
    rows.into_iter().map(|(_, s)| s).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_only_active_users_with_present_scores_meeting_threshold() {
        let users = [
            User { id: 3, name: "Cara", active: true, score: Some(9) },
            User { id: 1, name: "Able", active: false, score: Some(20) },
            User { id: 4, name: "Duke", active: true, score: None },
            User { id: 2, name: "Bert", active: true, score: Some(12) },
        ];

        assert_eq!(
            summarize_active_users(&users, 10),
            vec!["2:BERT:12"]
        );
    }

    #[test]
    fn sorts_by_score_desc_then_name_then_id() {
        let users = [
            User { id: 9, name: "zoe", active: true, score: Some(7) },
            User { id: 2, name: "amy", active: true, score: Some(10) },
            User { id: 5, name: "bob", active: true, score: Some(10) },
            User { id: 1, name: "amy", active: true, score: Some(10) },
        ];

        assert_eq!(
            summarize_active_users(&users, 5),
            vec!["1:AMY:10", "2:AMY:10", "5:BOB:10", "9:ZOE:7"]
        );
    }

    #[test]
    fn empty_when_nothing_matches() {
        let users = [
            User { id: 1, name: "A", active: false, score: Some(50) },
            User { id: 2, name: "B", active: true, score: None },
            User { id: 3, name: "C", active: true, score: Some(4) },
        ];

        let out = summarize_active_users(&users, 10);
        assert!(out.is_empty());
    }
}
