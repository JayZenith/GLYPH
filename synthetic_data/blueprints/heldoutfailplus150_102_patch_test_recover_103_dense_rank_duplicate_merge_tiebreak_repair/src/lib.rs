use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub player: &'static str,
    pub score: u32,
    pub attempts: u32,
    pub last_submission: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ranked {
    pub rank: usize,
    pub player: &'static str,
    pub score: u32,
    pub attempts: u32,
    pub last_submission: u32,
}

pub fn rank_leaderboard(entries: &[Entry]) -> Vec<Ranked> {
    let mut by_player: HashMap<&'static str, Entry> = HashMap::new();
    for entry in entries {
        by_player.insert(entry.player, entry.clone());
    }

    let mut items: Vec<Entry> = by_player.into_values().collect();
    items.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then(a.attempts.cmp(&b.attempts))
            .then(a.player.cmp(&b.player))
    });

    items
        .into_iter()
        .enumerate()
        .map(|(idx, e)| Ranked {
            rank: idx + 1,
            player: e.player,
            score: e.score,
            attempts: e.attempts,
            last_submission: e.last_submission,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names_and_ranks(rows: &[Ranked]) -> Vec<(usize, &'static str)> {
        rows.iter().map(|r| (r.rank, r.player)).collect()
    }

    #[test]
    fn merges_duplicates_by_best_score_then_tiebreaks() {
        let rows = rank_leaderboard(&[
            Entry { player: "ivy", score: 90, attempts: 2, last_submission: 40 },
            Entry { player: "ivy", score: 95, attempts: 5, last_submission: 80 },
            Entry { player: "zoe", score: 95, attempts: 4, last_submission: 70 },
            Entry { player: "amy", score: 95, attempts: 4, last_submission: 65 },
            Entry { player: "max", score: 88, attempts: 1, last_submission: 20 },
        ]);

        assert_eq!(
            names_and_ranks(&rows),
            vec![(1, "amy"), (1, "zoe"), (2, "ivy"), (3, "max")]
        );
        assert_eq!(rows[2].score, 95);
        assert_eq!(rows[2].attempts, 5);
    }

    #[test]
    fn ties_use_last_submission_before_name() {
        let rows = rank_leaderboard(&[
            Entry { player: "mila", score: 77, attempts: 3, last_submission: 50 },
            Entry { player: "noah", score: 77, attempts: 3, last_submission: 30 },
            Entry { player: "olga", score: 77, attempts: 3, last_submission: 40 },
        ]);

        assert_eq!(
            names_and_ranks(&rows),
            vec![(1, "noah"), (1, "olga"), (1, "mila")]
        );
    }

    #[test]
    fn duplicate_same_score_keeps_fewer_attempts_then_earlier_submission() {
        let rows = rank_leaderboard(&[
            Entry { player: "rex", score: 70, attempts: 6, last_submission: 90 },
            Entry { player: "rex", score: 70, attempts: 4, last_submission: 100 },
            Entry { player: "rex", score: 70, attempts: 4, last_submission: 80 },
            Entry { player: "sue", score: 69, attempts: 1, last_submission: 10 },
        ]);

        assert_eq!(rows[0].player, "rex");
        assert_eq!(rows[0].score, 70);
        assert_eq!(rows[0].attempts, 4);
        assert_eq!(rows[0].last_submission, 80);
        assert_eq!(rows[0].rank, 1);
        assert_eq!(rows[1].rank, 2);
    }

    #[test]
    fn dense_ranks_do_not_skip_numbers_after_ties() {
        let rows = rank_leaderboard(&[
            Entry { player: "ann", score: 100, attempts: 2, last_submission: 20 },
            Entry { player: "bob", score: 100, attempts: 2, last_submission: 25 },
            Entry { player: "cam", score: 100, attempts: 5, last_submission: 10 },
            Entry { player: "dan", score: 95, attempts: 1, last_submission: 5 },
            Entry { player: "eve", score: 95, attempts: 3, last_submission: 4 },
            Entry { player: "fay", score: 80, attempts: 1, last_submission: 1 },
        ]);

        assert_eq!(
            names_and_ranks(&rows),
            vec![(1, "ann"), (1, "bob"), (2, "cam"), (3, "dan"), (4, "eve"), (5, "fay")]
        );
    }
}
