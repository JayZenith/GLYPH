pub fn has_conflict(existing: &[(u32, u32)], candidate: (u32, u32)) -> bool {
    let (start, end) = candidate;
    if start > end {
        return true;
    }

    existing.iter().any(|&(s, e)| {
        start >= s && start <= e
    })
}

#[cfg(test)]
mod tests {
    use super::has_conflict;

    #[test]
    fn no_conflict_when_touching_edges() {
        let bookings = vec![(10, 20), (30, 40)];
        assert!(!has_conflict(&bookings, (20, 30)));
        assert!(!has_conflict(&bookings, (0, 10)));
        assert!(!has_conflict(&bookings, (40, 50)));
    }

    #[test]
    fn overlap_inside_existing_conflicts() {
        let bookings = vec![(10, 20)];
        assert!(has_conflict(&bookings, (12, 18)));
        assert!(has_conflict(&bookings, (5, 12)));
        assert!(has_conflict(&bookings, (18, 25)));
    }

    #[test]
    fn candidate_covering_existing_conflicts() {
        let bookings = vec![(10, 20), (30, 35)];
        assert!(has_conflict(&bookings, (5, 25)));
        assert!(has_conflict(&bookings, (0, 40)));
    }

    #[test]
    fn zero_length_candidate_is_invalid() {
        let bookings = vec![(10, 20)];
        assert!(has_conflict(&bookings, (15, 15)));
        assert!(has_conflict(&bookings, (25, 25)));
    }

    #[test]
    fn reversed_candidate_is_invalid() {
        let bookings = vec![(10, 20)];
        assert!(has_conflict(&bookings, (9, 3)));
    }
}
