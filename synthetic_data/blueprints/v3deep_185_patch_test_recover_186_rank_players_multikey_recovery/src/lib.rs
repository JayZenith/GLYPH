#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Player {
    pub name: String,
    pub score: i32,
    pub wins: u32,
    pub losses: u32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RankedPlayer {
    pub rank: usize,
    pub name: String,
    pub score: i32,
    pub wins: u32,
    pub losses: u32,
}

pub fn rank_players(players: &[Player]) -> Vec<RankedPlayer> {
    let mut items = players.to_vec();
    items.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then(a.wins.cmp(&b.wins))
            .then(b.losses.cmp(&a.losses))
            .then(b.name.cmp(&a.name))
    });

    let mut out = Vec::new();
    for (i, p) in items.into_iter().enumerate() {
        out.push(RankedPlayer {
            rank: i + 1,
            name: p.name,
            score: p.score,
            wins: p.wins,
            losses: p.losses,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(name: &str, score: i32, wins: u32, losses: u32) -> Player {
        Player {
            name: name.to_string(),
            score,
            wins,
            losses,
        }
    }

    #[test]
    fn sorts_by_all_keys_in_order() {
        let ranked = rank_players(&[
            p("Zoe", 10, 3, 1),
            p("Amy", 10, 5, 4),
            p("Bob", 10, 5, 2),
            p("Cara", 12, 1, 9),
        ]);

        let names: Vec<_> = ranked.iter().map(|r| r.name.as_str()).collect();
        assert_eq!(names, vec!["Cara", "Bob", "Amy", "Zoe"]);

        let ranks: Vec<_> = ranked.iter().map(|r| r.rank).collect();
        assert_eq!(ranks, vec![1, 2, 3, 4]);
    }

    #[test]
    fn tied_records_share_rank_and_next_rank_skips() {
        let ranked = rank_players(&[
            p("Beta", 20, 7, 1),
            p("Alpha", 20, 7, 1),
            p("Gamma", 18, 9, 0),
            p("Delta", 18, 9, 0),
            p("Epsilon", 17, 2, 8),
        ]);

        let pairs: Vec<_> = ranked
            .iter()
            .map(|r| (r.name.as_str(), r.rank))
            .collect();
        assert_eq!(
            pairs,
            vec![
                ("Alpha", 1),
                ("Beta", 1),
                ("Delta", 3),
                ("Gamma", 3),
                ("Epsilon", 5),
            ]
        );
    }

    #[test]
    fn empty_input_returns_empty_output() {
        let ranked = rank_players(&[]);
        assert!(ranked.is_empty());
    }
}
