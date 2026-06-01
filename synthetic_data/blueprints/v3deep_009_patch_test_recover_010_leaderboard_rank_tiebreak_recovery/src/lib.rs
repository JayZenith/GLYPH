use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub score: u32,
    pub wins: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RankedEntry {
    pub rank: usize,
    pub name: String,
    pub score: u32,
    pub wins: u32,
}

fn better(a: &Entry, b: &Entry) -> bool {
    a.score > b.score || (a.score == b.score && a.wins > b.wins)
}

pub fn leaderboard(entries: &[Entry]) -> Vec<RankedEntry> {
    let mut best_by_name: HashMap<String, Entry> = HashMap::new();
    for e in entries {
        match best_by_name.get(&e.name) {
            Some(prev) if better(prev, e) => {}
            _ => {
                best_by_name.insert(e.name.clone(), e.clone());
            }
        }
    }

    let mut items: Vec<Entry> = best_by_name.into_values().collect();
    items.sort_by(|a, b| a.score.cmp(&b.score).then(a.wins.cmp(&b.wins)).then(a.name.cmp(&b.name)));

    let mut out = Vec::new();
    let mut current_rank = 1;
    for (idx, e) in items.into_iter().enumerate() {
        if idx > 0 {
            current_rank += 1;
        }
        out.push(RankedEntry {
            rank: current_rank,
            name: e.name,
            score: e.score,
            wins: e.wins,
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn e(name: &str, score: u32, wins: u32) -> Entry {
        Entry {
            name: name.to_string(),
            score,
            wins,
        }
    }

    #[test]
    fn sorts_by_score_then_wins_then_name() {
        let got = leaderboard(&[
            e("zoe", 10, 2),
            e("amy", 20, 1),
            e("bob", 20, 3),
            e("abe", 20, 3),
            e("cal", 10, 5),
        ]);
        let names: Vec<_> = got.into_iter().map(|r| r.name).collect();
        assert_eq!(names, vec!["abe", "bob", "amy", "cal", "zoe"]);
    }

    #[test]
    fn duplicate_names_keep_only_best_record_before_sorting() {
        let got = leaderboard(&[
            e("kai", 10, 2),
            e("ivy", 12, 1),
            e("kai", 12, 0),
            e("kai", 12, 4),
            e("ivy", 11, 8),
        ]);
        let got: Vec<_> = got
            .into_iter()
            .map(|r| (r.name, r.score, r.wins, r.rank))
            .collect();
        assert_eq!(got, vec![("kai".to_string(), 12, 4, 1), ("ivy".to_string(), 12, 1, 2)]);
    }

    #[test]
    fn ties_share_rank_and_next_rank_skips() {
        let got = leaderboard(&[
            e("ann", 30, 2),
            e("bea", 30, 2),
            e("cam", 25, 9),
            e("dan", 25, 9),
            e("eli", 25, 1),
            e("fay", 20, 7),
        ]);
        let got: Vec<_> = got.into_iter().map(|r| (r.name, r.rank)).collect();
        assert_eq!(
            got,
            vec![
                ("ann".to_string(), 1),
                ("bea".to_string(), 1),
                ("cam".to_string(), 3),
                ("dan".to_string(), 3),
                ("eli".to_string(), 5),
                ("fay".to_string(), 6),
            ]
        );
    }
}
