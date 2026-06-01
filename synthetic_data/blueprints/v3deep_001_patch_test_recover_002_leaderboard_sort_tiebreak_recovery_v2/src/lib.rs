use std::cmp::Ordering;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Player {
    pub name: &'static str,
    pub points: u32,
    pub wins: u32,
    pub losses: u32,
    pub last_active_days: u32,
}

pub fn leaderboard(players: &[Player]) -> Vec<String> {
    let mut rows = players.to_vec();
    rows.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then_with(|| a.wins.cmp(&b.wins))
            .then_with(|| a.losses.cmp(&b.losses))
            .then_with(|| a.last_active_days.cmp(&b.last_active_days))
            .then_with(|| a.name.cmp(&b.name))
    });

    rows.into_iter()
        .enumerate()
        .map(|(idx, p)| format!("{}. {} ({} pts)", idx + 1, p.name, p.points))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{leaderboard, Player};

    fn p(
        name: &'static str,
        points: u32,
        wins: u32,
        losses: u32,
        last_active_days: u32,
    ) -> Player {
        Player {
            name,
            points,
            wins,
            losses,
            last_active_days,
        }
    }

    #[test]
    fn orders_by_points_then_wins_then_fewer_losses_then_recent_then_name() {
        let players = vec![
            p("Zed", 12, 7, 2, 4),
            p("Ada", 15, 4, 5, 3),
            p("Bea", 15, 6, 4, 9),
            p("Eli", 15, 6, 4, 2),
            p("Cal", 15, 6, 3, 8),
            p("Dax", 15, 6, 3, 1),
        ];

        let got = leaderboard(&players);
        let expected = vec![
            "1. Dax (15 pts)",
            "2. Cal (15 pts)",
            "3. Eli (15 pts)",
            "4. Bea (15 pts)",
            "5. Ada (15 pts)",
            "6. Zed (12 pts)",
        ];
        assert_eq!(got, expected);
    }

    #[test]
    fn deduplicates_by_name_keeping_best_entry_before_sorting() {
        let players = vec![
            p("Mia", 10, 5, 1, 8),
            p("Noa", 11, 4, 2, 6),
            p("Mia", 14, 5, 3, 10),
            p("Noa", 11, 6, 4, 1),
            p("Oli", 11, 6, 4, 4),
        ];

        let got = leaderboard(&players);
        let expected = vec![
            "1. Mia (14 pts)",
            "2. Noa (11 pts)",
            "3. Oli (11 pts)",
        ];
        assert_eq!(got, expected);
    }

    #[test]
    fn rank_numbers_are_dense_even_after_dedup() {
        let players = vec![
            p("Ivy", 9, 3, 3, 7),
            p("Ivy", 9, 5, 1, 2),
            p("Uma", 8, 4, 3, 1),
        ];

        let got = leaderboard(&players);
        assert_eq!(got, vec!["1. Ivy (9 pts)", "2. Uma (8 pts)"]);
    }

    #[test]
    fn empty_input_returns_no_rows() {
        let got = leaderboard(&[]);
        let expected: Vec<String> = vec![];
        assert_eq!(got, expected);
    }
}
