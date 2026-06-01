struct Booking {
    name: &'static str,
    start: u32,
    end: u32,
}

fn overlaps(a: &Booking, b: &Booking) -> bool {
    a.start <= b.end && b.start <= a.end
}

fn main() {
    let requests = vec![
        Booking { name: "alpha", start: 540, end: 600 },
        Booking { name: "beta", start: 600, end: 630 },
        Booking { name: "gamma", start: 590, end: 610 },
        Booking { name: "delta", start: 630, end: 660 },
        Booking { name: "epsilon", start: 700, end: 700 },
    ];

    let mut accepted: Vec<Booking> = Vec::new();
    let mut rejected: Vec<String> = Vec::new();

    for req in requests {
        let mut conflict_with: Option<&'static str> = None;
        for existing in &accepted {
            if overlaps(&req, existing) {
                conflict_with = Some(existing.name);
            }
        }

        if let Some(name) = conflict_with {
            rejected.push(format!("{} -> conflicts with {}", req.name, name));
        } else if req.start > req.end {
            rejected.push(format!("{} -> invalid interval", req.name));
        } else {
            accepted.push(req);
        }
    }

    println!("accepted: {}", accepted.iter().map(|b| b.name).collect::<Vec<_>>().join(", "));
    for line in rejected {
        println!("{}", line);
    }
}
