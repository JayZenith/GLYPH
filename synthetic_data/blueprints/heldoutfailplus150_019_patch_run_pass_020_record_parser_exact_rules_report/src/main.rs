const INPUT: &str = "1001|alice|eng|7|true\n1002|Bob|eng|4|false\n0999|zoe|ops|3|true\n1003|mia|sales|11|true\n1004|ivy|qa|8\n1005|liam|ops|2|TRUE\n1006|noah|support|4|false\n1007|eve-2|eng|5|true\n1008|otto|hr|0|false";

fn validate_line(line: &str) -> Result<(u32, String, String, u8, bool), &'static str> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 5 {
        return Err("bad field count");
    }

    let id: u32 = parts[0].parse().map_err(|_| "invalid id")?;
    if id == 0 {
        return Err("invalid id");
    }

    let name = parts[1];
    if name.is_empty() || !name.chars().all(|c| c.is_ascii_alphanumeric()) {
        return Err("invalid name");
    }

    let team = parts[2];
    if team.is_empty() {
        return Err("invalid team");
    }

    let score: u8 = parts[3].parse().map_err(|_| "invalid score")?;
    if score > 10 {
        return Err("invalid score");
    }

    let active = match parts[4] {
        "true" | "TRUE" => true,
        "false" | "FALSE" => false,
        _ => return Err("invalid active"),
    };

    Ok((id, name.to_string(), team.to_string(), score, active))
}

fn main() {
    let mut valid = Vec::new();
    let mut invalid = Vec::new();

    for (idx, line) in INPUT.lines().enumerate() {
        match validate_line(line) {
            Ok((_, name, team, score, _)) => valid.push(format!("{}:{}:{}", name, team, score)),
            Err(msg) => invalid.push(format!("line{}: {}", idx + 1, msg)),
        }
    }

    println!("valid:{}", valid.len());
    for v in valid {
        println!("{}", v);
    }
    println!("invalid:{}", invalid.len());
    for e in invalid {
        println!("{}", e);
    }
}
