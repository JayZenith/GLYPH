enum Route {
    Ground,
    Express,
    International,
    Freight,
    Pickup,
}

enum Note {
    None,
    Signature,
    Hazmat,
    Liftgate,
    Desk,
    Customs,
}

struct Shipment {
    id: &'static str,
    route: Route,
    weekend: bool,
    remote: bool,
    note: Note,
}

fn label(s: &Shipment) -> String {
    let route = match s.route {
        Route::Ground => {
            if s.remote {
                "GROUND-REMOTE"
            } else {
                "GROUND"
            }
        }
        Route::Express => {
            if s.weekend {
                "EXPRESS-SAT"
            } else {
                "EXPRESS"
            }
        }
        Route::International => "INTL",
        Route::Freight => {
            if s.remote {
                "FREIGHT-REMOTE"
            } else {
                "FREIGHT"
            }
        }
        Route::Pickup => "PICKUP",
    };

    let suffix = match s.note {
        Note::None => "NONE",
        Note::Signature => "SIG",
        Note::Hazmat => "HAZMAT",
        Note::Liftgate => "LIFTGATE",
        Note::Desk => "DESK",
        Note::Customs => "CUSTOMS",
    };

    format!("{} {} [{}]", s.id, route, suffix)
}

fn main() {
    let shipments = [
        Shipment {
            id: "R1",
            route: Route::Express,
            weekend: false,
            remote: false,
            note: Note::Hazmat,
        },
        Shipment {
            id: "R2",
            route: Route::Express,
            weekend: true,
            remote: false,
            note: Note::Signature,
        },
        Shipment {
            id: "R3",
            route: Route::International,
            weekend: false,
            remote: false,
            note: Note::Customs,
        },
        Shipment {
            id: "R4",
            route: Route::Freight,
            weekend: false,
            remote: true,
            note: Note::Liftgate,
        },
        Shipment {
            id: "R5",
            route: Route::Pickup,
            weekend: false,
            remote: false,
            note: Note::Desk,
        },
        Shipment {
            id: "R6",
            route: Route::Ground,
            weekend: false,
            remote: false,
            note: Note::None,
        },
    ];

    for s in shipments {
        println!("{}", label(&s));
    }
}
