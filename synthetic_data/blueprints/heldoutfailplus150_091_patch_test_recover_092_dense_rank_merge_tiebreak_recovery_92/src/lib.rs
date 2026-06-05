use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub id: &'static str,
    pub score: i32,
    pub wins: u32,
    pub penalty: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RankedEntry {
    pub rank: usize,
    pub id: &'static str,
    pub score: i32,
    pub wins: u32,
    pub penalty: u32,
}

pub fn rank_entries(entries: &[Entry]) -> Vec<RankedEntry> {
    let mut by_id: HashMap<&'static str, Entry> = HashMap::new();
    for e in entries {
        by_id.insert(e.id, e.clone());
    }

    let mut merged: Vec<Entry> = by_id.into_values().collect();
    merged.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then_with(|| a.id.cmp(&b.id))
    });

    merged
        .into_iter()
        .enumerate()
        .map(|(i, e)| RankedEntry {
            rank: i + 1,
            id: e.id,
            score: e.score,
            wins: e.wins,
            penalty: e.penalty,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ids(ranked: &[RankedEntry]) -> Vec<&'static str> {
        ranked.iter().map(|r| r.id).collect()
    }

    fn ranks(ranked: &[RankedEntry]) -> Vec<usize> {
        ranked.iter().map(|r| r.rank).collect()
    }

    #[test]
    fn merges_duplicates_by_best_record_per_id() {
        let entries = vec![
            Entry { id: "mira", score: 70, wins: 5, penalty: 12 },
            Entry { id: "otto", score: 70, wins: 6, penalty: 15 },
            Entry { id: "mira", score: 90, wins: 4, penalty: 99 },
            Entry { id: "otto", score: 88, wins: 8, penalty: 30 },
            Entry { id: "nina", score: 88, wins: 7, penalty: 20 },
        ];

        let ranked = rank_entries(&entries);
        assert_eq!(ids(&ranked), vec!["mira", "otto", "nina"]);
        assert_eq!(ranked[0].score, 90);
        assert_eq!(ranked[1].score, 88);
        assert_eq!(ranked[1].wins, 8);
    }

    #[test]
    fn tie_breaks_use_wins_then_lower_penalty_then_id() {
        let entries = vec![
            Entry { id: "zeta", score: 50, wins: 3, penalty: 8 },
            Entry { id: "beta", score: 50, wins: 5, penalty: 11 },
            Entry { id: "alpha", score: 50, wins: 5, penalty: 11 },
            Entry { id: "gamma", score: 50, wins: 5, penalty: 7 },
        ];

        let ranked = rank_entries(&entries);
        assert_eq!(ids(&ranked), vec!["gamma", "alpha", "beta", "zeta"]);
    }

    #[test]
    fn uses_dense_ranks_for_tied_final_records() {
        let entries = vec![
            Entry { id: "a", score: 100, wins: 4, penalty: 10 },
            Entry { id: "b", score: 100, wins: 4, penalty: 10 },
            Entry { id: "c", score: 95, wins: 9, penalty: 1 },
            Entry { id: "d", score: 95, wins: 9, penalty: 1 },
            Entry { id: "e", score: 80, wins: 2, penalty: 30 },
        ];

        let ranked = rank_entries(&entries);
        assert_eq!(ranks(&ranked), vec![1, 1, 2, 2, 3]);
    }

    #[test]
    fn merging_and_ties_consider_full_record_not_just_score() {
        let entries = vec![
            Entry { id: "ivy", score: 77, wins: 4, penalty: 20 },
            Entry { id: "ivy", score: 77, wins: 6, penalty: 40 },
            Entry { id: "jade", score: 77, wins: 6, penalty: 10 },
            Entry { id: "kyle", score: 77, wins: 6, penalty: 10 },
            Entry { id: "luca", score: 77, wins: 5, penalty: 1 },
        ];

        let ranked = rank_entries(&entries);
        assert_eq!(ids(&ranked), vec!["jade", "kyle", "ivy", "luca"]);
        assert_eq!(ranks(&ranked), vec![1, 1, 2, 3]);
        assert_eq!(ranked[2].wins, 6);
        assert_eq!(ranked[2].penalty, 40);
    }
}
