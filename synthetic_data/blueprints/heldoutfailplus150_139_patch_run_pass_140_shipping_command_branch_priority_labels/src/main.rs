#[derive(Clone, Copy)]
enum Speed {
    Standard,
    Express,
    Overnight,
}

#[derive(Clone, Copy)]
enum Package {
    Envelope,
    Box,
    Tube,
    Crate,
}

#[derive(Clone, Copy)]
struct Shipment {
    speed: Speed,
    package: Package,
    fragile: bool,
    oversize: bool,
    international: bool,
    return_to_sender: bool,
    hazmat: bool,
}

fn label(s: Shipment) -> &'static str {
    match s.package {
        Package::Envelope => "DOC-MAIL",
        Package::Tube => "TUBE",
        Package::Crate => "FREIGHT",
        Package::Box => match s.speed {
            Speed::Express => "EXPRESS-BOX",
            Speed::Overnight => "OVERNIGHT-BOX",
            Speed::Standard => "PARCEL",
        },
    }
}

fn describe(s: Shipment) -> String {
    let mut parts = Vec::new();
    if s.return_to_sender {
        parts.push("RETURN");
    }
    if s.international {
        parts.push("INTERNATIONAL");
    }
    if s.fragile {
        parts.push("FRAGILE");
    }
    if s.oversize {
        parts.push("OVERSIZE");
    }
    if s.hazmat {
        parts.push("HAZMAT");
    }
    parts.push(match s.speed {
        Speed::Standard => "STANDARD",
        Speed::Express => "EXPRESS",
        Speed::Overnight => "OVERNIGHT",
    });
    parts.push(match s.package {
        Package::Envelope => "ENVELOPE",
        Package::Box => "BOX",
        Package::Tube => "TUBE",
        Package::Crate => "CRATE",
    });
    parts.join(" ")
}

fn main() {
    let shipments = [
        Shipment { speed: Speed::Express, package: Package::Box, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Express, package: Package::Tube, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Overnight, package: Package::Box, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Overnight, package: Package::Envelope, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Envelope, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Crate, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Box, fragile: false, oversize: false, international: false, return_to_sender: true, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Envelope, fragile: false, oversize: false, international: false, return_to_sender: true, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Box, fragile: false, oversize: false, international: true, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Envelope, fragile: false, oversize: false, international: true, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Envelope, fragile: false, oversize: false, international: true, return_to_sender: true, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Box, fragile: false, oversize: true, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Box, fragile: true, oversize: true, international: false, return_to_sender: false, hazmat: false },
        Shipment { speed: Speed::Standard, package: Package::Crate, fragile: false, oversize: false, international: false, return_to_sender: false, hazmat: true },
    ];

    for s in shipments {
        println!("{} -> {}", describe(s), label(s));
    }
}
