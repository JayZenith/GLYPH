use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub score: i32,
    pub attempts: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ranked {
    pub rank: usize,
    pub name: String,
    pub score: i32,
    pub attempts: u32,
}

pub fn rank_entries(entries: &[Entry]) -> Vec<Ranked> {
    let mut merged: BTreeMap<String, Entry> = BTreeMap::new();
    for e in entries {
        let key = e.name.clone();
        merged
            .entry(key)
            .and_modify(|cur| {
                cur.score += e.score;
                if e.attempts < cur.attempts {
                    cur.attempts = e.attempts;
                }
            })
            .or_insert_with(|| e.clone());
    }

    let mut rows: Vec<Entry> = merged.into_values().collect();
    rows.sort_by(|a, b| b.score.cmp(&a.score));

    rows.into_iter()
        .enumerate()
        .map(|(i, e)| Ranked {
            rank: i + 1,
            name: e.name,
            score: e.score,
            attempts: e.attempts,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names_rank_score_attempts(rows: &[Ranked]) -> Vec<(usize, String, i32, u32)> {
        rows.iter()
            .map(|r| (r.rank, r.name.clone(), r.score, r.attempts))
            .collect()
    }

    #[test]
    fn merges_case_insensitive_duplicates_and_preserves_best_display_name() {
        let rows = rank_entries(&[
            Entry { name: "alice".into(), score: 10, attempts: 5 },
            Entry { name: "ALICE".into(), score: 12, attempts: 3 },
            Entry { name: "Bob".into(), score: 15, attempts: 4 },
        ]);

        assert_eq!(
            names_rank_score_attempts(&rows),
            vec![
                (1, "ALICE".into(), 22, 3),
                (2, "Bob".into(), 15, 4),
            ]
        );
    }

    #[test]
    fn uses_dense_ranking_for_equal_scores() {
        let rows = rank_entries(&[
            Entry { name: "A".into(), score: 30, attempts: 2 },
            Entry { name: "B".into(), score: 30, attempts: 4 },
            Entry { name: "C".into(), score: 25, attempts: 1 },
            Entry { name: "D".into(), score: 25, attempts: 3 },
            Entry { name: "E".into(), score: 10, attempts: 1 },
        ]);

        assert_eq!(rows.iter().map(|r| r.rank).collect::<Vec<_>>(), vec![1, 1, 2, 2, 3]);
    }

    #[test]
    fn tie_breaks_by_fewer_attempts_then_name_case_insensitively() {
        let rows = rank_entries(&[
            Entry { name: "zoe".into(), score: 50, attempts: 3 },
            Entry { name: "Amy".into(), score: 50, attempts: 1 },
            Entry { name: "bob".into(), score: 50, attempts: 1 },
            Entry { name: "Clio".into(), score: 40, attempts: 2 },
        ]);

        assert_eq!(
            rows.iter().map(|r| r.name.as_str()).collect::<Vec<_>>(),
            vec!["Amy", "bob", "zoe", "Clio"]
        );
        assert_eq!(rows[0].rank, 1);
        assert_eq!(rows[1].rank, 1);
        assert_eq!(rows[2].rank, 1);
        assert_eq!(rows[3].rank, 2);
    }

    #[test]
    fn keeps_lexicographically_smallest_display_name_among_duplicates_with_same_best_attempts() {
        let rows = rank_entries(&[
            Entry { name: "zed".into(), score: 7, attempts: 2 },
            Entry { name: "Zed".into(), score: 8, attempts: 2 },
            Entry { name: "mila".into(), score: 20, attempts: 1 },
        ]);

        assert_eq!(
            names_rank_score_attempts(&rows),
            vec![
                (1, "mila".into(), 20, 1),
                (2, "Zed".into(), 15, 2),
            ]
        );
    }
}
