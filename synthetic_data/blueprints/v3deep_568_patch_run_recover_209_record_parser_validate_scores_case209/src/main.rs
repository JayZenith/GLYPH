use std::collections::HashSet;

const INPUT: &str = "id=alpha;score=42;active=true
id=beta;score=abc;active=false
id=alpha;score=7;active=true
id=gamma;active=true
id=delta;score=100;active=TRUE";

fn main() {
    let mut seen = HashSet::new();
    let mut valid = 0usize;
    let mut invalid = Vec::new();

    for (idx, line) in INPUT.lines().enumerate() {
        let mut id = "";
        let mut score = "0";
        let mut active = false;

        for part in line.split(',') {
            let mut kv = part.splitn(2, ':');
            let key = kv.next().unwrap_or("");
            let val = kv.next().unwrap_or("");
            match key {
                "id" => id = val,
                "score" => score = val,
                "active" => active = val == "true" || val == "TRUE",
                _ => {}
            }
        }

        if id.is_empty() {
            invalid.push(format!("{}: missing id", idx));
            continue;
        }
        if seen.contains(id) {
            invalid.push(format!("{}: duplicate id", idx));
            continue;
        }
        seen.insert(id.to_string());

        if score.parse::<u32>().is_err() {
            invalid.push(format!("{}: malformed score", idx));
            continue;
        }

        if !active {
            invalid.push(format!("{}: inactive", idx));
            continue;
        }

        valid += 1;
    }

    println!("valid={}", valid);
    if !invalid.is_empty() {
        println!("errors={}", invalid.join(", "));
    }
}
