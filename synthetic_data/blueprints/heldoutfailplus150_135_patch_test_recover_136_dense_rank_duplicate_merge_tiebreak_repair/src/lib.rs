use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub rank: usize,
    pub name: String,
    pub score: i32,
    pub rounds: u32,
}

pub fn leaderboard(rows: &[(&str, i32, u32)]) -> Vec<Entry> {
    let mut merged: BTreeMap<String, (i32, u32, String)> = BTreeMap::new();
    for &(name, score, rounds) in rows {
        let key = name.to_string();
        let e = merged.entry(key).or_insert((0, 0, name.to_string()));
        e.0 += score;
        e.1 += rounds;
    }

    let mut items: Vec<(String, i32, u32)> = merged
        .into_iter()
        .map(|(_, (score, rounds, display))| (display, score, rounds))
        .collect();

    items.sort_by(|a, b| {
        b.1.cmp(&a.1)
            .then_with(|| a.0.cmp(&b.0))
    });

    let mut out = Vec::new();
    for (idx, (name, score, rounds)) in items.into_iter().enumerate() {
        out.push(Entry {
            rank: idx + 1,
            name,
            score,
            rounds,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(xs: &[Entry]) -> Vec<&str> {
        xs.iter().map(|e| e.name.as_str()).collect()
    }

    fn ranks(xs: &[Entry]) -> Vec<usize> {
        xs.iter().map(|e| e.rank).collect()
    }

    #[test]
    fn merges_case_insensitive_duplicates_and_keeps_best_display_name() {
        let rows = [
            ("ALICE", 10, 2),
            ("alice", 8, 1),
            ("Bob", 13, 2),
            ("bob", 3, 1),
        ];
        let got = leaderboard(&rows);
        assert_eq!(got.len(), 2);
        assert_eq!(got[0], Entry { rank: 1, name: "ALICE".to_string(), score: 18, rounds: 3 });
        assert_eq!(got[1], Entry { rank: 2, name: "Bob".to_string(), score: 16, rounds: 3 });
    }

    #[test]
    fn uses_dense_ranks_for_equal_scores() {
        let rows = [
            ("Alpha", 12, 2),
            ("Bravo", 12, 3),
            ("Charlie", 9, 1),
            ("Delta", 9, 4),
            ("Echo", 5, 1),
        ];
        let got = leaderboard(&rows);
        assert_eq!(names(&got), vec!["Alpha", "Bravo", "Charlie", "Delta", "Echo"]);
        assert_eq!(ranks(&got), vec![1, 1, 2, 2, 3]);
    }

    #[test]
    fn tie_breaks_by_fewer_rounds_then_case_insensitive_name() {
        let rows = [
            ("zeta", 20, 5),
            ("Alpha", 20, 2),
            ("beta", 20, 2),
            ("Gamma", 20, 3),
        ];
        let got = leaderboard(&rows);
        assert_eq!(names(&got), vec!["Alpha", "beta", "Gamma", "zeta"]);
        assert_eq!(ranks(&got), vec![1, 1, 1, 1]);
    }

    #[test]
    fn merged_entries_participate_in_ties_using_combined_totals_and_rounds() {
        let rows = [
            ("nova", 7, 1),
            ("NOVA", 8, 2),
            ("Orion", 15, 4),
            ("pegasus", 15, 2),
            ("PEGASUS", 0, 1),
            ("Lyra", 14, 1),
        ];
        let got = leaderboard(&rows);
        assert_eq!(names(&got), vec!["nova", "pegasus", "Orion", "Lyra"]);
        assert_eq!(ranks(&got), vec![1, 1, 1, 2]);
        assert_eq!(got[0].score, 15);
        assert_eq!(got[0].rounds, 3);
        assert_eq!(got[1].score, 15);
        assert_eq!(got[1].rounds, 3);
    }
}
