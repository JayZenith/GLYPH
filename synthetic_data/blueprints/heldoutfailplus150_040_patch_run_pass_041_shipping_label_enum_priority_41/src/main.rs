enum Route {
    Direct,
    Hub,
    Return,
}

enum Customs {
    Cleared,
    Hold,
    Missing,
}

struct Shipment {
    code: &'static str,
    route: Route,
    fragile: bool,
    oversize: bool,
    express: bool,
    customs: Customs,
}

fn command_label(s: &Shipment) -> &'static str {
    match (&s.route, &s.customs, s.fragile, s.oversize, s.express) {
        (Route::Return, _, _, _, _) => "RETURN: sender review",
        (_, Customs::Hold, _, _, _) => "CUSTOMS: wait",
        (_, Customs::Missing, _, _, _) => "CUSTOMS: docs needed",
        (_, _, true, _, _) => "FRAGILE: careful handling",
        (_, _, _, true, _) => "BULK: pallet lane",
        (Route::Direct, Customs::Cleared, _, _, true) => "EXPRESS: route direct",
        _ => "STANDARD: sort",
    }
}

fn main() {
    let shipments = [
        Shipment {
            code: "A1",
            route: Route::Hub,
            fragile: false,
            oversize: false,
            express: false,
            customs: Customs::Hold,
        },
        Shipment {
            code: "B2",
            route: Route::Hub,
            fragile: true,
            oversize: true,
            express: false,
            customs: Customs::Cleared,
        },
        Shipment {
            code: "C3",
            route: Route::Return,
            fragile: true,
            oversize: false,
            express: true,
            customs: Customs::Cleared,
        },
        Shipment {
            code: "D4",
            route: Route::Direct,
            fragile: false,
            oversize: false,
            express: true,
            customs: Customs::Cleared,
        },
        Shipment {
            code: "E5",
            route: Route::Hub,
            fragile: false,
            oversize: true,
            express: false,
            customs: Customs::Cleared,
        },
        Shipment {
            code: "F6",
            route: Route::Hub,
            fragile: false,
            oversize: false,
            express: false,
            customs: Customs::Missing,
        },
    ];

    for s in shipments {
        println!("{} => {}", s.code, command_label(&s));
    }
}
