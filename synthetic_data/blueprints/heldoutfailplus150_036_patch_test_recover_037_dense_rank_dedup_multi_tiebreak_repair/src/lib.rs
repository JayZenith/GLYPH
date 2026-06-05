use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub score: u32,
    pub solved: u32,
    pub penalty: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RankedEntry {
    pub rank: u32,
    pub name: String,
    pub score: u32,
    pub solved: u32,
    pub penalty: u32,
}

pub fn leaderboard(entries: &[Entry]) -> Vec<RankedEntry> {
    let mut merged: HashMap<String, Entry> = HashMap::new();
    for entry in entries {
        merged.insert(entry.name.clone(), entry.clone());
    }

    let mut rows: Vec<Entry> = merged.into_values().collect();
    rows.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then_with(|| a.name.cmp(&b.name))
    });

    let mut out = Vec::new();
    for (idx, row) in rows.into_iter().enumerate() {
        out.push(RankedEntry {
            rank: (idx as u32) + 1,
            name: row.name,
            score: row.score,
            solved: row.solved,
            penalty: row.penalty,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(name: &str, score: u32, solved: u32, penalty: u32) -> Entry {
        Entry {
            name: name.to_string(),
            score,
            solved,
            penalty,
        }
    }

    #[test]
    fn merges_duplicates_by_best_submission_before_sorting() {
        let rows = leaderboard(&[
            e("zeta", 88, 5, 150),
            e("amy", 90, 5, 200),
            e("amy", 90, 6, 180),
            e("bob", 90, 6, 210),
            e("bob", 91, 4, 400),
        ]);

        let got: Vec<_> = rows
            .into_iter()
            .map(|r| (r.rank, r.name, r.score, r.solved, r.penalty))
            .collect();

        assert_eq!(
            got,
            vec![
                (1, "bob".to_string(), 91, 4, 400),
                (2, "amy".to_string(), 90, 6, 180),
                (3, "zeta".to_string(), 88, 5, 150),
            ]
        );
    }

    #[test]
    fn sorts_by_score_then_solved_then_lower_penalty_then_name() {
        let rows = leaderboard(&[
            e("cara", 100, 4, 110),
            e("able", 100, 5, 200),
            e("baker", 100, 5, 120),
            e("delta", 100, 5, 120),
            e("echo", 100, 5, 120),
        ]);

        let got: Vec<_> = rows.into_iter().map(|r| r.name).collect();
        assert_eq!(got, vec!["baker", "delta", "echo", "able", "cara"]);
    }

    #[test]
    fn uses_dense_ranks_based_on_score_only() {
        let rows = leaderboard(&[
            e("a", 100, 2, 20),
            e("b", 100, 9, 10),
            e("c", 95, 1, 5),
            e("d", 95, 8, 3),
            e("e", 90, 7, 1),
        ]);

        let got: Vec<_> = rows.into_iter().map(|r| (r.name, r.rank)).collect();
        assert_eq!(
            got,
            vec![
                ("b".to_string(), 1),
                ("a".to_string(), 1),
                ("d".to_string(), 2),
                ("c".to_string(), 2),
                ("e".to_string(), 3),
            ]
        );
    }

    #[test]
    fn duplicate_choice_uses_full_tiebreak_not_last_seen() {
        let rows = leaderboard(&[
            e("mira", 77, 4, 90),
            e("mira", 77, 5, 130),
            e("mira", 77, 5, 120),
            e("noel", 77, 5, 120),
        ]);

        let got: Vec<_> = rows
            .into_iter()
            .map(|r| (r.rank, r.name, r.score, r.solved, r.penalty))
            .collect();

        assert_eq!(
            got,
            vec![
                (1, "mira".to_string(), 77, 5, 120),
                (1, "noel".to_string(), 77, 5, 120),
            ]
        );
    }
}
