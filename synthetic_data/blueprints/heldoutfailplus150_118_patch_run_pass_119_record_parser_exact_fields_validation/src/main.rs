const INPUT: &str = "101|alice|88|gold\n222|bob|0|bronze\n99|cara|70|silver\n333|Eve|50|gold\n444|zoe|100|silver\n555|max9|42|bronze\n666|ann|101|gold\n777|ivy|10|platinum\n888|li|20|silver\n999|mila|40|gold|extra";

fn parse_record(line: &str) -> Option<(u32, String, u32, String)> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return None;
    }

    let id = parts[0].parse::<u32>().ok()?;
    let name = parts[1];
    let score = parts[2].parse::<u32>().ok()?;
    let tier = parts[3];

    if id == 0 {
        return None;
    }
    if name.is_empty() {
        return None;
    }
    if score > 100 {
        return None;
    }
    if tier.is_empty() {
        return None;
    }

    Some((id, name.to_string(), score, tier.to_string()))
}

fn main() {
    let mut accepted = Vec::new();
    let mut rejected = 0usize;

    for line in INPUT.lines() {
        match parse_record(line) {
            Some((id, name, score, tier)) => accepted.push(format!("{}:{}:{}:{}", id, name, score, tier)),
            None => rejected += 1,
        }
    }

    println!("ACCEPTED");
    for row in &accepted {
        println!("{}", row);
    }
    println!("SUMMARY accepted={} rejected={}", accepted.len(), rejected);
}
