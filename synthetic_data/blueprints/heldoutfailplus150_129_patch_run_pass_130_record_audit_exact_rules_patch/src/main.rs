const INPUT: &str = "1001|alice|34|88|true|na
1002|bob|29|91|false
0999|carol|41|77|true|eu
1003|Dan|30|64|true|ap
1004|erin|17|70|false|sa
1005|faye|22|101|true|eu
1006|gina|28|55|yes|na
1007|zoe|65|100|false|ap
1008|mira|18|0|true|eu
1009|ivy-lee|44|90|true|sa
1010|otto|38|82|false|xx
1011|li|26|73|true|na|extra";

fn validate_line(line: &str) -> Result<String, &'static str> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 6 {
        return Err("bad field count");
    }

    let id = parts[0];
    if id.parse::<u32>().is_err() {
        return Err("invalid id");
    }

    let name = parts[1];
    if name.len() < 2 || !name.chars().all(|c| c.is_ascii_alphabetic() || c == '-') {
        return Err("invalid name");
    }

    let age = parts[2].parse::<u32>().map_err(|_| "invalid age")?;
    if age == 0 || age > 120 {
        return Err("invalid age");
    }

    let score = parts[3].parse::<u32>().map_err(|_| "invalid score")?;
    if score > 100 {
        return Err("invalid score");
    }

    let active = parts[4];
    if active != "true" && active != "false" {
        return Err("invalid active");
    }

    let region = parts[5];
    if region.len() != 2 {
        return Err("invalid region");
    }

    Ok(name.to_string())
}

fn main() {
    let mut valid_names = Vec::new();
    let mut invalids = Vec::new();

    for (idx, line) in INPUT.lines().enumerate() {
        match validate_line(line) {
            Ok(name) => valid_names.push(name),
            Err(msg) => invalids.push(format!("line {}: {}", idx + 1, msg)),
        }
    }

    println!("valid: {}", valid_names.len());
    for name in valid_names {
        println!("{}:ok", name);
    }
    println!("invalid: {}", invalids.len());
    for msg in invalids {
        println!("{}", msg);
    }
}
