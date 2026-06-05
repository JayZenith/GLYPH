const INPUT: &str = "alpha|10|3|xray\nBeta|10|3|xray\nbeta|100|1|yankee\ngamma|0|2|zulu\ndelta|50|5|xray\nepsilon|77|2|Zulu\nzeta|42|4|zulu\neta|12|3\ntheta|30|2|xray|extra\niota|9|2|xray\nkappa|55|2|xeno\nlambda|88|0|xerox";

#[derive(Debug)]
struct Record {
    name: String,
    score: u32,
    level: u32,
    tag: String,
}

fn parse_line(line: &str) -> Option<Record> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return None;
    }

    let name = parts[0];
    let score: u32 = parts[1].parse().ok()?;
    let level: u32 = parts[2].parse().ok()?;
    let tag = parts[3];

    if name.is_empty() || !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return None;
    }
    if score > 99 {
        return None;
    }
    if !(1..=5).contains(&level) {
        return None;
    }
    if tag.len() < 4 || !tag.chars().all(|c| c.is_ascii_alphabetic()) {
        return None;
    }

    Some(Record {
        name: name.to_string(),
        score,
        level,
        tag: tag.to_string(),
    })
}

fn main() {
    let mut valid = Vec::new();
    let mut invalid = 0usize;

    for line in INPUT.lines() {
        match parse_line(line) {
            Some(r) => valid.push(r),
            None => invalid += 1,
        }
    }

    println!("valid:{} invalid:{}", valid.len(), invalid);
    for r in valid {
        println!("OK {} {} {} {}", r.name, r.score, r.level, r.tag);
    }
}
