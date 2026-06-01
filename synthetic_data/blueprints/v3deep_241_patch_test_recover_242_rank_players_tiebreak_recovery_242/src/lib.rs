#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Player {
    pub name: String,
    pub score: u32,
    pub wins: u32,
    pub penalties: u32,
}

pub fn leaderboard(players: &[Player]) -> Vec<String> {
    let mut items = players.to_vec();
    items.sort_by(|a, b| {
        a.score
            .cmp(&b.score)
            .then(a.wins.cmp(&b.wins))
            .then(a.penalties.cmp(&b.penalties))
            .then(a.name.cmp(&b.name))
    });

    items
        .into_iter()
        .enumerate()
        .map(|(i, p)| format!("{}. {} (score={}, wins={}, penalties={})", i + 1, p.name, p.score, p.wins, p.penalties))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::{leaderboard, Player};

    fn p(name: &str, score: u32, wins: u32, penalties: u32) -> Player {
        Player {
            name: name.to_string(),
            score,
            wins,
            penalties,
        }
    }

    #[test]
    fn ranks_by_score_then_wins_then_lower_penalties_then_name() {
        let rows = vec![
            p("Mira", 10, 3, 2),
            p("Zane", 12, 1, 4),
            p("Ava", 12, 1, 1),
            p("Liam", 12, 2, 7),
            p("Noah", 12, 2, 3),
        ];

        assert_eq!(
            leaderboard(&rows),
            vec![
                "1. Noah (score=12, wins=2, penalties=3)",
                "2. Liam (score=12, wins=2, penalties=7)",
                "3. Ava (score=12, wins=1, penalties=1)",
                "4. Zane (score=12, wins=1, penalties=4)",
                "5. Mira (score=10, wins=3, penalties=2)",
            ]
        );
    }

    #[test]
    fn name_is_final_tiebreak_when_all_numbers_match() {
        let rows = vec![
            p("Zoe", 8, 4, 0),
            p("Ada", 8, 4, 0),
            p("Moe", 8, 4, 0),
        ];

        assert_eq!(
            leaderboard(&rows),
            vec![
                "1. Ada (score=8, wins=4, penalties=0)",
                "2. Moe (score=8, wins=4, penalties=0)",
                "3. Zoe (score=8, wins=4, penalties=0)",
            ]
        );
    }

    #[test]
    fn keeps_only_best_record_per_name_before_ranking() {
        let rows = vec![
            p("Ivy", 7, 2, 1),
            p("Ivy", 9, 1, 5),
            p("Kai", 8, 3, 2),
            p("Kai", 8, 3, 1),
            p("Bea", 9, 1, 4),
        ];

        assert_eq!(
            leaderboard(&rows),
            vec![
                "1. Bea (score=9, wins=1, penalties=4)",
                "2. Ivy (score=9, wins=1, penalties=5)",
                "3. Kai (score=8, wins=3, penalties=1)",
            ]
        );
    }
}
