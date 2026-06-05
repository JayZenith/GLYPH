use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub rank: usize,
    pub name: String,
    pub score: i32,
    pub solved: u32,
    pub penalty: u32,
}

#[derive(Debug, Clone)]
pub struct Attempt<'a> {
    pub name: &'a str,
    pub score: i32,
    pub solved: u32,
    pub penalty: u32,
}

pub fn leaderboard(attempts: &[Attempt<'_>]) -> Vec<Entry> {
    let mut by_name: HashMap<String, (i32, u32, u32)> = HashMap::new();

    for a in attempts {
        by_name.insert(a.name.to_string(), (a.score, a.solved, a.penalty));
    }

    let mut rows: Vec<Entry> = by_name
        .into_iter()
        .map(|(name, (score, solved, penalty))| Entry {
            rank: 0,
            name,
            score,
            solved,
            penalty,
        })
        .collect();

    rows.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then_with(|| a.name.cmp(&b.name))
    });

    for (idx, row) in rows.iter_mut().enumerate() {
        row.rank = idx + 1;
    }

    rows
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(rows: &[Entry]) -> Vec<&str> {
        rows.iter().map(|e| e.name.as_str()).collect()
    }

    fn ranks(rows: &[Entry]) -> Vec<usize> {
        rows.iter().map(|e| e.rank).collect()
    }

    #[test]
    fn merges_duplicates_by_best_score_then_dense_ranks() {
        let rows = leaderboard(&[
            Attempt { name: "ivy", score: 120, solved: 4, penalty: 90 },
            Attempt { name: "max", score: 130, solved: 3, penalty: 200 },
            Attempt { name: "ivy", score: 150, solved: 5, penalty: 80 },
            Attempt { name: "zoe", score: 150, solved: 4, penalty: 70 },
        ]);

        assert_eq!(names(&rows), vec!["ivy", "zoe", "max"]);
        assert_eq!(ranks(&rows), vec![1, 2, 3]);
        assert_eq!(rows[0].score, 150);
        assert_eq!(rows[0].solved, 5);
        assert_eq!(rows[0].penalty, 80);
    }

    #[test]
    fn solved_breaks_score_ties_before_name() {
        let rows = leaderboard(&[
            Attempt { name: "beta", score: 100, solved: 4, penalty: 80 },
            Attempt { name: "alpha", score: 100, solved: 5, penalty: 300 },
            Attempt { name: "gamma", score: 90, solved: 9, penalty: 1 },
        ]);

        assert_eq!(names(&rows), vec!["alpha", "beta", "gamma"]);
        assert_eq!(ranks(&rows), vec![1, 2, 3]);
    }

    #[test]
    fn lower_penalty_breaks_remaining_ties() {
        let rows = leaderboard(&[
            Attempt { name: "nina", score: 200, solved: 6, penalty: 40 },
            Attempt { name: "omar", score: 200, solved: 6, penalty: 25 },
            Attempt { name: "pia", score: 180, solved: 7, penalty: 5 },
        ]);

        assert_eq!(names(&rows), vec!["omar", "nina", "pia"]);
        assert_eq!(ranks(&rows), vec![1, 2, 3]);
    }

    #[test]
    fn name_is_final_tie_break_and_is_case_insensitive() {
        let rows = leaderboard(&[
            Attempt { name: "zoe", score: 70, solved: 2, penalty: 10 },
            Attempt { name: "AL", score: 70, solved: 2, penalty: 10 },
            Attempt { name: "bob", score: 70, solved: 2, penalty: 10 },
        ]);

        assert_eq!(names(&rows), vec!["AL", "bob", "zoe"]);
        assert_eq!(ranks(&rows), vec![1, 1, 1]);
    }

    #[test]
    fn duplicate_merge_prefers_more_solved_then_lower_penalty_for_same_score() {
        let rows = leaderboard(&[
            Attempt { name: "rhea", score: 160, solved: 4, penalty: 90 },
            Attempt { name: "rhea", score: 160, solved: 6, penalty: 140 },
            Attempt { name: "rhea", score: 160, solved: 6, penalty: 110 },
            Attempt { name: "tess", score: 150, solved: 8, penalty: 10 },
        ]);

        assert_eq!(rows[0].name, "rhea");
        assert_eq!(rows[0].score, 160);
        assert_eq!(rows[0].solved, 6);
        assert_eq!(rows[0].penalty, 110);
    }

    #[test]
    fn dense_rank_uses_all_three_competitive_fields() {
        let rows = leaderboard(&[
            Attempt { name: "ann", score: 300, solved: 7, penalty: 50 },
            Attempt { name: "bea", score: 300, solved: 7, penalty: 50 },
            Attempt { name: "cy", score: 300, solved: 7, penalty: 60 },
            Attempt { name: "dan", score: 300, solved: 6, penalty: 10 },
            Attempt { name: "eli", score: 250, solved: 9, penalty: 1 },
        ]);

        assert_eq!(names(&rows), vec!["ann", "bea", "cy", "dan", "eli"]);
        assert_eq!(ranks(&rows), vec![1, 1, 2, 3, 4]);
    }
}
