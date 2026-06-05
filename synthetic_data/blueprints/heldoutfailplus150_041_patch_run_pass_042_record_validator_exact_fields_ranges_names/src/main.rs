const INPUT: &str = "anna,23,7,ops\nBob,23,7,ops\nmila,17,50,sales\nnoah,30,1000,ops\nzoe,22,15,Sales\nli,40,44,hr\nmila,60,999,sales\nivy, 30,40,ops,extra\nleo,30,-1,ops\n";

fn parse_record(line: &str) -> Result<String, &'static str> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() < 4 {
        return Err("bad_field_count");
    }

    let name = parts[0].trim();
    if name.len() < 3 || !name.chars().all(|c| c.is_alphabetic()) {
        return Err("bad_name");
    }

    let age: i32 = parts[1].trim().parse().map_err(|_| "bad_age")?;
    if age < 18 {
        return Err("bad_age");
    }

    let score: i32 = parts[2].trim().parse().map_err(|_| "bad_score")?;
    if score > 999 {
        return Err("bad_score");
    }

    let dept = parts[3].trim();
    if !dept.chars().all(|c| c.is_alphabetic()) {
        return Err("bad_dept");
    }

    Ok(format!("{}|{}|{}|{}", name, age, score, dept))
}

fn main() {
    let mut ok = Vec::new();
    let mut err = Vec::new();

    for (idx, line) in INPUT.lines().enumerate() {
        match parse_record(line) {
            Ok(v) => ok.push(v),
            Err(e) => err.push(format!("{}:{}", idx + 1, e)),
        }
    }

    println!("OK {}", ok.len());
    for v in ok {
        println!("{}", v);
    }
    println!("ERR {}", err.len());
    for e in err {
        println!("{}", e);
    }
}
