use std::cmp::Ordering;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Item {
    pub name: &'static str,
    pub score: i32,
    pub wins: u32,
    pub penalty: u32,
    pub featured: bool,
}

pub fn ranked_names(items: &[Item]) -> Vec<&'static str> {
    let mut v = items.to_vec();
    v.sort_by(|a, b| compare_items(a, b));
    v.into_iter().map(|i| i.name).collect()
}

fn compare_items(a: &Item, b: &Item) -> Ordering {
    a.score
        .cmp(&b.score)
        .then(a.wins.cmp(&b.wins))
        .then(a.penalty.cmp(&b.penalty))
        .then(a.name.cmp(&b.name))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn item(
        name: &'static str,
        score: i32,
        wins: u32,
        penalty: u32,
        featured: bool,
    ) -> Item {
        Item {
            name,
            score,
            wins,
            penalty,
            featured,
        }
    }

    #[test]
    fn orders_by_score_then_wins_then_penalty_then_featured_then_name() {
        let items = vec![
            item("delta", 10, 3, 5, false),
            item("beta", 12, 1, 9, false),
            item("alpha", 12, 1, 9, true),
            item("gamma", 12, 4, 2, false),
            item("omega", 12, 4, 2, true),
            item("zeta", 12, 4, 1, false),
        ];

        assert_eq!(
            ranked_names(&items),
            vec!["zeta", "omega", "gamma", "alpha", "beta", "delta"]
        );
    }

    #[test]
    fn featured_only_breaks_exact_metric_ties() {
        let items = vec![
            item("plain-top", 20, 8, 1, false),
            item("feat-mid", 18, 4, 6, true),
            item("plain-mid", 18, 4, 6, false),
            item("feat-low", 18, 3, 1, true),
        ];

        assert_eq!(
            ranked_names(&items),
            vec!["plain-top", "feat-mid", "plain-mid", "feat-low"]
        );
    }

    #[test]
    fn alphabetical_name_is_final_tiebreak() {
        let items = vec![
            item("charlie", 7, 2, 9, false),
            item("bravo", 7, 2, 9, false),
            item("alpha", 7, 2, 9, false),
        ];

        assert_eq!(ranked_names(&items), vec!["alpha", "bravo", "charlie"]);
    }

    #[test]
    fn keeps_negative_scores_at_the_bottom() {
        let items = vec![
            item("steady", 0, 2, 5, false),
            item("risky", -1, 9, 0, true),
            item("safe", 3, 0, 7, false),
        ];

        assert_eq!(ranked_names(&items), vec!["safe", "steady", "risky"]);
    }

    #[test]
    fn lower_penalty_beats_higher_penalty_when_score_and_wins_match() {
        let items = vec![
            item("high-penalty", 9, 5, 8, true),
            item("low-penalty", 9, 5, 2, false),
            item("mid-penalty", 9, 5, 4, true),
        ];

        assert_eq!(
            ranked_names(&items),
            vec!["low-penalty", "mid-penalty", "high-penalty"]
        );
    }

    #[test]
    fn higher_wins_beat_lower_wins_with_same_score() {
        let items = vec![
            item("many-wins", 11, 6, 9, false),
            item("few-wins", 11, 2, 0, true),
            item("mid-wins", 11, 4, 1, false),
        ];

        assert_eq!(
            ranked_names(&items),
            vec!["many-wins", "mid-wins", "few-wins"]
        );
    }
}
