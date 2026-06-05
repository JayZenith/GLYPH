const INPUT: &str = "anna,4,north\nZoe,3,south\nmax,0,east\nmila,2,west\nnoah,5,south,extra\nivy,3,north\nli,2,east\noval,2,West\n";

fn parse_valid(line: &str) -> Option<(String, u32, String)> {
    let parts: Vec<&str> = line.split(',').collect();
    if parts.len() < 3 {
        return None;
    }

    let name = parts[0].trim();
    let level: u32 = parts[1].trim().parse().ok()?;
    let region = parts[2].trim();

    if name.len() < 2 {
        return None;
    }
    if level > 5 {
        return None;
    }
    if region != "north" && region != "south" && region != "east" && region != "west" {
        return None;
    }

    Some((name.to_string(), level, region.to_string()))
}

fn main() {
    let mut rows = Vec::new();
    for line in INPUT.lines() {
        if let Some((name, level, region)) = parse_valid(line) {
            rows.push(format!("{}|{}|{}", name, region, level));
        }
    }

    println!("VALID {}", rows.len());
    for row in rows {
        println!("{}", row);
    }
}
