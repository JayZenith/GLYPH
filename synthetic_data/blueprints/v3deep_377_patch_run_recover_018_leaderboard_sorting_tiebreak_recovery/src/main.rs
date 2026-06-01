use std::collections::BTreeMap;

#[derive(Clone, Debug)]
struct Entry {
    name: String,
    score: i32,
    penalties: i32,
    last_minute: i32,
}

fn parse(input: &str) -> Vec<Entry> {
    input
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|line| {
            let parts: Vec<&str> = line.split(',').collect();
            Entry {
                name: parts[0].to_string(),
                score: parts[1].parse().unwrap(),
                penalties: parts[2].parse().unwrap(),
                last_minute: parts[3].parse().unwrap(),
            }
        })
        .collect()
}

fn leaderboard(entries: &[Entry]) -> Vec<Entry> {
    let mut rows = entries.to_vec();
    rows.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then(a.penalties.cmp(&b.penalties))
            .then(b.last_minute.cmp(&a.last_minute))
            .then(b.name.cmp(&a.name))
    });
    rows.truncate(5);
    rows
}

fn format_board(entries: &[Entry]) -> String {
    entries
        .iter()
        .enumerate()
        .map(|(idx, e)| format!("{}. {} {} {} {}", idx + 1, e.name, e.score, e.penalties, e.last_minute))
        .collect::<Vec<_>>()
        .join("\n")
}

fn main() {
    let input = "Ava,100,3,20
Ben,120,4,30
Cara,120,5,15
Dana,110,3,40
Eli,70,2,10
Ava,20,1,25
Eli,50,2,30
Fay,110,4,35
Gus,90,1,12
Hana,90,1,18";

    let entries = parse(input);
    let board = leaderboard(&entries);
    let out = format_board(&board);
    println!("{}", out);
}
