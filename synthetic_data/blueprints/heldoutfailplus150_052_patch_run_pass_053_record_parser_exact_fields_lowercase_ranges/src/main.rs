fn valid_name(name: &str) -> bool {
    !name.is_empty() && name.chars().all(|c| c.is_ascii_alphabetic())
}

fn valid_code(code: &str) -> bool {
    code.len() >= 2 && code.chars().all(|c| c.is_ascii_alphanumeric())
}

fn parse_line(line: &str) -> Result<(String, u32, u32, String), String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 4 {
        return Err("field-count".into());
    }

    let name = parts[0];
    let id: u32 = parts[1].parse().map_err(|_| "id")?;
    let score: u32 = parts[2].parse().map_err(|_| "score")?;
    let code = parts[3];

    if !valid_name(name) {
        return Err("name".into());
    }
    if id < 100 || id > 200 {
        return Err("id-range".into());
    }
    if score > 100 {
        return Err("score-range".into());
    }
    if !valid_code(code) {
        return Err("code".into());
    }

    Ok((name.to_string(), id, score, code.to_string()))
}

fn main() {
    let input = [
        "aaron|199|88|xz",
        "Bob|101|50|ok",
        "clara|200|0|xy",
        "dave|99|75|toolong",
        "erin|150|42",
        "frank|150|42|q1",
        "gina|150|101|zz",
        "hank|abc|70|mn",
        "ivy|120|33|mN",
        "jo|100|1|ab|extra",
        "zoe|100|1|aa",
    ];

    for line in input {
        match parse_line(line) {
            Ok((name, id, score, code)) => println!("ACCEPT {} {} {} {}", name, id, score, code),
            Err(_) => println!("REJECT {}", line),
        }
    }
}
