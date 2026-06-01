#[derive(Clone)]
struct Team {
    name: &'static str,
    points: u32,
    goals_for: i32,
    goals_against: i32,
}

impl Team {
    fn gd(&self) -> i32 {
        self.goals_for - self.goals_against
    }
}

fn main() {
    let mut teams = vec![
        Team { name: "Lions", points: 10, goals_for: 9, goals_against: 4 },
        Team { name: "Tigers", points: 10, goals_for: 10, goals_against: 6 },
        Team { name: "Bears", points: 12, goals_for: 11, goals_against: 5 },
        Team { name: "Owls", points: 10, goals_for: 9, goals_against: 4 },
        Team { name: "Falcons", points: 10, goals_for: 8, goals_against: 3 },
        Team { name: "Lions", points: 8, goals_for: 7, goals_against: 5 },
    ];

    teams.sort_by(|a, b| {
        a.points.cmp(&b.points)
            .then(a.gd().cmp(&b.gd()))
            .then(a.goals_against.cmp(&b.goals_against))
            .then(a.name.cmp(b.name))
    });

    for (i, t) in teams.iter().enumerate() {
        println!(
            "{}. {} {} pts gd {:+} gs {}",
            i + 1,
            t.name,
            t.points,
            t.gd(),
            t.goals_for
        );
    }
}
