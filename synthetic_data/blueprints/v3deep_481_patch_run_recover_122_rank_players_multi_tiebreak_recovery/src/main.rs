#[derive(Clone)]
struct Player {
    name: &'static str,
    score: u32,
    wins: u32,
    losses: u32,
}

fn players() -> Vec<Player> {
    vec![
        Player { name: "Zed", score: 14, wins: 4, losses: 1 },
        Player { name: "Ava", score: 14, wins: 4, losses: 2 },
        Player { name: "Mira", score: 14, wins: 5, losses: 1 },
        Player { name: "Nia", score: 12, wins: 6, losses: 0 },
        Player { name: "Eli", score: 12, wins: 6, losses: 1 },
        Player { name: "Kai", score: 14, wins: 4, losses: 1 },
        Player { name: "Uma", score: 12, wins: 5, losses: 1 },
    ]
}

fn format_table(mut items: Vec<Player>) -> String {
    items.sort_by(|a, b| a.name.cmp(b.name));

    let mut out = String::new();
    let mut rank = 1usize;

    for (i, p) in items.iter().enumerate() {
        if i > 0 {
            out.push('\n');
            rank += 1;
        }
        out.push_str(&format!(
            "{}. {} score={} wins={} losses={}",
            rank,
            p.name,
            p.score,
            p.wins,
            p.losses
        ));
    }

    out
}

fn main() {
    println!("{}", format_table(players()));
}
