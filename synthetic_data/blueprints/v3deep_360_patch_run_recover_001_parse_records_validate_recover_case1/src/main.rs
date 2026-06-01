const INPUT: &str = r#"
# name|age|role
Alice|34|Admin
Bob|17|user
Cara|29|moderator
Dana|65| User 
Eve|x|guest
Frank|18|guest|extra
 |22|admin
Frank|18|guest
Gina|40|ADMIN
"#;

fn parse_line(line: &str) -> Option<String> {
    let line = line.trim();
    if line.is_empty() || line.starts_with('#') {
        return None;
    }

    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 3 {
        return None;
    }

    let name = parts[0];
    let age: u8 = parts[1].parse().ok()?;
    let role = parts[2];

    if name.is_empty() {
        return None;
    }

    Some(format!("{}:{}:{}", name.to_uppercase(), age, role.to_lowercase()))
}

fn main() {
    let mut out = Vec::new();
    for line in INPUT.lines() {
        if let Some(row) = parse_line(line) {
            out.push(row);
        }
    }
    print!("{}", out.join("\n"));
}
