pub fn active_usernames(lines: &[&str], min_score: i32) -> Vec<String> {
    lines
        .iter()
        .filter_map(|line| {
            let mut parts = line.split('|');
            let name = parts.next()?;
            let status = parts.next()?;
            let score = parts.next()?.parse::<i32>().ok()?;
            if status == "active" && score > min_score {
                Some(name.to_string())
            } else {
                None
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::active_usernames;

    #[test]
    fn keeps_active_users_at_or_above_threshold() {
        let input = [
            "alice|active|10",
            "bob|active|9",
            "cara|inactive|50",
            "dave|active|11",
        ];
        assert_eq!(active_usernames(&input, 10), vec!["alice", "dave"]);
    }

    #[test]
    fn trims_names_and_ignores_blank_names() {
        let input = [
            "  erin  |active|7",
            "   |active|9",
            "frank|active|8",
        ];
        assert_eq!(active_usernames(&input, 7), vec!["erin", "frank"]);
    }

    #[test]
    fn accepts_case_insensitive_status() {
        let input = [
            "gina|ACTIVE|3",
            "hank|Active|5",
            "ian|inactive|8",
        ];
        assert_eq!(active_usernames(&input, 4), vec!["hank"]);
    }

    #[test]
    fn deduplicates_names_preserving_first_accepted_order() {
        let input = [
            "jill|active|4",
            "jill|active|9",
            "kate|active|6",
            "jill|inactive|20",
            "kate|active|7",
        ];
        assert_eq!(active_usernames(&input, 4), vec!["jill", "kate"]);
    }

    #[test]
    fn skips_records_with_extra_fields_or_bad_scores() {
        let input = [
            "lara|active|12|admin",
            "mike|active|oops",
            "nina|active|12",
            "omar|active|12|",
        ];
        assert_eq!(active_usernames(&input, 10), vec!["nina"]);
    }
}
