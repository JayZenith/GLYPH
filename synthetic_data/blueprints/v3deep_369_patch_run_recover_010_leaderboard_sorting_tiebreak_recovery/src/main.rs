use std::collections::HashSet;

#[derive(Clone)]
struct Team {
    name: &'static str,
    solved: u32,
    penalty: u32,
    last: u32,
}

fn format_board(mut teams: Vec<Team>) -> String {
    let mut seen = HashSet::new();
    teams.retain(|t| seen.insert(t.name));

    teams.sort_by(|a, b| {
        b.solved.cmp(&a.solved)
            .then(b.penalty.cmp(&a.penalty))
            .then(b.last.cmp(&a.last))
            .then(b.name.cmp(&a.name))
    });

    teams
        .into_iter()
        .enumerate()
        .map(|(i, t)| {
            format!(
                "{}. {} | solved={} penalty={} last={}",
                i + 1,
                t.name,
                t.solved,
                t.penalty,
                t.last
            )
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn main() {
    let teams = vec![
        Team { name: "Alpha", solved: 7, penalty: 900, last: 120 },
        Team { name: "Bravo", solved: 7, penalty: 860, last: 105 },
        Team { name: "Gamma", solved: 6, penalty: 740, last: 95 },
        Team { name: "Echo", solved: 7, penalty: 860, last: 105 },
        Team { name: "Bravo", solved: 8, penalty: 800, last: 100 },
        Team { name: "Delta", solved: 7, penalty: 860, last: 110 },
        Team { name: "Foxtrot", solved: 5, penalty: 600, last: 70 },
        Team { name: "Kappa", solved: 6, penalty: 700, last: 80 },
    ];

    println!("{}", format_board(teams));
}
