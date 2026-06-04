enum Speed {
    Ground,
    Air,
    Sea,
}

enum Shipment {
    Standard { parcel: &'static str, speed: Speed },
    Priority { parcel: &'static str, speed: Speed },
    Bulk { parcel: &'static str, speed: Speed },
    Oversize { parcel: &'static str, speed: Speed },
    International { parcel: &'static str, speed: Speed },
}

fn kind_and_command(shipment: &Shipment) -> (&'static str, &'static str) {
    match shipment {
        Shipment::Priority { .. } => ("PRIORITY", "LOAD-STANDARD"),
        Shipment::Oversize { .. } => ("OVERSIZE", "FREIGHT"),
        Shipment::Bulk { .. } => ("BULK", "LOAD-BULK"),
        Shipment::International { .. } => ("INTERNATIONAL", "CUSTOMS"),
        Shipment::Standard { .. } => ("STANDARD", "LOAD-STANDARD"),
    }
}

fn speed_name(speed: &Speed) -> &'static str {
    match speed {
        Speed::Ground => "ground",
        Speed::Air => "air",
        Speed::Sea => "sea",
    }
}

fn render(shipment: &Shipment) -> String {
    let (kind, command) = kind_and_command(shipment);
    match shipment {
        Shipment::Standard { parcel, speed }
        | Shipment::Priority { parcel, speed }
        | Shipment::Bulk { parcel, speed }
        | Shipment::Oversize { parcel, speed }
        | Shipment::International { parcel, speed } => {
            format!("{} | parcel={} | speed={} | command={}", kind, parcel, speed_name(speed), command)
        }
    }
}

fn main() {
    let shipments = [
        Shipment::Priority { parcel: "BOOKS", speed: Speed::Air },
        Shipment::Oversize { parcel: "SOFA", speed: Speed::Ground },
        Shipment::Bulk { parcel: "RICE", speed: Speed::Sea },
        Shipment::Standard { parcel: "CABLES", speed: Speed::Ground },
        Shipment::International { parcel: "TEA", speed: Speed::Air },
        Shipment::Standard { parcel: "BOLTS", speed: Speed::Sea },
    ];

    for shipment in shipments.iter() {
        println!("{}", render(shipment));
    }
}
