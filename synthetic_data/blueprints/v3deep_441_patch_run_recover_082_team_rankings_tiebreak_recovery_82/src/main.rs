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
        Team { name: "Falcons", points: 7, goals_for: 6, goals_against: 2 },
        Team { name: "Aardvarks", points: 7, goals_for: 5, goals_against: 1 },
        Team { name: "Cobras", points: 7, goals_for: 7, goals_against: 4 },
        Team { name: "Dynamos", points: 6, goals_for: 8, goals_against: 3 },
        Team { name: "Eagles", points: 6, goals_for: 6, goals_against: 1 },
        Team { name: "Bears", points: 7, goals_for: 6, goals_against: 2 },
    ];

    teams.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then(a.goal_diff().cmp(&b.goal_diff()))
            .then(a.goals_for.cmp(&b.goals_for))
            .then(a.name.cmp(b.name))
    });

    println!("Standings:");
    for (i, team) in teams.iter().enumerate() {
        let gd = team.goal_diff();
        println!(
            "{}. {} | pts={} | gd={} | gf={}",
            i + 1,
            team.name,
            team.points,
            gd,
            team.goals_for
        );
    }
}
