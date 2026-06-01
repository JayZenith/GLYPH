#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Player {
    pub name: &'static str,
    pub points: u32,
    pub wins: u32,
    pub losses: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Standing {
    pub rank: usize,
    pub name: &'static str,
    pub points: u32,
    pub wins: u32,
    pub losses: u32,
}

pub fn standings(players: &[Player]) -> Vec<Standing> {
    let mut players = players.to_vec();
    players.sort_by(|a, b| a.name.cmp(b.name));

    let mut out = Vec::with_capacity(players.len());
    for (i, p) in players.into_iter().enumerate() {
        out.push(Standing {
            rank: i + 1,
            name: p.name,
            points: p.points,
            wins: p.wins,
            losses: p.losses,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn orders_by_points_then_wins_then_fewer_losses_then_name_and_shares_rank_on_full_tie() {
        let input = vec![
            Player { name: "Zed", points: 12, wins: 5, losses: 3 },
            Player { name: "Ava", points: 15, wins: 4, losses: 2 },
            Player { name: "Mia", points: 15, wins: 4, losses: 1 },
            Player { name: "Bob", points: 15, wins: 6, losses: 5 },
            Player { name: "Eli", points: 12, wins: 5, losses: 3 },
        ];

        let got = standings(&input);
        let summary: Vec<_> = got
            .into_iter()
            .map(|s| (s.rank, s.name, s.points, s.wins, s.losses))
            .collect();

        assert_eq!(
            summary,
            vec![
                (1, "Bob", 15, 6, 5),
                (2, "Mia", 15, 4, 1),
                (3, "Ava", 15, 4, 2),
                (4, "Eli", 12, 5, 3),
                (4, "Zed", 12, 5, 3),
            ]
        );
    }

    #[test]
    fn competition_ranks_skip_after_tied_group() {
        let input = vec![
            Player { name: "Nia", points: 9, wins: 3, losses: 1 },
            Player { name: "Kai", points: 9, wins: 3, losses: 1 },
            Player { name: "Omar", points: 8, wins: 4, losses: 2 },
            Player { name: "Pia", points: 7, wins: 5, losses: 0 },
        ];

        let got = standings(&input);
        let ranks: Vec<_> = got.into_iter().map(|s| (s.rank, s.name)).collect();

        assert_eq!(ranks, vec![(1, "Kai"), (1, "Nia"), (3, "Omar"), (4, "Pia")]);
    }

    #[test]
    fn empty_input_returns_empty_output() {
        let got = standings(&[]);
        assert!(got.is_empty());
    }
}
