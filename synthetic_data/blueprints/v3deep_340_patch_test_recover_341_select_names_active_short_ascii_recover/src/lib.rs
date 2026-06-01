pub struct User {
    pub id: u32,
    pub name: Option<&'static str>,
    pub active: bool,
    pub score: i32,
}

pub fn selected_names(users: &[User]) -> Vec<String> {
    users
        .iter()
        .filter(|u| u.score >= 10)
        .map(|u| u.name.unwrap_or(""))
        .filter(|name| name.len() <= 8)
        .map(|name| name.to_uppercase())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_users() -> Vec<User> {
        vec![
            User { id: 1, name: Some("  anna  "), active: true, score: 12 },
            User { id: 2, name: Some("bob"), active: false, score: 18 },
            User { id: 3, name: Some("carl9"), active: true, score: 17 },
            User { id: 4, name: Some("zoe"), active: true, score: 9 },
            User { id: 5, name: None, active: true, score: 22 },
            User { id: 6, name: Some("eve-1"), active: true, score: 20 },
            User { id: 7, name: Some("maximilian"), active: true, score: 25 },
            User { id: 8, name: Some(" Li "), active: true, score: 10 },
        ]
    }

    #[test]
    fn keeps_only_active_scored_ascii_alphabetic_short_names() {
        let got = selected_names(&sample_users());
        assert_eq!(got, vec!["ANNA", "LI"]);
    }

    #[test]
    fn excludes_missing_and_non_letter_names() {
        let users = vec![
            User { id: 1, name: None, active: true, score: 50 },
            User { id: 2, name: Some("jo3"), active: true, score: 50 },
            User { id: 3, name: Some("amy!"), active: true, score: 50 },
            User { id: 4, name: Some("mila"), active: true, score: 50 },
        ];
        assert_eq!(selected_names(&users), vec!["MILA"]);
    }

    #[test]
    fn trims_before_length_check() {
        let users = vec![
            User { id: 1, name: Some("  claire "), active: true, score: 99 },
            User { id: 2, name: Some("  ruth "), active: true, score: 99 },
        ];
        assert_eq!(selected_names(&users), vec!["RUTH"]);
    }

    #[test]
    fn preserves_input_order_of_selected_names() {
        let users = vec![
            User { id: 1, name: Some("  noa"), active: true, score: 11 },
            User { id: 2, name: Some("ava"), active: true, score: 14 },
            User { id: 3, name: Some("ian7"), active: true, score: 99 },
            User { id: 4, name: Some("mia"), active: false, score: 99 },
        ];
        assert_eq!(selected_names(&users), vec!["NOA", "AVA"]);
    }
}
