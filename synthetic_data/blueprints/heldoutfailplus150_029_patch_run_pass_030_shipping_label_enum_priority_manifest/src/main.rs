enum Service {
    Standard,
    Express,
    Freight,
    Pickup,
}

enum Zone {
    Domestic,
    International,
}

struct Shipment {
    code: &'static str,
    service: Service,
    zone: Zone,
    hazmat: bool,
    signature: bool,
    hold_at_hub: bool,
    address_ok: bool,
}

fn label(s: &Shipment) -> &'static str {
    match (&s.service, &s.zone) {
        (Service::Pickup, _) => "PICKUP",
        (Service::Express, Zone::International) => "EXPRESS",
        (Service::Freight, _) => "FREIGHT",
        (_, _) if s.hazmat => "HAZMAT",
        (_, _) if s.hold_at_hub => "HOLD",
        (Service::Standard, _) if s.signature => "STANDARD",
        _ => "STANDARD",
    }
}

fn main() {
    let shipments = [
        Shipment {
            code: "A1",
            service: Service::Express,
            zone: Zone::Domestic,
            hazmat: false,
            signature: false,
            hold_at_hub: true,
            address_ok: false,
        },
        Shipment {
            code: "B2",
            service: Service::Express,
            zone: Zone::International,
            hazmat: false,
            signature: true,
            hold_at_hub: false,
            address_ok: true,
        },
        Shipment {
            code: "C3",
            service: Service::Freight,
            zone: Zone::Domestic,
            hazmat: false,
            signature: false,
            hold_at_hub: false,
            address_ok: true,
        },
        Shipment {
            code: "D4",
            service: Service::Standard,
            zone: Zone::Domestic,
            hazmat: true,
            signature: false,
            hold_at_hub: false,
            address_ok: true,
        },
        Shipment {
            code: "E5",
            service: Service::Standard,
            zone: Zone::Domestic,
            hazmat: false,
            signature: true,
            hold_at_hub: false,
            address_ok: true,
        },
        Shipment {
            code: "F6",
            service: Service::Pickup,
            zone: Zone::Domestic,
            hazmat: false,
            signature: false,
            hold_at_hub: false,
            address_ok: true,
        },
    ];

    for s in shipments.iter() {
        println!("{} => {}", s.code, label(s));
    }
}
