enum Service {
    Ground,
    Express,
    Freight,
    Pickup,
}

enum Zone {
    Domestic,
    International,
    Local,
}

struct Shipment {
    code: &'static str,
    service: Service,
    zone: Zone,
    hold_at_hub: bool,
    signature_required: bool,
    customs_cleared: bool,
}

fn label(s: &Shipment) -> &'static str {
    match (&s.service, &s.zone) {
        (Service::Pickup, _) => "PICKUP",
        (Service::Ground, _) => "GROUND",
        (Service::Express, Zone::International) => "EXPRESS-INTL",
        (Service::Express, _) => "EXPRESS",
        (Service::Freight, Zone::International) => "FREIGHT-INTL",
        (Service::Freight, _) => "FREIGHT",
    }
}

fn main() {
    let shipments = [
        Shipment {
            code: "PKG-1",
            service: Service::Express,
            zone: Zone::International,
            hold_at_hub: true,
            signature_required: false,
            customs_cleared: true,
        },
        Shipment {
            code: "PKG-2",
            service: Service::Ground,
            zone: Zone::Domestic,
            hold_at_hub: false,
            signature_required: true,
            customs_cleared: true,
        },
        Shipment {
            code: "PKG-3",
            service: Service::Express,
            zone: Zone::Local,
            hold_at_hub: false,
            signature_required: false,
            customs_cleared: true,
        },
        Shipment {
            code: "PKG-4",
            service: Service::Pickup,
            zone: Zone::Domestic,
            hold_at_hub: true,
            signature_required: true,
            customs_cleared: true,
        },
        Shipment {
            code: "PKG-5",
            service: Service::Freight,
            zone: Zone::International,
            hold_at_hub: false,
            signature_required: true,
            customs_cleared: false,
        },
        Shipment {
            code: "PKG-6",
            service: Service::Freight,
            zone: Zone::Domestic,
            hold_at_hub: false,
            signature_required: false,
            customs_cleared: false,
        },
    ];

    for s in shipments.iter() {
        println!("{} => {}", s.code, label(s));
    }
}
