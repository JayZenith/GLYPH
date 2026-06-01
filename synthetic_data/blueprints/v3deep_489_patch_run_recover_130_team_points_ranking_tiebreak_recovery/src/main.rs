#[derive(Clone)]
struct Team {
    name: &'static str,
    points: u32,
    wins: u32,
    penalties: u32,
}

fn main() {
    let mut teams = vec![
        Team { name: "Alpha", points: 10, wins: 3, penalties: 2 },
        Team { name: "Beta", points: 10, wins: 3, penalties: 1 },
        Team { name: "Gamma", points: 10, wins: 2, penalties: 0 },
        Team { name: "Delta", points: 10, wins: 3, penalties: 1 },
        Team { name: "Eta", points: 9, wins: 3, penalties: 0 },
        Team { name: "Zeta", points: 9, wins: 2, penalties: 0 },
        Team { name: "Epsilon", points: 8, wins: 4, penalties: 3 },
    ];

    teams.sort_by(|a, b| {
        a.points
            .cmp(&b.points)
            .then(a.wins.cmp(&b.wins))
            .then(a.penalties.cmp(&b.penalties))
            .then(a.name.cmp(&b.name))
    });

    for (i, team) in teams.iter().enumerate() {
        println!(
            "{}. {} | {} pts | {}W | {} pen",
            i + 1,
            team.name,
            team.points,
            team.wins,
            team.penalties
        );
    }
}
