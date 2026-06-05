const INPUT: &str = "alice|dev|34|72\nBob|ops|28|88\ncarol|qa|41|100\ndave|dev|17|55\nerin|sales|66|70\nfrank|ops|40|101\ngina|dev|32\nhank|dev|32|70|extra\nivy|support|30|40\njack|qa|30|070\nkate|ops|30|0\nliz|ops|30|99\nmike|dev|30|9x\nnoah|dev|-2|50\n";

fn parse_valid_names(input: &str) -> Vec<String> {
    let mut out = Vec::new();
    for line in input.lines() {
        if line.trim().is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 4 {
            continue;
        }

        let name = parts[0].trim();
        let dept = parts[1].trim();
        let age: i32 = match parts[2].trim().parse() {
            Ok(v) => v,
            Err(_) => continue,
        };
        let score: i32 = match parts[3].trim().parse() {
            Ok(v) => v,
            Err(_) => continue,
        };

        if !name.chars().all(|c| c.is_ascii_alphabetic()) {
            continue;
        }
        if dept.is_empty() {
            continue;
        }
        if !(18..=65).contains(&age) {
            continue;
        }
        if !(0..=100).contains(&score) {
            continue;
        }

        out.push(name.to_string());
    }
    out
}

fn main() {
    let names = parse_valid_names(INPUT);
    println!("ACCEPTED {}", names.len());
    for name in names {
        println!("{}", name);
    }
}
