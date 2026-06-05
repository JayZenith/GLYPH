use std::collections::HashMap;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScoreRow {
    pub name: String,
    pub points: u32,
    pub solved: u32,
    pub penalties: u32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RankedRow {
    pub rank: usize,
    pub name: String,
    pub points: u32,
    pub solved: u32,
    pub penalties: u32,
}

pub fn summarize(rows: &[ScoreRow]) -> Vec<RankedRow> {
    let mut merged: HashMap<String, ScoreRow> = HashMap::new();
    for row in rows {
        let entry = merged.entry(row.name.clone()).or_insert_with(|| ScoreRow {
            name: row.name.clone(),
            points: 0,
            solved: 0,
            penalties: 0,
        });
        entry.points += row.points;
        entry.solved += row.solved;
        entry.penalties += row.penalties;
    }

    let mut items: Vec<ScoreRow> = merged.into_values().collect();
    items.sort_by(|a, b| {
        b.points
            .cmp(&a.points)
            .then_with(|| a.penalties.cmp(&b.penalties))
            .then_with(|| a.name.cmp(&b.name))
    });

    items
        .into_iter()
        .enumerate()
        .map(|(i, row)| RankedRow {
            rank: i + 1,
            name: row.name,
            points: row.points,
            solved: row.solved,
            penalties: row.penalties,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn row(name: &str, points: u32, solved: u32, penalties: u32) -> ScoreRow {
        ScoreRow {
            name: name.to_string(),
            points,
            solved,
            penalties,
        }
    }

    #[test]
    fn merges_case_insensitive_duplicates_and_uses_best_display_name() {
        let rows = vec![
            row("zoe", 30, 3, 40),
            row("Zoe", 20, 1, 15),
            row("amy", 45, 4, 18),
        ];
        let got = summarize(&rows);
        assert_eq!(
            got,
            vec![
                RankedRow {
                    rank: 1,
                    name: "Zoe".to_string(),
                    points: 50,
                    solved: 4,
                    penalties: 55,
                },
                RankedRow {
                    rank: 2,
                    name: "amy".to_string(),
                    points: 45,
                    solved: 4,
                    penalties: 18,
                },
            ]
        );
    }

    #[test]
    fn sorts_by_points_then_solved_then_lower_penalties_then_name_case_insensitive() {
        let rows = vec![
            row("delta", 50, 5, 10),
            row("Bravo", 50, 6, 40),
            row("charlie", 50, 6, 30),
            row("alpha", 50, 6, 30),
        ];
        let got = summarize(&rows);
        assert_eq!(
            got.into_iter().map(|r| r.name).collect::<Vec<_>>(),
            vec!["alpha", "charlie", "Bravo", "delta"]
        );
    }

    #[test]
    fn assigns_dense_ranks_after_ties() {
        let rows = vec![
            row("alpha", 100, 8, 20),
            row("bravo", 100, 8, 20),
            row("charlie", 95, 9, 5),
            row("delta", 95, 7, 1),
            row("echo", 80, 10, 50),
        ];
        let got = summarize(&rows);
        assert_eq!(
            got.into_iter().map(|r| (r.name, r.rank)).collect::<Vec<_>>(),
            vec![
                ("alpha".to_string(), 1),
                ("bravo".to_string(), 1),
                ("charlie".to_string(), 2),
                ("delta".to_string(), 3),
                ("echo".to_string(), 4),
            ]
        );
    }

    #[test]
    fn keeps_title_case_over_lower_or_upper_for_display_name() {
        let rows = vec![
            row("ALICE", 10, 1, 1),
            row("alice", 15, 1, 2),
            row("Alice", 20, 2, 3),
            row("bob", 40, 3, 1),
        ];
        let got = summarize(&rows);
        assert_eq!(got[1].name, "Alice");
        assert_eq!(got[1].points, 45);
    }

    #[test]
    fn name_tiebreak_is_case_insensitive_but_stable_for_display() {
        let rows = vec![
            row("bob", 10, 1, 1),
            row("ALAN", 10, 1, 1),
            row("amy", 10, 1, 1),
        ];
        let got = summarize(&rows);
        assert_eq!(
            got.into_iter().map(|r| r.name).collect::<Vec<_>>(),
            vec!["ALAN", "amy", "bob"]
        );
    }
}
