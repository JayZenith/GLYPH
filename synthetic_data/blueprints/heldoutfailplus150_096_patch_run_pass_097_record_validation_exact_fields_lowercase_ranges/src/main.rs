fn parse_record(line: &str) -> Result<(String, u32, u8), String> {
    let parts: Vec<&str> = line.split(':').collect();
    if parts.len() < 3 {
        return Err("expected 3 fields".to_string());
    }

    let name = parts[0].trim();
    if name.is_empty() {
        return Err("empty name".to_string());
    }
    if !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return Err("invalid lowercase name".to_string());
    }

    let score = parts[1]
        .trim()
        .parse::<u32>()
        .map_err(|_| "invalid score".to_string())?;

    let level = parts[2]
        .trim()
        .parse::<u8>()
        .map_err(|_| "invalid level".to_string())?;

    Ok((name.to_string(), score, level))
}

fn main() {
    let input = "alpha:10:2\nsolo:5\n:3:1\nzoe:0:1\nBeta:20:3\nmira:101:4\nrex:50:0\nivy:xx:2\nneo:30:two\nmira:99:4";

    let mut valid = Vec::new();
    let mut invalid = Vec::new();

    for (idx, line) in input.lines().enumerate() {
        match parse_record(line) {
            Ok((name, score, level)) => valid.push(format!("{}:{}:{}", name, score, level)),
            Err(msg) => invalid.push(format!("line {}: {}", idx + 1, msg)),
        }
    }

    println!("valid:{}", valid.len());
    for row in &valid {
        println!("{}", row);
    }
    println!("invalid:{}", invalid.len());
    for row in &invalid {
        println!("{}", row);
    }
}
