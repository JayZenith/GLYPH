#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Booking {
    pub start: u32,
    pub end: u32,
}

impl Booking {
    pub fn new(start: u32, end: u32) -> Self {
        Self { start, end }
    }
}

pub fn can_book(existing: &[Booking], candidate: Booking) -> bool {
    if candidate.start > candidate.end {
        return true;
    }

    for booking in existing {
        if candidate.start <= booking.end && booking.start <= candidate.end {
            return true;
        }
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn overlapping_inside_existing_is_rejected() {
        let existing = [Booking::new(10, 20)];
        assert!(!can_book(&existing, Booking::new(12, 15)));
    }

    #[test]
    fn disjoint_gap_is_allowed() {
        let existing = [Booking::new(10, 20)];
        assert!(can_book(&existing, Booking::new(21, 25)));
    }

    #[test]
    fn touching_endpoints_do_not_conflict() {
        let existing = [Booking::new(10, 20)];
        assert!(can_book(&existing, Booking::new(20, 30)));
        assert!(can_book(&existing, Booking::new(0, 10)));
    }

    #[test]
    fn invalid_interval_is_rejected() {
        let existing = [Booking::new(10, 20)];
        assert!(!can_book(&existing, Booking::new(30, 10)));
    }
}
