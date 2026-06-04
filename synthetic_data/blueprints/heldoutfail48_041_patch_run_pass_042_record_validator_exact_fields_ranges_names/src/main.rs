const INPUT: &str = "u1|alice|30|88|dev
u2|Bob|30|88|dev
u3|carl|17|88|dev
u4|dana|30|101|dev
u5|erin|30|88|Dev
u6|fay|30|88
u7|glen|30|88|ops|extra
u8|ivy-lee|30|88|ops
u9|zoe|65|0|qa
u10|amy|30|088|qa";

fn validate(line: &str) -> Option<String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 5 {
        return None;
    }

    let id = parts[0];
    let name = parts[1];
    let age: i32 = parts[2].parse().ok()?;
    let score: i32 = parts[3].parse().ok()?;
    let team = parts[4];

    if !id.starts_with('u') || id.len() < 2 {
        return None;
    }
    if !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return None;
    }
    if !(18..=65).contains(&age) {
        return None;
    }
    if !(0..=100).contains(&score) {
        return None;
    }
    if team.is_empty() {
        return None;
    }

    Some(id.to_string())
}

fn main() {
    let mut ok = Vec::new();
    let mut err = 0;

    for line in INPUT.lines() {
        match validate(line) {
            Some(id) => ok.push(id),
            None => err += 1,
        }
    }

    println!("OK [{}]", ok.join(","));
    println!("ERR {}", err);
}
