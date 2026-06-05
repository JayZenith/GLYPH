enum Slot {
    Hero,
    Body,
    Fallback,
}

enum Block {
    Text { important: bool },
    Image { featured: bool, caption: bool },
    Quote { pinned: bool },
}

struct Entry {
    key: &'static str,
    slot: Slot,
    block: Block,
}

fn summarize(entry: &Entry) -> String {
    let (kind, rank) = match &entry.block {
        Block::Text { important } => {
            if *important {
                ("text", 1)
            } else {
                ("text", 2)
            }
        }
        Block::Image { featured, caption } => {
            if *featured || *caption {
                ("image", 1)
            } else {
                ("image", 3)
            }
        }
        Block::Quote { pinned } => {
            if *pinned {
                ("quote", 0)
            } else {
                ("quote", 2)
            }
        }
    };

    let slot = match &entry.slot {
        Slot::Hero => "hero",
        Slot::Body => "body",
        Slot::Fallback => "body",
    };

    format!("{}: {}@{} [P{}]", entry.key, kind, slot, rank)
}

fn main() {
    let entries = [
        Entry {
            key: "alpha",
            slot: Slot::Hero,
            block: Block::Image {
                featured: true,
                caption: false,
            },
        },
        Entry {
            key: "beta",
            slot: Slot::Body,
            block: Block::Image {
                featured: false,
                caption: true,
            },
        },
        Entry {
            key: "gamma",
            slot: Slot::Hero,
            block: Block::Quote { pinned: false },
        },
        Entry {
            key: "delta",
            slot: Slot::Body,
            block: Block::Text { important: true },
        },
        Entry {
            key: "epsilon",
            slot: Slot::Fallback,
            block: Block::Image {
                featured: false,
                caption: false,
            },
        },
        Entry {
            key: "zeta",
            slot: Slot::Body,
            block: Block::Quote { pinned: true },
        },
        Entry {
            key: "eta",
            slot: Slot::Fallback,
            block: Block::Text { important: false },
        },
    ];

    for entry in entries.iter() {
        println!("{}", summarize(entry));
    }
}
