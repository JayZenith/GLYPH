use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub team: &'static str,
    pub member: &'static str,
    pub hours: u32,
    pub billable: bool,
}

pub fn build_report(entries: &[Entry]) -> String {
    let mut totals: BTreeMap<&str, (u32, u32, u32)> = BTreeMap::new();

    for entry in entries {
        if entry.hours == 0 {
            continue;
        }

        let row = totals.entry(entry.team).or_insert((0, 0, 0));
        row.0 += entry.hours;
        row.1 += 1;
        if entry.billable {
            row.2 += entry.hours;
        }
    }

    let mut out = String::new();
    for (team, (hours, members, billable)) in totals {
        let utilization = if hours == 0 { 0 } else { (billable * 100) / hours };
        out.push_str(&format!("{team}: total={hours} members={members} util={utilization}%\n"));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_entries() -> Vec<Entry> {
        vec![
            Entry { team: "alpha", member: "ann", hours: 5, billable: true },
            Entry { team: "alpha", member: "ann", hours: 3, billable: false },
            Entry { team: "alpha", member: "abe", hours: 4, billable: true },
            Entry { team: "beta", member: "bea", hours: 0, billable: true },
            Entry { team: "beta", member: "bob", hours: 6, billable: false },
            Entry { team: "beta", member: "bob", hours: 2, billable: true },
            Entry { team: "ops", member: "ola", hours: 0, billable: false },
        ]
    }

    #[test]
    fn report_groups_sorted_and_formats_summary() {
        let report = build_report(&sample_entries());
        let lines: Vec<&str> = report.lines().collect();
        assert_eq!(
            lines,
            vec![
                "alpha: total=12 active=2 util=75%",
                "beta: total=8 active=1 util=25%",
            ]
        );
    }

    #[test]
    fn report_skips_zero_total_teams_and_has_no_trailing_newline() {
        let report = build_report(&sample_entries());
        assert!(!report.ends_with('\n'));
        assert!(!report.contains("ops:"));
    }

    #[test]
    fn report_empty_input_is_empty_string() {
        assert_eq!(build_report(&[]), "");
    }
}
