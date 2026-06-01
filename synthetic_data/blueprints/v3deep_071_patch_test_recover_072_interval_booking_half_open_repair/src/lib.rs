pub fn can_book(existing: &[(u32, u32)], start: u32, end: u32) -> bool {
    if start >= end {
        return true;
    }

    for &(s, e) in existing {
        if end < s || start > e {
            continue;
        }
        return false;
    }

    true
}

#[cfg(test)]
mod tests {
    use super::can_book;

    #[test]
    fn allows_non_overlapping_gap() {
        let bookings = [(10, 12), (15, 18)];
        assert!(can_book(&bookings, 12, 15));
    }

    #[test]
    fn rejects_partial_overlap() {
        let bookings = [(10, 12), (15, 18)];
        assert!(!can_book(&bookings, 11, 16));
    }

    #[test]
    fn rejects_contained_booking() {
        let bookings = [(10, 20)];
        assert!(!can_book(&bookings, 12, 14));
    }

    #[test]
    fn rejects_invalid_empty_interval() {
        let bookings = [(10, 12)];
        assert!(!can_book(&bookings, 9, 9));
    }

    #[test]
    fn touching_endpoints_do_not_overlap() {
        let bookings = [(10, 12), (15, 18)];
        assert!(can_book(&bookings, 18, 20));
    }
}
