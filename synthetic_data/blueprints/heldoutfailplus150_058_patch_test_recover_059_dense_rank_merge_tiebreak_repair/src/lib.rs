use std::cmp::Ordering;
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub rank: usize,
    pub name: String,
    pub points: i32,
    pub events: u32,
    pub best_finish: u32,
}

pub fn leaderboard(rows: &[(&str, i32, u32, u32)]) -> Vec<Entry> {
    let mut merged: BTreeMap<String, (i32, u32, u32)> = BTreeMap::new();
    for &(name, points, events, best_finish) in rows {
        let key = name.to_string();
        let slot = merged.entry(key).or_insert((0, 0, best_finish));
        slot.0 += points;
        slot.1 += 1;
        if best_finish > slot.2 {
            slot.2 = best_finish;
        }
    }

    let mut out: Vec<Entry> = merged
        .into_iter()
        .map(|(name, (points, events, best_finish))| Entry {
            rank: 0,
            name,
            points,
            events,
            best_finish,
        })
        .collect();

    out.sort_by(|a, b| {
        b.points
            .cmp(&a.points)
            .then_with(|| a.events.cmp(&b.events))
            .then_with(|| b.best_finish.cmp(&a.best_finish))
            .then_with(|| a.name.cmp(&b.name))
    });

    for (i, e) in out.iter_mut().enumerate() {
        e.rank = i + 1;
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(xs: &[Entry]) -> Vec<&str> {
        xs.iter().map(|e| e.name.as_str()).collect()
    }

    #[test]
    fn merges_duplicates_and_uses_dense_ranks() {
        let board = leaderboard(&[
            ("Liu", 7, 1, 2),
            ("Mia", 10, 1, 1),
            ("Liu", 3, 1, 1),
            ("Noa", 10, 1, 1),
            ("Zed", 8, 1, 3),
        ]);

        assert_eq!(names(&board), vec!["Liu", "Mia", "Noa", "Zed"]);
        assert_eq!(board[0].points, 10);
        assert_eq!(board[0].events, 2);
        assert_eq!(board[0].best_finish, 1);
        assert_eq!(board.iter().map(|e| e.rank).collect::<Vec<_>>(), vec![1, 1, 1, 2]);
    }

    #[test]
    fn tie_breaks_use_fewer_events_then_better_finish_then_name() {
        let board = leaderboard(&[
            ("Ivy", 12, 1, 2),
            ("Bea", 12, 1, 3),
            ("Kira", 12, 1, 3),
            ("Ivy", 0, 1, 2),
            ("Moe", 11, 1, 1),
        ]);

        assert_eq!(names(&board), vec!["Bea", "Kira", "Ivy", "Moe"]);
        assert_eq!(board[0].rank, 1);
        assert_eq!(board[1].rank, 1);
        assert_eq!(board[2].rank, 2);
        assert_eq!(board[3].rank, 3);
    }

    #[test]
    fn ignores_zero_or_negative_point_rows_but_still_keeps_positive_totals() {
        let board = leaderboard(&[
            ("Rin", 5, 1, 4),
            ("Rin", 0, 1, 1),
            ("Sol", -2, 1, 1),
            ("Tao", 5, 1, 2),
            ("Uma", 4, 1, 1),
        ]);

        assert_eq!(names(&board), vec!["Tao", "Rin", "Uma"]);
        assert_eq!(board.iter().map(|e| e.rank).collect::<Vec<_>>(), vec![1, 1, 2]);
        assert!(board.iter().all(|e| e.points > 0));
    }

    #[test]
    fn name_comparison_is_case_insensitive_with_lowercase_as_final_tiebreak() {
        let board = leaderboard(&[
            ("amy", 9, 1, 2),
            ("Zoe", 8, 1, 1),
            ("Amy", 9, 1, 2),
            ("bob", 9, 1, 2),
        ]);

        assert_eq!(names(&board), vec!["Amy", "amy", "bob", "Zoe"]);
        assert_eq!(board.iter().map(|e| e.rank).collect::<Vec<_>>(), vec![1, 1, 1, 2]);
    }
}
