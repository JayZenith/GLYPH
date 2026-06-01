pub fn extract_enabled_tags(input: &[&str]) -> Vec<String> {
    input
        .iter()
        .filter_map(|raw| {
            let s = raw.trim();
            if s.is_empty() || s.starts_with('#') {
                return None;
            }

            let (enabled, rest) = s.split_once(':')?;
            if enabled != "on" {
                return None;
            }

            let tag = rest.trim();
            if tag.is_empty() {
                return None;
            }

            Some(tag.to_string())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::extract_enabled_tags;

    #[test]
    fn keeps_only_enabled_tags_and_normalizes_case() {
        let input = [
            "on: Alpha",
            "off: beta",
            " on :  gamma ",
            "#on: hidden",
            "on:DELTA",
        ];

        let got = extract_enabled_tags(&input);
        assert_eq!(got, vec!["alpha", "gamma", "delta"]);
    }

    #[test]
    fn splits_comma_lists_and_dedups_by_first_occurrence() {
        let input = [
            "on: red, blue",
            "on: blue, green",
            "on: red",
            "off: yellow, blue",
        ];

        let got = extract_enabled_tags(&input);
        assert_eq!(got, vec!["red", "blue", "green"]);
    }

    #[test]
    fn ignores_blank_items_and_inline_comments() {
        let input = [
            "on: kiwi, , mango # seasonal",
            "on: pear#keep-before-comment",
            "on:   ",
            "# full line comment",
        ];

        let got = extract_enabled_tags(&input);
        assert_eq!(got, vec!["kiwi", "mango", "pear"]);
    }
}
