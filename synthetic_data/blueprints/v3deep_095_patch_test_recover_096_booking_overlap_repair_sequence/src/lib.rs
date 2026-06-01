pub fn overlaps(existing: (u32, u32), requested: (u32, u32)) -> bool {
    let (a_start, a_end) = existing;
    let (b_start, b_end) = requested;

    if a_start >= a_end || b_start >= b_end {
        return true;
    }

    a_start <= b_end && b_start <= a_end
}

pub fn can_book(existing: &[(u32, u32)], requested: (u32, u32)) -> bool {
    if requested.0 >= requested.1 {
        return true;
    }

    existing.iter().all(|&slot| overlaps(slot, requested))
}

#[cfg(test)]
mod tests {
    use super::{can_book, overlaps};

    #[test]
    fn touching_intervals_do_not_overlap() {
        assert!(!overlaps((10, 12), (12, 15)));
        assert!(!overlaps((12, 15), (10, 12)));
    }

    #[test]
    fn interior_overlap_is_detected() {
        assert!(overlaps((10, 14), (12, 13)));
        assert!(overlaps((12, 13), (10, 14)));
    }

    #[test]
    fn invalid_intervals_never_overlap() {
        assert!(!overlaps((5, 5), (5, 8)));
        assert!(!overlaps((7, 9), (9, 9)));
    }

    #[test]
    fn booking_succeeds_when_no_existing_slot_conflicts() {
        let existing = [(8, 10), (12, 14)];
        assert!(can_book(&existing, (10, 12)));
    }

    #[test]
    fn booking_fails_when_any_existing_slot_conflicts() {
        let existing = [(8, 10), (12, 14)];
        assert!(!can_book(&existing, (9, 11)));
    }

    #[test]
    fn invalid_requested_interval_cannot_be_booked() {
        let existing = [(8, 10)];
        assert!(!can_book(&existing, (10, 10)));
    }
}
