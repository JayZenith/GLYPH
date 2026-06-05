use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: String,
    pub points: i32,
    pub wins: u32,
    pub played: u32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ranked {
    pub rank: usize,
    pub name: String,
    pub points: i32,
    pub wins: u32,
    pub played: u32,
}

pub fn rank_leaderboard(entries: &[Entry]) -> Vec<Ranked> {
    let mut merged: BTreeMap<String, Entry> = BTreeMap::new();

    for e in entries {
        let key = e.name.clone();
        let slot = merged.entry(key.clone()).or_insert(Entry {
            name: key,
            points: 0,
            wins: 0,
            played: 0,
        });
        slot.points += e.points;
        slot.wins += e.wins;
        slot.played += e.played;
    }

    let mut items: Vec<Entry> = merged.into_values().collect();
    items.sort_by(|a, b| a.points.cmp(&b.points));

    let mut out = Vec::new();
    let mut last_points: Option<i32> = None;
    let mut rank = 0usize;

    for (idx, e) in items.into_iter().enumerate() {
        if last_points != Some(e.points) {
            rank = idx + 1;
            last_points = Some(e.points);
        }
        out.push(Ranked {
            rank,
            name: e.name,
            points: e.points,
            wins: e.wins,
            played: e.played,
        });
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(v: &[Ranked]) -> Vec<&str> {
        v.iter().map(|r| r.name.as_str()).collect()
    }

    #[test]
    fn merges_case_insensitive_duplicates() {
        let rows = vec![
            Entry { name: "ALICE".into(), points: 4, wins: 1, played: 2 },
            Entry { name: "alice".into(), points: 6, wins: 2, played: 3 },
            Entry { name: "Bob".into(), points: 7, wins: 2, played: 2 },
        ];
        let ranked = rank_leaderboard(&rows);
        assert_eq!(ranked.len(), 2);
        assert_eq!(ranked[0].name, "alice");
        assert_eq!(ranked[0].points, 10);
        assert_eq!(ranked[0].wins, 3);
        assert_eq!(ranked[0].played, 5);
    }

    #[test]
    fn sorts_by_points_desc_then_wins_desc_then_played_asc_then_name() {
        let rows = vec![
            Entry { name: "zoe".into(), points: 12, wins: 4, played: 7 },
            Entry { name: "amy".into(), points: 12, wins: 5, played: 8 },
            Entry { name: "bob".into(), points: 12, wins: 5, played: 6 },
            Entry { name: "cal".into(), points: 12, wins: 5, played: 6 },
            Entry { name: "dan".into(), points: 10, wins: 9, played: 1 },
        ];
        let ranked = rank_leaderboard(&rows);
        assert_eq!(names(&ranked), vec!["bob", "cal", "amy", "zoe", "dan"]);
    }

    #[test]
    fn uses_dense_ranks_not_competition_ranks() {
        let rows = vec![
            Entry { name: "a".into(), points: 30, wins: 3, played: 3 },
            Entry { name: "b".into(), points: 30, wins: 2, played: 3 },
            Entry { name: "c".into(), points: 20, wins: 9, played: 9 },
            Entry { name: "d".into(), points: 20, wins: 8, played: 9 },
            Entry { name: "e".into(), points: 10, wins: 1, played: 1 },
        ];
        let ranked = rank_leaderboard(&rows);
        let pairs: Vec<(&str, usize)> = ranked.iter().map(|r| (r.name.as_str(), r.rank)).collect();
        assert_eq!(pairs, vec![("a", 1), ("b", 1), ("c", 2), ("d", 2), ("e", 3)]);
    }

    #[test]
    fn merged_name_uses_lowercase_canonical_and_tiebreaks_apply_after_merge() {
        let rows = vec![
            Entry { name: "Mia".into(), points: 5, wins: 1, played: 2 },
            Entry { name: "MIA".into(), points: 5, wins: 2, played: 2 },
            Entry { name: "Noah".into(), points: 10, wins: 3, played: 5 },
            Entry { name: "olga".into(), points: 10, wins: 3, played: 4 },
        ];
        let ranked = rank_leaderboard(&rows);
        assert_eq!(names(&ranked), vec!["mia", "olga", "noah"]);
        assert_eq!(ranked[0].rank, 1);
        assert_eq!(ranked[1].rank, 1);
        assert_eq!(ranked[2].rank, 1);
    }
}
