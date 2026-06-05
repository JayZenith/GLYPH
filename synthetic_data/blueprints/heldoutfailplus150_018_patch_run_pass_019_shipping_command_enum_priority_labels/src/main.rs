enum Speed {
    Standard,
    Express,
}

enum Route {
    Domestic,
    International,
    Return,
}

enum Handling {
    Normal,
    Fragile,
    Oversize,
}

struct Shipment {
    speed: Option<Speed>,
    route: Route,
    handling: Handling,
}

fn label(s: &Shipment) -> String {
    let head = match s.speed {
        Some(Speed::Express) => "EXPRESS",
        Some(Speed::Standard) => "STANDARD",
        None => match s.route {
            Route::International => "INTERNATIONAL",
            Route::Return => "RETURN",
            Route::Domestic => "UNKNOWN",
        },
    };

    match s.handling {
        Handling::Normal => head.to_string(),
        Handling::Fragile => format!("{}+FRAGILE", head),
        Handling::Oversize => format!("{}+OVERSIZE", head),
    }
}

fn action(s: &Shipment) -> &'static str {
    match (&s.speed, &s.route, &s.handling) {
        (Some(Speed::Express), _, _) => "air-dispatch",
        (Some(Speed::Standard), _, _) => "ground-batch",
        (_, Route::International, _) => "priority-air",
        (_, Route::Return, _) => "reverse-logistics",
        (_, _, Handling::Fragile) => "inspect-wrap",
        (_, _, Handling::Oversize) => "freight-schedule",
        _ => "manual-triage",
    }
}

fn main() {
    let shipments = [
        Shipment {
            speed: Some(Speed::Express),
            route: Route::Domestic,
            handling: Handling::Normal,
        },
        Shipment {
            speed: Some(Speed::Express),
            route: Route::Domestic,
            handling: Handling::Fragile,
        },
        Shipment {
            speed: Some(Speed::Standard),
            route: Route::Domestic,
            handling: Handling::Normal,
        },
        Shipment {
            speed: Some(Speed::Standard),
            route: Route::Domestic,
            handling: Handling::Oversize,
        },
        Shipment {
            speed: None,
            route: Route::International,
            handling: Handling::Normal,
        },
        Shipment {
            speed: Some(Speed::Express),
            route: Route::International,
            handling: Handling::Normal,
        },
        Shipment {
            speed: None,
            route: Route::Return,
            handling: Handling::Normal,
        },
        Shipment {
            speed: None,
            route: Route::Return,
            handling: Handling::Fragile,
        },
        Shipment {
            speed: None,
            route: Route::Domestic,
            handling: Handling::Normal,
        },
    ];

    for s in shipments.iter() {
        println!("{} -> {}", label(s), action(s));
    }
}
