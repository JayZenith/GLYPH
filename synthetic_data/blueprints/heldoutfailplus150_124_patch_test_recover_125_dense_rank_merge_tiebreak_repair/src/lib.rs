use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScoreRow {
    pub player: String,
    pub score: i32,
    pub solved: u32,
    pub penalty: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RankedRow {
    pub rank: usize,
    pub player: String,
    pub score: i32,
    pub solved: u32,
    pub penalty: u32,
}

pub fn leaderboard(rows: &[ScoreRow]) -> Vec<RankedRow> {
    let mut merged: Vec<ScoreRow> = rows.to_vec();

    merged.sort_by(|a, b| {
        b.score.cmp(&a.score)
            .then_with(|| a.player.cmp(&b.player))
    });

    merged
        .into_iter()
        .enumerate()
        .map(|(idx, row)| RankedRow {
            rank: idx + 1,
            player: row.player,
            score: row.score,
            solved: row.solved,
            penalty: row.penalty,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(player: &str, score: i32, solved: u32, penalty: u32) -> ScoreRow {
        ScoreRow {
            player: player.to_string(),
            score,
            solved,
            penalty,
        }
    }

    #[test]
    fn merges_duplicate_players_by_best_score_then_more_solved_then_lower_penalty() {
        let board = leaderboard(&[
            row("Kai", 90, 4, 30),
            row("Mira", 90, 5, 40),
            row("Kai", 90, 5, 20),
            row("Noor", 88, 6, 10),
            row("Mira", 91, 3, 99),
        ]);

        let names: Vec<_> = board.iter().map(|r| r.player.as_str()).collect();
        assert_eq!(names, vec!["Mira", "Kai", "Noor"]);

        assert_eq!(board[0].score, 91);
        assert_eq!(board[1].solved, 5);
        assert_eq!(board[1].penalty, 20);
    }

    #[test]
    fn sort_order_uses_score_then_solved_then_penalty_then_name() {
        let board = leaderboard(&[
            row("Zed", 100, 4, 10),
            row("Ana", 100, 5, 50),
            row("Bea", 100, 5, 20),
            row("Cid", 100, 5, 20),
            row("Dax", 95, 7, 5),
        ]);

        let names: Vec<_> = board.iter().map(|r| r.player.as_str()).collect();
        assert_eq!(names, vec!["Bea", "Cid", "Ana", "Zed", "Dax"]);
    }

    #[test]
    fn equal_score_solved_and_penalty_share_dense_rank() {
        let board = leaderboard(&[
            row("Bea", 100, 5, 20),
            row("Cid", 100, 5, 20),
            row("Ana", 100, 5, 50),
            row("Dax", 95, 7, 5),
            row("Eli", 95, 7, 5),
            row("Fox", 80, 1, 0),
        ]);

        let ranks: Vec<_> = board.iter().map(|r| (r.player.as_str(), r.rank)).collect();
        assert_eq!(
            ranks,
            vec![
                ("Bea", 1),
                ("Cid", 1),
                ("Ana", 2),
                ("Dax", 3),
                ("Eli", 3),
                ("Fox", 4),
            ]
        );
    }

    #[test]
    fn duplicate_merge_happens_before_ranking_and_keeps_tie_groups() {
        let board = leaderboard(&[
            row("Uma", 70, 2, 20),
            row("Uma", 70, 3, 15),
            row("Vic", 70, 3, 15),
            row("Wes", 70, 3, 10),
            row("Xia", 69, 9, 1),
        ]);

        let rows: Vec<_> = board
            .iter()
            .map(|r| (r.player.as_str(), r.rank, r.score, r.solved, r.penalty))
            .collect();

        assert_eq!(
            rows,
            vec![
                ("Wes", 1, 70, 3, 10),
                ("Uma", 2, 70, 3, 15),
                ("Vic", 2, 70, 3, 15),
                ("Xia", 3, 69, 9, 1),
            ]
        );
    }

    #[test]
    fn empty_input_returns_empty_output() {
        let board = leaderboard(&[]);
        assert!(board.is_empty());
    }
}
