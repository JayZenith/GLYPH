const INPUT: &str = "alice,120,ops\nBob,120,ops\nclio,450,ml\ndana,0,ops\nerin,1000,ops\nfrank,30,Ops\ngail,42,infra,extra\nhelen,77\nian,-5,qa\njane,075,qa\nzoe,999,api\nmi,80,ops\nkara,10,o9s\nluke,85,sre\n";

fn parse_record(line: &str) -> Option<(String, u16, String)> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() < 3 {
        return None;
    }
    let name = parts[0].trim();
    let score: u16 = parts[1].trim().parse().ok()?;
    let dept = parts[2].trim();

    if name.len() < 2 || dept.is_empty() {
        return None;
    }

    Some((name.to_string(), score, dept.to_string()))
}

fn main() {
    let mut out = Vec::new();
    for line in INPUT.lines() {
        if let Some((name, score, dept)) = parse_record(line) {
            out.push(format!("{}#{}@{}", name, score, dept));
        }
    }
    println!("valid: {}", out.len());
    if !out.is_empty() {
        println!("{}", out.join("\n"));
    }
}
