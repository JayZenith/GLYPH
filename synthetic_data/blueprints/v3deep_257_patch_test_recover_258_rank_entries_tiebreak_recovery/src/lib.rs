#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub name: &'static str,
    pub score: u32,
    pub wins: u32,
}

pub fn rank_entries(entries: &[Entry]) -> Vec<String> {
    let mut items = entries.to_vec();
    items.sort_by(|a, b| {
        a.score
            .cmp(&b.score)
            .then_with(|| a.wins.cmp(&b.wins))
            .then_with(|| a.name.cmp(b.name))
    });

    let mut out = Vec::new();
    let mut last_score = None;
    let mut place = 0usize;

    for (idx, item) in items.iter().enumerate() {
        if Some(item.score) != last_score {
            place = idx + 1;
            last_score = Some(item.score);
        }
        out.push(format!("{}:{}({}/{})", place, item.name, item.score, item.wins));
    }

    out
}

#[cfg(test)]
mod tests {
    use super::{rank_entries, Entry};

    #[test]
    fn orders_by_score_then_wins_then_name() {
        let items = vec![
            Entry { name: "zoe", score: 12, wins: 3 },
            Entry { name: "amy", score: 15, wins: 1 },
            Entry { name: "bea", score: 15, wins: 4 },
            Entry { name: "ada", score: 15, wins: 4 },
        ];

        assert_eq!(
            rank_entries(&items),
            vec![
                "1:ada(15/4)",
                "1:bea(15/4)",
                "3:amy(15/1)",
                "4:zoe(12/3)",
            ]
        );
    }

    #[test]
    fn ties_require_same_score_and_wins() {
        let items = vec![
            Entry { name: "ivy", score: 9, wins: 2 },
            Entry { name: "eli", score: 9, wins: 5 },
            Entry { name: "max", score: 7, wins: 9 },
            Entry { name: "ava", score: 9, wins: 5 },
        ];

        assert_eq!(
            rank_entries(&items),
            vec![
                "1:ava(9/5)",
                "1:eli(9/5)",
                "3:ivy(9/2)",
                "4:max(7/9)",
            ]
        );
    }

    #[test]
    fn empty_input_stays_empty() {
        let items: Vec<Entry> = vec![];
        assert!(rank_entries(&items).is_empty());
    }
}
