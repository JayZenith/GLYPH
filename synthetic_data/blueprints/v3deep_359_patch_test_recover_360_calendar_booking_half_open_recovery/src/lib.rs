#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Booking {
    pub room: String,
    pub start: u32,
    pub end: u32,
}

impl Booking {
    pub fn new(room: &str, start: u32, end: u32) -> Self {
        Self {
            room: room.to_string(),
            start,
            end,
        }
    }
}

pub fn can_book(existing: &[Booking], candidate: &Booking) -> bool {
    if candidate.start > candidate.end {
        return false;
    }

    for b in existing {
        if b.room != candidate.room {
            continue;
        }

        if candidate.start <= b.end && candidate.end >= b.start {
            return false;
        }
    }

    true
}

pub fn conflicting_bookings(existing: &[Booking], candidate: &Booking) -> Vec<Booking> {
    let mut out = Vec::new();
    for b in existing {
        if b.room == candidate.room && candidate.start <= b.end && candidate.end >= b.start {
            out.push(b.clone());
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seed() -> Vec<Booking> {
        vec![
            Booking::new("A", 10, 20),
            Booking::new("A", 20, 25),
            Booking::new("A", 30, 40),
            Booking::new("B", 10, 50),
        ]
    }

    #[test]
    fn allows_back_to_back_in_same_room() {
        let existing = seed();
        let candidate = Booking::new("A", 25, 30);
        assert!(can_book(&existing, &candidate));
        assert!(conflicting_bookings(&existing, &candidate).is_empty());
    }

    #[test]
    fn rejects_zero_length_and_inverted_ranges() {
        let existing = seed();
        assert!(!can_book(&existing, &Booking::new("A", 22, 22)));
        assert!(!can_book(&existing, &Booking::new("A", 23, 22)));
        assert!(conflicting_bookings(&existing, &Booking::new("A", 22, 22)).is_empty());
    }

    #[test]
    fn ignores_other_rooms() {
        let existing = seed();
        let candidate = Booking::new("C", 15, 18);
        assert!(can_book(&existing, &candidate));
        assert!(conflicting_bookings(&existing, &candidate).is_empty());
    }

    #[test]
    fn reports_all_true_overlaps_in_order() {
        let existing = seed();
        let candidate = Booking::new("A", 18, 35);
        let conflicts = conflicting_bookings(&existing, &candidate);
        assert_eq!(conflicts.len(), 3);
        assert_eq!(conflicts[0], Booking::new("A", 10, 20));
        assert_eq!(conflicts[1], Booking::new("A", 20, 25));
        assert_eq!(conflicts[2], Booking::new("A", 30, 40));
        assert!(!can_book(&existing, &candidate));
    }
}
