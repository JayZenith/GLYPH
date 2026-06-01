use std::cmp::Ordering;

#[derive(Clone)]
struct Team {
    name: &'static str,
    points: u32,
    goals_for: i32,
    goals_against: i32,
}

impl Team {
    fn goal_diff(&self) -> i32 {
        self.goals_against - self.goals_for
    }
}

fn main() {
    let mut teams = vec![
        Team { name: "Aces", points: 8, goals_for: 5, goals_against: 2 },
        Team { name: "Bears", points: 8, goals_for: 6, goals_against: 3 },
        Team { name: "Cobras", points: 8, goals_for: 6, goals_against: 3 },
        Team { name: "Dynamos", points: 5, goals_for: 4, goals_against: 6 },
        Team { name: "Falcons", points: 10, goals_for: 8, goals_against: 4 },
    ];

    teams.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then_with(|| a.goal_diff().cmp(&b.goal_diff()))
            .then_with(|| a.name.cmp(&b.name))
    });

    let mut lines = Vec::new();
    for (i, team) in teams.iter().enumerate() {
        lines.push(format!(
            "{}. {} - {} pts (GD {:+}, GS {})",
            i + 1,
            team.name,
            team.points,
            team.goal_diff(),
            team.goals_against
        ));
    }

    println!("{}", lines.join("\n"));
}
