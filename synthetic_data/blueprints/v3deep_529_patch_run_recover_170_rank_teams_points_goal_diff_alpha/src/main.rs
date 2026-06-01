struct Team {
    name: &'static str,
    points: u32,
    goals_for: i32,
    goals_against: i32,
}

impl Team {
    fn goal_diff(&self) -> i32 {
        self.goals_for - self.goals_against
    }
}

fn main() {
    let mut teams = vec![
        Team { name: "Comets", points: 12, goals_for: 8, goals_against: 3 },
        Team { name: "Bears", points: 12, goals_for: 9, goals_against: 5 },
        Team { name: "Aces", points: 10, goals_for: 7, goals_against: 4 },
        Team { name: "Dynamos", points: 10, goals_for: 6, goals_against: 3 },
        Team { name: "Falcons", points: 12, goals_for: 9, goals_against: 4 },
    ];

    teams.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then(a.goal_diff().cmp(&b.goal_diff()))
            .then(a.goals_for.cmp(&b.goals_for))
            .then(b.name.cmp(&a.name))
    });

    for (idx, team) in teams.iter().enumerate() {
        println!(
            "{}. {} - {} pts (GD:{}, GS:{})",
            idx,
            team.name,
            team.points,
            team.goal_diff(),
            team.goals_for
        );
    }
}
