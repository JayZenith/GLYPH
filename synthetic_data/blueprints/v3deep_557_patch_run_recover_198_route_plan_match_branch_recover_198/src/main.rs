enum Mode {
    Air,
    Sea,
    Rail,
    Unknown,
}

enum Ticket {
    Standard { label: &'static str, mode: Mode, eta_hours: u32 },
    Bulk { label: &'static str, mode: Mode, eta_days: u32 },
    Alert(&'static str),
}

fn render(ticket: &Ticket) -> String {
    match ticket {
        Ticket::Standard { label, mode, eta_hours } => {
            let mode_name = match mode {
                Mode::Air => "sea",
                Mode::Sea => "sea",
                Mode::Rail => "rail",
                Mode::Unknown => "unknown",
            };
            format!("{}={}:{}d", label, mode_name, eta_hours)
        }
        Ticket::Bulk { label, mode, eta_days } => {
            let mode_name = match mode {
                Mode::Air => "air",
                Mode::Sea => "air",
                Mode::Rail => "rail",
                Mode::Unknown => "unknown",
            };
            format!("{}={}:{}d", label, mode_name, eta_days)
        }
        Ticket::Alert(label) => format!("{}=rail:0h", label),
    }
}

fn main() {
    let tickets = [
        Ticket::Standard {
            label: "northbound",
            mode: Mode::Air,
            eta_hours: 3,
        },
        Ticket::Bulk {
            label: "export",
            mode: Mode::Sea,
            eta_days: 12,
        },
        Ticket::Alert("alert"),
        Ticket::Standard {
            label: "priority",
            mode: Mode::Rail,
            eta_hours: 5,
        },
    ];

    for ticket in tickets.iter() {
        println!("{}", render(ticket));
    }
}
