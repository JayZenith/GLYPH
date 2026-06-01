const INPUT: &str = "A100|red|2|hot,new\nB200|blue|0|sale\nBAD!|green|3|ok\nC300|yellow|1|vip\nD400|blue|4|-\nE500|green|5|x, x\nF600|red|1|alpha,beta\n";

fn valid_id(s: &str) -> bool {
    s.len() == 4 && s.chars().all(|c| c.is_ascii_alphanumeric())
}

fn valid_color(s: &str) -> bool {
    matches!(s, "red" | "blue" | "green" | "yellow")
}

fn parse_qty(s: &str) -> Option<u32> {
    s.parse().ok()
}

fn valid_tags(s: &str) -> bool {
    !s.trim().is_empty()
}

fn main() {
    let mut valid = 0;
    let mut invalid = 0;
    let mut lines = Vec::new();

    for row in INPUT.lines() {
        let parts: Vec<&str> = row.split(',').collect();
        if parts.len() != 4 {
            invalid += 1;
            lines.push(format!("{}:bad_fields", row));
            continue;
        }

        let id = parts[0];
        let color = parts[1];
        let qty = parts[2];
        let tags = parts[3];

        let status = if !valid_id(id) {
            "bad_id"
        } else if !valid_color(color) {
            "bad_color"
        } else if parse_qty(qty).unwrap_or(0) < 0 {
            "bad_qty"
        } else if !valid_tags(tags) {
            "bad_tags"
        } else {
            "ok"
        };

        if status == "ok" {
            valid += 1;
        } else {
            invalid += 1;
        }
        lines.push(format!("{}:{}", id, status));
    }

    println!("valid={} invalid={}", valid, invalid);
    for line in lines {
        println!("{}", line);
    }
}
