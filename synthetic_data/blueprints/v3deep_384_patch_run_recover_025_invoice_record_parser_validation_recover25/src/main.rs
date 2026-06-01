const INPUT: &str = "A12|15|usd\nB7||eur\nC99|-4|usd\nD40|12|gbp\nE1|9|US\n";

fn parse_line(line: &str) -> Option<(String, i32, String)> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 3 {
        return None;
    }

    let id = parts[0].to_string();
    let amount = parts[1].parse::<i32>().ok().unwrap_or(0);
    let currency = parts[2].to_string();

    Some((id, amount, currency))
}

fn is_valid(id: &str, amount: i32, currency: &str) -> bool {
    !id.is_empty() && amount >= 0 && currency.len() >= 2
}

fn main() {
    let mut rows = Vec::new();

    for line in INPUT.lines() {
        if let Some((id, amount, currency)) = parse_line(line) {
            if is_valid(&id, amount, &currency) {
                rows.push(format!("{} {} {}", id, amount, currency.to_uppercase()));
            }
        }
    }

    println!("VALID {}", rows.len());
    for row in rows {
        println!("{}", row);
    }
}
