#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Player {
    pub name: &'static str,
    pub wins: u32,
    pub goal_diff: i32,
    pub goals_for: u32,
}

pub fn ranked_names(players: &[Player]) -> Vec<&'static str> {
    let mut items = players.to_vec();
    items.sort_by(|a, b| {
        a.wins
            .cmp(&b.wins)
            .then(a.goal_diff.cmp(&b.goal_diff))
            .then(a.goals_for.cmp(&b.goals_for))
            .then(a.name.cmp(&b.name))
    });
    items.into_iter().map(|p| p.name).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sorts_by_wins_then_goal_diff_then_goals_for() {
        let players = vec![
            Player { name: "Bears", wins: 4, goal_diff: 3, goals_for: 8 },
            Player { name: "Arrows", wins: 6, goal_diff: 1, goals_for: 9 },
            Player { name: "Comets", wins: 6, goal_diff: 5, goals_for: 7 },
            Player { name: "Dragons", wins: 6, goal_diff: 5, goals_for: 11 },
        ];

        assert_eq!(
            ranked_names(&players),
            vec!["Dragons", "Comets", "Arrows", "Bears"]
        );
    }

    #[test]
    fn uses_name_as_final_tiebreak_in_ascending_order() {
        let players = vec![
            Player { name: "Zephyrs", wins: 3, goal_diff: 0, goals_for: 5 },
            Player { name: "Astros", wins: 3, goal_diff: 0, goals_for: 5 },
            Player { name: "Bolts", wins: 3, goal_diff: 0, goals_for: 5 },
        ];

        assert_eq!(
            ranked_names(&players),
            vec!["Astros", "Bolts", "Zephyrs"]
        );
    }

    #[test]
    fn preserves_duplicates_in_sorted_output() {
        let players = vec![
            Player { name: "Owls", wins: 2, goal_diff: -1, goals_for: 4 },
            Player { name: "Owls", wins: 2, goal_diff: -1, goals_for: 4 },
            Player { name: "Lynx", wins: 2, goal_diff: -1, goals_for: 4 },
        ];

        assert_eq!(
            ranked_names(&players),
            vec!["Lynx", "Owls", "Owls"]
        );
    }

    #[test]
    fn handles_empty_input() {
        let players: Vec<Player> = vec![];
        assert!(ranked_names(&players).is_empty());
    }
}
