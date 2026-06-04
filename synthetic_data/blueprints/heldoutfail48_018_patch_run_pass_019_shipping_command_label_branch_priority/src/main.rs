enum Mode {
    Ground,
    Air,
    Sea,
    Pickup,
}

struct Shipment {
    id: u32,
    mode: Mode,
    international: bool,
    express: bool,
    hold: bool,
    oversized: bool,
}

fn label_for(s: &Shipment) -> &'static str {
    match s.mode {
        Mode::Pickup => "PICKUP",
        Mode::Air if s.international => "AIR",
        Mode::Air if s.express => "AIR-EXPRESS",
        Mode::Air => "AIR-STANDARD",
        Mode::Ground if s.oversized => "GROUND",
        Mode::Ground if s.hold => "GROUND-HOLD",
        Mode::Ground => "GROUND-STANDARD",
        Mode::Sea if s.express => "SEA-EXPRESS",
        Mode::Sea => "SEA",
    }
}

fn main() {
    let shipments = [
        Shipment { id: 101, mode: Mode::Ground, international: true, express: false, hold: true, oversized: false },
        Shipment { id: 102, mode: Mode::Air, international: false, express: true, hold: false, oversized: false },
        Shipment { id: 103, mode: Mode::Sea, international: false, express: false, hold: false, oversized: true },
        Shipment { id: 104, mode: Mode::Air, international: true, express: false, hold: false, oversized: false },
        Shipment { id: 105, mode: Mode::Ground, international: false, express: false, hold: false, oversized: true },
        Shipment { id: 106, mode: Mode::Pickup, international: false, express: false, hold: true, oversized: false },
    ];

    for shipment in shipments.iter() {
        println!("{} => {}", shipment.id, label_for(shipment));
    }
}
