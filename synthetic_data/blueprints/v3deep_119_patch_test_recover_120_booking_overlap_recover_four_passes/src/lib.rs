pub fn can_book(existing: &[(u32, u32)], start: u32, end: u32) -> bool {
    if start > end {
        return false;
    }

    for &(s, e) in existing {
        if start >= s && start <= e {
            return false;
        }
    }

    true
}

#[cfg(test)]
mod tests {
    use super::can_book;

    #[test]
    fn rejects_overlapping_start_inside_existing() {
        assert!(!can_book(&[(10, 20)], 15, 18));
    }

    #[test]
    fn rejects_when_new_interval_contains_existing() {
        assert!(!can_book(&[(10, 20)], 5, 25));
    }

    #[test]
    fn rejects_when_end_falls_inside_existing() {
        assert!(!can_book(&[(10, 20)], 5, 12));
    }

    #[test]
    fn allows_touching_endpoints_as_non_overlapping() {
        assert!(can_book(&[(10, 20)], 20, 25));
        assert!(can_book(&[(10, 20)], 5, 10));
    }

    #[test]
    fn rejects_invalid_or_zero_length_ranges() {
        assert!(!can_book(&[], 8, 8));
        assert!(!can_book(&[], 9, 8));
    }

    #[test]
    fn checks_all_existing_bookings() {
        assert!(!can_book(&[(1, 3), (8, 12)], 10, 11));
    }
}
