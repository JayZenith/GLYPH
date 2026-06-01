use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub category: &'static str,
    pub amount: i32,
    pub active: bool,
}

pub fn summarize(entries: &[Entry]) -> String {
    let mut totals: BTreeMap<&str, (i32, usize)> = BTreeMap::new();

    for entry in entries {
        let slot = totals.entry(entry.category).or_insert((0, 0));
        slot.0 += entry.amount;
        slot.1 += 1;
    }

    let mut out = Vec::new();
    for (category, (total, count)) in totals {
        out.push(format!("{}:{} ({})", category, total, count));
    }

    if out.is_empty() {
        "no data".to_string()
    } else {
        out.join("\n")
    }
}

#[cfg(test)]
mod tests {
    use super::{summarize, Entry};

    #[test]
    fn groups_active_entries_and_sorts_categories() {
        let entries = [
            Entry { category: "ops", amount: 3, active: true },
            Entry { category: "sales", amount: 7, active: false },
            Entry { category: "ops", amount: 2, active: true },
            Entry { category: "sales", amount: 5, active: true },
        ];

        assert_eq!(summarize(&entries), "ops:5 [2]\nsales:5 [1]");
    }

    #[test]
    fn omits_zero_total_categories_and_reports_empty_when_no_active_nonzero_data() {
        let entries = [
            Entry { category: "alpha", amount: 0, active: true },
            Entry { category: "beta", amount: 2, active: false },
            Entry { category: "alpha", amount: 0, active: true },
        ];

        assert_eq!(summarize(&entries), "no active data");
    }

    #[test]
    fn counts_only_active_contributors_to_each_total() {
        let entries = [
            Entry { category: "dev", amount: 4, active: true },
            Entry { category: "dev", amount: -1, active: true },
            Entry { category: "dev", amount: 10, active: false },
            Entry { category: "qa", amount: 1, active: true },
        ];

        assert_eq!(summarize(&entries), "dev:3 [2]\nqa:1 [1]");
    }
}
