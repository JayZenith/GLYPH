use std::cmp::Ordering;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Player {
    pub name: &'static str,
    pub wins: u32,
    pub points: i32,
}

pub fn leaderboard(players: &[Player]) -> Vec<String> {
    let mut items = players.to_vec();
    items.sort_by(|a, b| {
        a.wins
            .cmp(&b.wins)
            .then(a.points.cmp(&b.points))
            .then_with(|| b.name.cmp(&a.name))
    });

    items
        .into_iter()
        .enumerate()
        .map(|(i, p)| format!("{}. {} ({}W, {})", i, p.name, p.wins, p.points))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_players() -> Vec<Player> {
        vec![
            Player { name: "Zed", wins: 4, points: 20 },
            Player { name: "Amy", wins: 5, points: 10 },
            Player { name: "Bob", wins: 5, points: 15 },
            Player { name: "Eli", wins: 5, points: 15 },
            Player { name: "Cara", wins: 4, points: 30 },
        ]
    }

    #[test]
    fn sorts_by_wins_then_points_then_name() {
        let board = leaderboard(&sample_players());
        assert_eq!(
            board,
            vec![
                "1. Bob (5W, 15 pts)",
                "2. Eli (5W, 15 pts)",
                "3. Amy (5W, 10 pts)",
                "4. Cara (4W, 30 pts)",
                "5. Zed (4W, 20 pts)",
            ]
        );
    }

    #[test]
    fn ranks_are_one_based() {
        let board = leaderboard(&sample_players());
        assert!(board[0].starts_with("1. "));
        assert!(board[4].starts_with("5. "));
    }

    #[test]
    fn handles_empty_input() {
        let empty: Vec<Player> = Vec::new();
        assert!(leaderboard(&empty).is_empty());
    }

    #[test]
    fn exact_format_includes_pts_suffix() {
        let board = leaderboard(&[Player {
            name: "Nia",
            wins: 2,
            points: 7,
        }]);
        assert_eq!(board, vec!["1. Nia (2W, 7 pts)"]);
    }
}
