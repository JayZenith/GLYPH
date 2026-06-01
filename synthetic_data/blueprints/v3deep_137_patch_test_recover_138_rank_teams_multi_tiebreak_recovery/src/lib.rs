use std::cmp::Ordering;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Team<'a> {
    pub name: &'a str,
    pub points: u32,
    pub goal_diff: i32,
    pub goals_for: u32,
    pub wins: u32,
}

pub fn rank_teams<'a>(teams: &[Team<'a>]) -> Vec<&'a str> {
    let mut ordered: Vec<&Team<'a>> = teams.iter().collect();
    ordered.sort_by(|a, b| {
        a.points
            .cmp(&b.points)
            .then_with(|| a.goal_diff.cmp(&b.goal_diff))
            .then_with(|| a.goals_for.cmp(&b.goals_for))
            .then_with(|| a.wins.cmp(&b.wins))
            .then_with(|| a.name.cmp(b.name))
    });
    ordered.into_iter().map(|t| t.name).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sorts_by_points_then_goal_diff() {
        let teams = vec![
            Team { name: "Lions", points: 12, goal_diff: 5, goals_for: 9, wins: 4 },
            Team { name: "Bears", points: 15, goal_diff: 1, goals_for: 8, wins: 5 },
            Team { name: "Owls", points: 12, goal_diff: 7, goals_for: 6, wins: 4 },
        ];
        assert_eq!(rank_teams(&teams), vec!["Bears", "Owls", "Lions"]);
    }

    #[test]
    fn uses_goals_for_before_wins() {
        let teams = vec![
            Team { name: "Arrows", points: 10, goal_diff: 3, goals_for: 11, wins: 3 },
            Team { name: "Blaze", points: 10, goal_diff: 3, goals_for: 9, wins: 5 },
            Team { name: "Comets", points: 10, goal_diff: 3, goals_for: 11, wins: 2 },
        ];
        assert_eq!(rank_teams(&teams), vec!["Arrows", "Comets", "Blaze"]);
    }

    #[test]
    fn uses_name_as_final_case_insensitive_tiebreak() {
        let teams = vec![
            Team { name: "zebras", points: 8, goal_diff: 0, goals_for: 7, wins: 2 },
            Team { name: "Alphas", points: 8, goal_diff: 0, goals_for: 7, wins: 2 },
            Team { name: "moose", points: 8, goal_diff: 0, goals_for: 7, wins: 2 },
        ];
        assert_eq!(rank_teams(&teams), vec!["Alphas", "moose", "zebras"]);
    }

    #[test]
    fn preserves_input_order_when_all_tiebreakers_match_ignoring_name_case() {
        let teams = vec![
            Team { name: "beta", points: 6, goal_diff: 1, goals_for: 4, wins: 2 },
            Team { name: "Beta", points: 6, goal_diff: 1, goals_for: 4, wins: 2 },
            Team { name: "gamma", points: 5, goal_diff: 0, goals_for: 3, wins: 1 },
        ];
        assert_eq!(rank_teams(&teams), vec!["beta", "Beta", "gamma"]);
    }

    #[test]
    fn handles_mixed_positive_and_negative_goal_diff() {
        let teams = vec![
            Team { name: "North", points: 9, goal_diff: -1, goals_for: 8, wins: 3 },
            Team { name: "South", points: 9, goal_diff: 2, goals_for: 6, wins: 2 },
            Team { name: "East", points: 9, goal_diff: -3, goals_for: 10, wins: 3 },
            Team { name: "West", points: 9, goal_diff: -1, goals_for: 9, wins: 2 },
        ];
        assert_eq!(rank_teams(&teams), vec!["South", "West", "North", "East"]);
    }
}
