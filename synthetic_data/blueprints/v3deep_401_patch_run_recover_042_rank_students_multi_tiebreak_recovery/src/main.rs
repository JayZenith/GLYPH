use std::cmp::Ordering;

#[derive(Clone)]
struct Student {
    name: &'static str,
    score: u32,
    penalties: u32,
    solved: u32,
}

fn better(a: &Student, b: &Student) -> bool {
    a.score > b.score
}

fn same_rank(a: &Student, b: &Student) -> bool {
    a.score == b.score
}

fn format_board(rows: &[Student]) -> String {
    let mut out = Vec::new();
    for (i, s) in rows.iter().enumerate() {
        out.push(format!("{}. {} {} {} {}", i + 1, s.name, s.score, s.penalties, s.solved));
    }
    out.join("\n")
}

fn main() {
    let raw = vec![
        Student { name: "Ivy", score: 90, penalties: 4, solved: 7 },
        Student { name: "Bea", score: 95, penalties: 5, solved: 4 },
        Student { name: "Ava", score: 90, penalties: 2, solved: 5 },
        Student { name: "Kai", score: 90, penalties: 2, solved: 6 },
        Student { name: "Zed", score: 95, penalties: 10, solved: 4 },
        Student { name: "Mia", score: 90, penalties: 2, solved: 6 },
        Student { name: "Eli", score: 95, penalties: 5, solved: 3 },
        Student { name: "Kai", score: 88, penalties: 1, solved: 7 },
    ];

    let mut deduped: Vec<Student> = Vec::new();
    for s in raw {
        if let Some(existing) = deduped.iter_mut().find(|x| x.name == s.name) {
            if better(&s, existing) {
                *existing = s;
            }
        } else {
            deduped.push(s);
        }
    }

    deduped.sort_by(|a, b| {
        if a.score != b.score {
            a.score.cmp(&b.score)
        } else if a.penalties != b.penalties {
            a.penalties.cmp(&b.penalties)
        } else if a.solved != b.solved {
            a.solved.cmp(&b.solved)
        } else {
            Ordering::Equal
        }
    });

    println!("{}", format_board(&deduped));
}
