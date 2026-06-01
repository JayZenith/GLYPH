pub fn collect_tags(items: &[&str]) -> Vec<String> {
    items
        .iter()
        .filter_map(|item| {
            let (name, tag) = item.split_once(':')?;
            let name = name.trim();
            let tag = tag.trim();
            if name.is_empty() || tag.is_empty() {
                return None;
            }
            if name.starts_with('#') || tag == "skip" {
                return None;
            }
            Some(tag.to_ascii_lowercase())
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::collect_tags;

    #[test]
    fn skips_comments_blank_values_and_skip_marker() {
        let items = [
            "alpha:One",
            "# note:ignored",
            "beta:skip",
            "gamma:",
            "delta:Two",
        ];
        assert_eq!(collect_tags(&items), vec!["one", "two"]);
    }

    #[test]
    fn trims_lowercases_dedups_and_sorts() {
        let items = [
            "apple: Zed ",
            "pear:alpha",
            "orange:zed",
            "melon: Beta",
            "berry:alpha ",
        ];
        assert_eq!(collect_tags(&items), vec!["alpha", "beta", "zed"]);
    }

    #[test]
    fn ignores_short_tags_and_missing_separator() {
        let items = [
            "ok:go",
            "tiny:x",
            "badline",
            "valid:Sun",
            "also:  y ",
        ];
        assert_eq!(collect_tags(&items), vec!["go", "sun"]);
    }
}
