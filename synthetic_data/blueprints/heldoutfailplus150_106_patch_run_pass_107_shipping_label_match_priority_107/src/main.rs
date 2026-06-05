enum Label {
    Priority,
    Hazard,
    International,
    Return,
    Standard,
}

fn parse_label(code: &str) -> Label {
    if code.contains("PR") {
        Label::Priority
    } else if code.contains("HZ") {
        Label::Hazard
    } else if code.contains("INTL") {
        Label::International
    } else if code.ends_with("-R") {
        Label::Return
    } else {
        Label::Standard
    }
}

fn route(code: &str) -> &'static str {
    match parse_label(code) {
        Label::Priority => "priority-air",
        Label::Hazard => "hazmat-ground",
        Label::International => "intl-pass",
        Label::Return => "returns-dock",
        Label::Standard => "standard-ground",
    }
}

fn main() {
    let codes = [
        "PR-778",
        "HZ-12",
        "HZ-X9-R",
        "INTL-7",
        "INTL-HZ-88",
        "STD-3-R",
        "AOG-1",
        "PR-INTL-9",
        "LOCAL",
        "HZ-PR-5",
    ];

    for code in codes {
        println!("{} -> {}", code, route(code));
    }
}
