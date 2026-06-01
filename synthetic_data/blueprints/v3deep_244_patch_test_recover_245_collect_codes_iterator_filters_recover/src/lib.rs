pub fn collect_codes<'a, I>(items: I) -> Vec<String>
where
    I: IntoIterator<Item = &'a str>,
{
    items
        .into_iter()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .filter_map(|s| s.strip_prefix("code:"))
        .map(|s| s.trim().to_string())
        .filter(|s| !s.contains(' '))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_codes;

    #[test]
    fn keeps_only_code_entries() {
        let input = ["note:x", "code:AA", "", " code:BB ", "skip", "code:CC"];
        assert_eq!(collect_codes(input), vec!["AA", "BB", "CC"]);
    }

    #[test]
    fn drops_blank_and_dash_only_codes() {
        let input = ["code:", "code:   ", "code:---", "code:A-1", "code:B2"];
        assert_eq!(collect_codes(input), vec!["A-1", "B2"]);
    }

    #[test]
    fn normalizes_case_and_deduplicates_preserving_first_seen_order() {
        let input = ["code:ab", "code:AB", "code:xy", "code:Xy", "code:zz"];
        assert_eq!(collect_codes(input), vec!["AB", "XY", "ZZ"]);
    }

    #[test]
    fn rejects_codes_with_non_ascii_alnum_or_dash() {
        let input = ["code:OK-1", "code:bad_code", "code:mi!x", "code:Z9"];
        assert_eq!(collect_codes(input), vec!["OK-1", "Z9"]);
    }

    #[test]
    fn ignores_disabled_entries_case_insensitively() {
        let input = ["code:AA", "disabled:BB", "DISABLED:CC", " code:DD "];
        assert_eq!(collect_codes(input), vec!["AA", "DD"]);
    }
}
