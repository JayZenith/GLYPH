use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub score: u32,
    pub penalties: u32,
    pub solved: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ranked {
    pub rank: usize,
    pub name: String,
    pub score: u32,
    pub penalties: u32,
    pub solved: u32,
}

pub fn rank_entries(entries: &[Entry]) -> Vec<Ranked> {
    let mut merged: BTreeMap<String, Entry> = BTreeMap::new();
    for e in entries {
        merged
            .entry(e.name.clone())
            .and_modify(|cur| {
                cur.score += e.score;
                cur.penalties += e.penalties;
                cur.solved += e.solved;
            })
            .or_insert_with(|| e.clone());
    }

    let mut items: Vec<Entry> = merged.into_values().collect();
    items.sort_by(|a, b| b.score.cmp(&a.score).then_with(|| a.name.cmp(&b.name)));

    let mut out = Vec::new();
    let mut last_score = None;
    let mut rank = 0;
    for (idx, e) in items.into_iter().enumerate() {
        if last_score != Some(e.score) {
            rank = idx + 1;
            last_score = Some(e.score);
        }
        out.push(Ranked {
            rank,
            name: e.name,
            score: e.score,
            penalties: e.penalties,
            solved: e.solved,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(name: &str, score: u32, penalties: u32, solved: u32) -> Entry {
        Entry {
            name: name.to_string(),
            score,
            penalties,
            solved,
        }
    }

    #[test]
    fn merges_duplicates_by_name_using_best_seen_values() {
        let rows = vec![
            e("mira", 80, 20, 3),
            e("zoe", 70, 10, 4),
            e("mira", 90, 15, 5),
            e("zoe", 70, 8, 6),
            e("kai", 90, 30, 2),
        ];
        let got = rank_entries(&rows);
        let names: Vec<_> = got.iter().map(|r| r.name.as_str()).collect();
        assert_eq!(names, vec!["mira", "kai", "zoe"]);

        let mira = got.iter().find(|r| r.name == "mira").unwrap();
        assert_eq!((mira.score, mira.penalties, mira.solved), (90, 15, 5));

        let zoe = got.iter().find(|r| r.name == "zoe").unwrap();
        assert_eq!((zoe.score, zoe.penalties, zoe.solved), (70, 8, 6));
    }

    #[test]
    fn sorts_by_score_then_lower_penalties_then_higher_solved_then_name() {
        let rows = vec![
            e("zeta", 100, 20, 3),
            e("beta", 100, 10, 1),
            e("alfa", 100, 10, 4),
            e("delta", 100, 10, 4),
            e("omega", 95, 1, 9),
        ];
        let got = rank_entries(&rows);
        let names: Vec<_> = got.iter().map(|r| r.name.as_str()).collect();
        assert_eq!(names, vec!["alfa", "delta", "beta", "zeta", "omega"]);
    }

    #[test]
    fn dense_ranks_use_full_tie_signature() {
        let rows = vec![
            e("amy", 100, 10, 3),
            e("bea", 100, 10, 3),
            e("cam", 100, 10, 2),
            e("dan", 95, 1, 9),
            e("eve", 95, 1, 9),
            e("flo", 95, 2, 9),
        ];
        let got = rank_entries(&rows);
        let pairs: Vec<_> = got.iter().map(|r| (r.name.as_str(), r.rank)).collect();
        assert_eq!(pairs, vec![
            ("amy", 1),
            ("bea", 1),
            ("cam", 2),
            ("dan", 3),
            ("eve", 3),
            ("flo", 4),
        ]);
    }

    #[test]
    fn duplicate_merge_can_change_final_order_after_reduction() {
        let rows = vec![
            e("nina", 88, 50, 1),
            e("omar", 88, 20, 3),
            e("nina", 88, 5, 4),
            e("pia", 88, 5, 3),
        ];
        let got = rank_entries(&rows);
        let names: Vec<_> = got.iter().map(|r| r.name.as_str()).collect();
        assert_eq!(names, vec!["nina", "pia", "omar"]);
        let ranks: Vec<_> = got.iter().map(|r| r.rank).collect();
        assert_eq!(ranks, vec![1, 2, 3]);
    }
}
