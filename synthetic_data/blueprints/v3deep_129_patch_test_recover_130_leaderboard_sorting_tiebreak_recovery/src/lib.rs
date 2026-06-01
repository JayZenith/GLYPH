use std::collections::HashSet;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub user: &'static str,
    pub points: u32,
    pub solved: u32,
    pub last_submit: u32,
}

pub fn leaderboard(entries: &[Entry]) -> Vec<Entry> {
    let mut seen = HashSet::new();
    let mut out = Vec::new();

    for entry in entries {
        if seen.insert(entry.user) {
            out.push(entry.clone());
        }
    }

    out.sort_by(|a, b| {
        a.points
            .cmp(&b.points)
            .then(a.solved.cmp(&b.solved))
            .then(a.last_submit.cmp(&b.last_submit))
            .then(a.user.cmp(&b.user))
    });

    out
}

#[cfg(test)]
mod tests {
    use super::{leaderboard, Entry};

    #[test]
    fn sorts_by_points_then_solved_then_earlier_submit_then_name() {
        let items = vec![
            Entry { user: "zoe", points: 90, solved: 4, last_submit: 15 },
            Entry { user: "amy", points: 100, solved: 3, last_submit: 50 },
            Entry { user: "bob", points: 100, solved: 5, last_submit: 40 },
            Entry { user: "ada", points: 100, solved: 5, last_submit: 10 },
            Entry { user: "bea", points: 100, solved: 5, last_submit: 10 },
        ];

        let got: Vec<&str> = leaderboard(&items).iter().map(|e| e.user).collect();
        assert_eq!(got, vec!["ada", "bea", "bob", "amy", "zoe"]);
    }

    #[test]
    fn keeps_best_entry_per_user_before_sorting() {
        let items = vec![
            Entry { user: "max", points: 90, solved: 4, last_submit: 60 },
            Entry { user: "ivy", points: 80, solved: 6, last_submit: 30 },
            Entry { user: "max", points: 120, solved: 3, last_submit: 90 },
            Entry { user: "ivy", points: 80, solved: 6, last_submit: 20 },
            Entry { user: "neo", points: 120, solved: 3, last_submit: 70 },
        ];

        let got = leaderboard(&items);
        let users: Vec<&str> = got.iter().map(|e| e.user).collect();
        let points: Vec<u32> = got.iter().map(|e| e.points).collect();
        let submits: Vec<u32> = got.iter().map(|e| e.last_submit).collect();

        assert_eq!(users, vec!["neo", "max", "ivy"]);
        assert_eq!(points, vec![120, 120, 80]);
        assert_eq!(submits, vec![70, 90, 20]);
    }

    #[test]
    fn name_is_final_tiebreaker_after_numeric_fields() {
        let items = vec![
            Entry { user: "kim", points: 50, solved: 2, last_submit: 8 },
            Entry { user: "ann", points: 50, solved: 2, last_submit: 8 },
            Entry { user: "liz", points: 50, solved: 2, last_submit: 8 },
        ];

        let got: Vec<&str> = leaderboard(&items).iter().map(|e| e.user).collect();
        assert_eq!(got, vec!["ann", "kim", "liz"]);
    }
}
