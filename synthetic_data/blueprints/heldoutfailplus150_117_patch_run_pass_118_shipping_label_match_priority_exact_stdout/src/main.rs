enum Route {
    Ground,
    Air,
    Sea,
    Pickup,
    Priority,
    Unknown,
}

fn route_from_tag(tag: &str) -> Route {
    if tag.contains("air") {
        Route::Air
    } else if tag.contains("sea") {
        Route::Sea
    } else if tag.contains("pickup") {
        Route::Pickup
    } else if tag.contains("ground") {
        Route::Ground
    } else if tag.contains("priority") {
        Route::Priority
    } else {
        Route::Unknown
    }
}

fn label_for(tag: &str) -> &'static str {
    match route_from_tag(tag) {
        Route::Ground => "ground",
        Route::Air => {
            if tag.ends_with("priority") {
                "air-priority"
            } else {
                "air"
            }
        }
        Route::Sea => "sea",
        Route::Pickup => {
            if tag.contains("air") {
                "hybrid-pickup"
            } else {
                "pickup"
            }
        }
        Route::Priority => "priority",
        Route::Unknown => "unknown",
    }
}

fn main() {
    let tags = [
        "ground",
        "air.priority",
        "air",
        "sea.bulk",
        "pickup",
        "air.priority.pickup",
        "pickup.air",
        "sea.priority",
        "rail",
        "priority",
    ];

    for tag in tags {
        println!("{} => {}", tag, label_for(tag));
    }
}
