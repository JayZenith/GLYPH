fn parse_line(line: &str) -> Option<String> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 3 {
        return None;
    }

    let id = parts[0];
    let name = parts[1];
    let score: i32 = parts[2].parse().ok()?;

    if id.is_empty() || name.is_empty() {
        return None;
    }

    Some(format!("{}:{}:{}", id, name, score))
}

fn main() {
    let input = "101|Alice|88
BAD|Bob|91
102||77
103|Carol|100
104|Dora|0
105|Eve|101
106|Frank|72
107|Grace|50|extra
108|Heidi|x";

    let output = input
        .lines()
        .filter_map(parse_line)
        .collect::<Vec<_>>()
        .join("\n");

    println!("{}", output);
}
