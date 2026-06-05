fn valid_record(line: &str) -> Option<String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return None;
    }

    let name = parts[0].trim();
    let dept = parts[1].trim();
    let level: i32 = parts[2].trim().parse().ok()?;
    let score: i32 = parts[3].trim().parse().ok()?;

    if name.is_empty() {
        return None;
    }
    if !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return None;
    }
    if dept.is_empty() {
        return None;
    }
    if !(1..=5).contains(&level) {
        return None;
    }
    if score < 0 {
        return None;
    }

    Some(name.to_string())
}

fn main() {
    let input = [
        "alice|eng|3|88",
        "bob|sales|2|70",
        "carol|ops|0|50",
        "dave|qa|4|101",
        "eve|eng|2",
        "frank|ops|2|40|extra",
        "Gina|eng|3|77",
        "henry7|qa|3|60",
        "ivy|ops|5|100",
        "jane||2|60",
        "kate|qa|1|-1",
        "leo|eng|1|90x",
        "mona|qa|1|0",
    ];

    let accepted: Vec<String> = input.into_iter().filter_map(valid_record).collect();
    println!("{:?}", accepted);
}
