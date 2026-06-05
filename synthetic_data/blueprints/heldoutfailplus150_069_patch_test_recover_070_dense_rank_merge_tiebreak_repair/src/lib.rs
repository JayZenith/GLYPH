use std::collections::HashMap;

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

pub fn leaderboard(entries: &[Entry]) -> Vec<Ranked> {
    let mut by_name: HashMap<String, Entry> = HashMap::new();
    for e in entries {
        match by_name.get_mut(&e.name) {
            Some(cur) => {
                if e.score >= cur.score {
                    *cur = e.clone();
                }
            }
            None => {
                by_name.insert(e.name.clone(), e.clone());
            }
        }
    }

    let mut rows: Vec<Entry> = by_name.into_values().collect();
    rows.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then(a.attempts.cmp(&b.attempts))
            .then(a.name.cmp(&b.name))
    });

    let mut out = Vec::new();
    for (i, row) in rows.into_iter().enumerate() {
        out.push(Ranked {
            rank: i + 1,
            name: row.name,
            score: row.score,
            attempts: row.attempts,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(rows: &[Ranked]) -> Vec<&str> {
        rows.iter().map(|r| r.name.as_str()).collect()
    }

    fn ranks(rows: &[Ranked]) -> Vec<usize> {
        rows.iter().map(|r| r.rank).collect()
    }

    #[test]
    fn merges_duplicates_and_keeps_best_score_then_fewest_attempts() {
        let rows = leaderboard(&[
            Entry { name: "ivy".into(), score: 10, attempts: 4 },
            Entry { name: "mila".into(), score: 12, attempts: 5 },
            Entry { name: "ivy".into(), score: 10, attempts: 2 },
            Entry { name: "noah".into(), score: 9, attempts: 1 },
        ]);

        assert_eq!(names(&rows), vec!["mila", "ivy", "noah"]);
        assert_eq!(rows[1].score, 10);
        assert_eq!(rows[1].attempts, 2);
    }

    #[test]
    fn dense_ranking_reuses_rank_for_equal_score_and_attempts() {
        let rows = leaderboard(&[
            Entry { name: "zoe".into(), score: 20, attempts: 1 },
            Entry { name: "adam".into(), score: 20, attempts: 1 },
            Entry { name: "bella".into(), score: 18, attempts: 2 },
            Entry { name: "cora".into(), score: 18, attempts: 2 },
            Entry { name: "dax".into(), score: 15, attempts: 1 },
        ]);

        assert_eq!(names(&rows), vec!["adam", "zoe", "bella", "cora", "dax"]);
        assert_eq!(ranks(&rows), vec![1, 1, 2, 2, 3]);
    }

    #[test]
    fn tie_breaks_use_latest_input_order_when_name_diff_but_score_and_attempts_match() {
        let rows = leaderboard(&[
            Entry { name: "lena".into(), score: 14, attempts: 3 },
            Entry { name: "omar".into(), score: 14, attempts: 3 },
            Entry { name: "pia".into(), score: 14, attempts: 3 },
            Entry { name: "q".into(), score: 10, attempts: 1 },
        ]);

        assert_eq!(names(&rows), vec!["pia", "omar", "lena", "q"]);
        assert_eq!(ranks(&rows), vec![1, 1, 1, 2]);
    }

    #[test]
    fn duplicate_names_do_not_create_extra_rank_groups() {
        let rows = leaderboard(&[
            Entry { name: "rex".into(), score: 30, attempts: 2 },
            Entry { name: "rex".into(), score: 30, attempts: 2 },
            Entry { name: "sue".into(), score: 25, attempts: 1 },
            Entry { name: "tia".into(), score: 25, attempts: 1 },
            Entry { name: "uma".into(), score: 20, attempts: 4 },
        ]);

        assert_eq!(names(&rows), vec!["rex", "tia", "sue", "uma"]);
        assert_eq!(ranks(&rows), vec![1, 2, 2, 3]);
    }
}
