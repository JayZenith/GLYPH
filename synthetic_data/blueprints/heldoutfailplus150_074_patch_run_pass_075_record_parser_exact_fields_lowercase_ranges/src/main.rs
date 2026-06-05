fn parse_record(line: &str) -> Result<(String, String, u8, i32), String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return Err("expected 4 fields".to_string());
    }

    let name = parts[0].trim();
    let team = parts[1].trim();
    let level: u8 = parts[2].trim().parse().map_err(|_| "invalid level".to_string())?;
    let score: i32 = parts[3].trim().parse().map_err(|_| "invalid score".to_string())?;

    if !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return Err("invalid name".to_string());
    }
    if team.len() < 2 {
        return Err("invalid team".to_string());
    }
    if level > 3 {
        return Err("level out of range".to_string());
    }
    if score > 100 {
        return Err("score out of range".to_string());
    }

    Ok((name.to_string(), team.to_string(), level, score))
}

fn main() {
    let input = "alice|eng|3|12
bob|hr|1|0
cara|ops|2
dave1|ops|2|10
erin|Ops|2|10
finn|qa|0|10
gail|fin|2|-1
hana|ux|2|7|extra";

    let mut valid = Vec::new();
    let mut invalid = Vec::new();

    for (idx, line) in input.lines().enumerate() {
        match parse_record(line) {
            Ok((name, team, level, score)) => {
                valid.push(format!("{}|{}|{}|{}", name, team, level, score));
            }
            Err(msg) => invalid.push(format!("line {}: {}", idx + 1, msg)),
        }
    }

    println!("VALID {}", valid.len());
    for row in &valid {
        println!("{}", row);
    }
    println!("INVALID {}", invalid.len());
    for row in &invalid {
        println!("{}", row);
    }
}
