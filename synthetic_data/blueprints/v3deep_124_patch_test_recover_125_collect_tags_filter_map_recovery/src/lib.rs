pub fn collect_tags(lines: &[&str]) -> Vec<String> {
    let mut out: Vec<String> = lines
        .iter()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                return None;
            }

            let mut parts = line.split('|');
            let enabled = parts.next()?;
            let category = parts.next()?;
            let tag = parts.next()?;
            let score = parts.next()?;

            if enabled != "on" {
                return None;
            }
            if category == "skip" {
                return None;
            }
            if score.parse::<u32>().ok()? < 10 {
                return None;
            }

            Some(tag.to_string())
        })
        .collect();

    out.sort();
    out
}

#[cfg(test)]
mod tests {
    use super::collect_tags;

    #[test]
    fn collects_enabled_non_skip_tags_with_score_threshold() {
        let input = [
            "on|core|Alpha|12",
            "off|core|Beta|30",
            "on|skip|Gamma|40",
            "on|ops|Delta|9",
            "#comment",
            "  ",
            "on|ops|Echo|11",
        ];

        assert_eq!(collect_tags(&input), vec!["alpha", "echo"]);
    }

    #[test]
    fn ignores_malformed_lines_and_bad_scores() {
        let input = [
            "on|core|One|10|extra",
            "on|core|Two|xx",
            "on|core|Three",
            "on|core|Four|15",
        ];

        assert_eq!(collect_tags(&input), vec!["four"]);
    }

    #[test]
    fn trims_tag_lowercases_and_dedups_after_sorting() {
        let input = [
            "on|core|  Zed  |11",
            "on|core|zed|13",
            "on|core|Able|10",
            "on|core|able|14",
            "on|core|Baker|12",
        ];

        assert_eq!(collect_tags(&input), vec!["able", "baker", "zed"]);
    }

    #[test]
    fn accepts_score_with_surrounding_spaces() {
        let input = ["on|core|Mix| 10 "];
        assert_eq!(collect_tags(&input), vec!["mix"]);
    }

    #[test]
    fn skips_empty_tags_after_trimming() {
        let input = ["on|core|   |12", "on|core|Kept|12"];
        assert_eq!(collect_tags(&input), vec!["kept"]);
    }
}
