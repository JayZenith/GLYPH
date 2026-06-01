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

pub fn can_book(existing: &[Booking], start: u32, end: u32) -> bool {
    if start > end {
        return false;
    }

    for b in existing {
        if start <= b.end && end >= b.start {
            return false;
        }
    }

    true
}

pub fn first_conflict(existing: &[Booking], start: u32, end: u32) -> Option<Booking> {
    for b in existing {
        if start <= b.end && end >= b.start {
            return Some(*b);
        }
    }
    None
}

pub fn insert_booking(existing: &mut Vec<Booking>, start: u32, end: u32) -> bool {
    if !can_book(existing, start, end) {
        return false;
    }
    existing.push(Booking::new(start, end));
    existing.sort_by_key(|b| b.start);
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Booking> {
        vec![Booking::new(10, 20), Booking::new(30, 40)]
    }

    #[test]
    fn rejects_invalid_or_zero_length_ranges() {
        let bookings = sample();
        assert!(!can_book(&bookings, 25, 25));
        assert!(!can_book(&bookings, 22, 21));
    }

    #[test]
    fn touching_endpoints_do_not_conflict() {
        let bookings = sample();
        assert!(can_book(&bookings, 20, 25));
        assert!(can_book(&bookings, 25, 30));
        assert_eq!(first_conflict(&bookings, 20, 25), None);
    }

    #[test]
    fn overlap_inside_existing_conflicts() {
        let bookings = sample();
        assert!(!can_book(&bookings, 12, 18));
        assert_eq!(first_conflict(&bookings, 12, 18), Some(Booking::new(10, 20)));
    }

    #[test]
    fn insert_keeps_sorted_and_respects_conflicts() {
        let mut bookings = vec![Booking::new(30, 40), Booking::new(10, 20)];
        assert!(insert_booking(&mut bookings, 20, 25));
        assert_eq!(bookings, vec![Booking::new(10, 20), Booking::new(20, 25), Booking::new(30, 40)]);
        assert!(!insert_booking(&mut bookings, 24, 31));
    }
}
