#[derive(Clone, Copy)]
struct Team {
    name: &'static str,
    points: u32,
    penalties: u32,
    wins: u32,
}

fn main() {
    let mut teams = vec![
        Team { name: "Atlas", points: 13, penalties: 2, wins: 3 },
        Team { name: "Bravo", points: 13, penalties: 2, wins: 5 },
        Team { name: "Cobra", points: 11, penalties: 0, wins: 3 },
        Team { name: "Delta", points: 13, penalties: 1, wins: 4 },
        Team { name: "Echo", points: 13, penalties: 1, wins: 4 },
        Team { name: "Frost", points: 11, penalties: 0, wins: 2 },
    ];

    teams.sort_by(|a, b| {
        a.points
            .cmp(&b.points)
            .then(a.penalties.cmp(&b.penalties))
            .then(a.wins.cmp(&b.wins))
            .then(a.name.cmp(&b.name))
    });

    for (i, team) in teams.iter().enumerate() {
        println!(
            "{}. {} {} pts ({} pen, {} wins)",
            i + 1,
            team.name,
            team.points,
            team.penalties,
            team.wins
        );
    }
}
