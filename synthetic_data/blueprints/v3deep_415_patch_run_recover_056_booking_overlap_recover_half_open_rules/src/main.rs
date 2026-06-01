fn overlaps(a: (u32, u32), b: (u32, u32)) -> bool {
    a.0 <= b.1 && b.0 <= a.1
}

fn status(room: &str, existing: &[(u32, u32)], request: (u32, u32)) -> String {
    let has_conflict = existing.iter().any(|&slot| overlaps(slot, request));
    format!("{}: {}", room, if has_conflict { "blocked" } else { "open" })
}

fn main() {
    let cases = [
        ("Room A", vec![(9, 11), (13, 15)], (10, 12)),
        ("Room B", vec![(9, 11), (13, 15)], (11, 13)),
        ("Room C", vec![(8, 10)], (10, 12)),
        ("Room D", vec![(14, 16)], (12, 14)),
    ];

    for (room, existing, request) in cases {
        println!("{}", status(room, &existing, request));
    }
}
