const INPUT: &str = "anna,ops,34,72\nBob,ops,41,70\nmila,eng,29,88\nzoe,sales,17,55\nliam,ops,22,101\nnoah,hr,33,77\nivy,eng,44\nmax1,ops,26,60\na,ops,26,60\nvera,eng,xx,90\nomar,ops,40,ninety\n";

fn validate_line(line: &str) -> Result<(String, String, u32, u32), String> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() < 4 {
        return Err("field_count".to_string());
    }

    let name = parts[0];
    let dept = parts[1];
    let age: u32 = parts[2].parse().map_err(|_| "age_parse".to_string())?;
    let score: u32 = parts[3].parse().map_err(|_| "score_parse".to_string())?;

    if !name.chars().all(|c| c.is_ascii_alphabetic()) {
        return Err("bad_name".to_string());
    }
    if dept != "ops" && dept != "eng" && dept != "sales" {
        return Err("bad_dept".to_string());
    }
    if age < 18 || age > 99 {
        return Err("age_range".to_string());
    }
    if score > 100 {
        return Err("score_range".to_string());
    }

    Ok((name.to_string(), dept.to_string(), age, score))
}

fn main() {
    let mut valid = Vec::new();
    let mut invalid = Vec::new();

    for (i, line) in INPUT.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        match validate_line(line) {
            Ok((name, dept, age, score)) => {
                valid.push(format!("{}|{}|{}|{}", name, dept, age, score));
            }
            Err(reason) => invalid.push(format!("{}: {}", i + 1, reason)),
        }
    }

    println!("VALID {}", valid.len());
    for v in &valid {
        println!("{}", v);
    }
    println!("INVALID {}", invalid.len());
    for e in &invalid {
        println!("{}", e);
    }
}
