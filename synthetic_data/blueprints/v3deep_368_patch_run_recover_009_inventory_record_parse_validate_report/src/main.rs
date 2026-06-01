const INPUT: &str = "A12|widget|5\nB1|bad qty|x\nC07|bolt|2|extra\nD09|gizmo|4\nAA3|bad code|7\nE11|spare part|0\nC07|bolt|2\n";

#[derive(Debug)]
struct Item {
    code: String,
    name: String,
    qty: u32,
}

fn parse_line(line: &str) -> Result<Item, &'static str> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 3 {
        return Err("field count");
    }

    let code = parts[0].trim();
    if code.len() != 3 || !code.chars().all(|c| c.is_ascii_alphanumeric()) {
        return Err("code");
    }

    let name = parts[1].trim();
    if name.is_empty() {
        return Err("name");
    }

    let qty: u32 = parts[2].trim().parse().map_err(|_| "qty")?;

    Ok(Item {
        code: code.to_string(),
        name: name.to_string(),
        qty,
    })
}

fn main() {
    let mut valid = Vec::new();
    let mut invalid = 0;

    for line in INPUT.lines() {
        match parse_line(line) {
            Ok(item) => valid.push(item),
            Err(_) => invalid += 1,
        }
    }

    println!("valid: {}", valid.len());
    for item in valid {
        println!("{}:{}:{}", item.code, item.name, item.qty);
    }
    println!("invalid: {}", invalid);
}
