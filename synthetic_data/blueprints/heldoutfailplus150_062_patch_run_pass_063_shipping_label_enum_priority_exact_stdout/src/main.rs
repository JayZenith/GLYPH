enum Speed {
    Ground,
    Air,
    Overnight,
}

enum Route {
    Local,
    International,
    Pickup,
}

enum Cargo {
    Standard,
    Fragile,
    Frozen,
    Hazmat,
    Bulky,
}

struct Shipment {
    name: &'static str,
    speed: Speed,
    route: Route,
    cargo: Cargo,
}

fn label(s: &Shipment) -> &'static str {
    match (&s.route, &s.speed, &s.cargo) {
        (Route::International, _, _) => "EXPORT",
        (_, _, Cargo::Hazmat) => "HAZARD",
        (_, _, Cargo::Frozen) => "COLD",
        (_, _, Cargo::Bulky) => "GROUND",
        (Route::Pickup, _, _) => "PICKUP",
        (_, Speed::Overnight, _) => "OVERNIGHT",
        (_, Speed::Air, _) => "AIR",
        _ => "GROUND",
    }
}

fn main() {
    let shipments = [
        Shipment {
            name: "overnight-frozen",
            speed: Speed::Overnight,
            route: Route::Local,
            cargo: Cargo::Frozen,
        },
        Shipment {
            name: "international-hazmat",
            speed: Speed::Air,
            route: Route::International,
            cargo: Cargo::Hazmat,
        },
        Shipment {
            name: "local-bulky",
            speed: Speed::Ground,
            route: Route::Local,
            cargo: Cargo::Bulky,
        },
        Shipment {
            name: "overnight-standard",
            speed: Speed::Overnight,
            route: Route::Local,
            cargo: Cargo::Standard,
        },
        Shipment {
            name: "pickup-fragile",
            speed: Speed::Ground,
            route: Route::Pickup,
            cargo: Cargo::Fragile,
        },
        Shipment {
            name: "international-standard",
            speed: Speed::Ground,
            route: Route::International,
            cargo: Cargo::Standard,
        },
        Shipment {
            name: "local-standard",
            speed: Speed::Ground,
            route: Route::Local,
            cargo: Cargo::Standard,
        },
        Shipment {
            name: "unknown",
            speed: Speed::Air,
            route: Route::Pickup,
            cargo: Cargo::Hazmat,
        },
    ];

    for s in shipments.iter() {
        println!("{} => {}", s.name, label(s));
    }
}
