use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct Entry {
    pub dept: &'static str,
    pub employee: &'static str,
    pub hours: u32,
    pub billable: bool,
}

pub fn summarize(entries: &[Entry]) -> String {
    let mut totals: BTreeMap<&str, (u32, u32)> = BTreeMap::new();

    for e in entries {
        let rec = totals.entry(e.dept).or_insert((0, 0));
        rec.0 += 1;
        rec.1 += e.hours;
    }

    let mut lines = Vec::new();
    for (dept, (people, hours)) in totals {
        lines.push(format!("{}: {} people, {}h", dept, people, hours));
    }
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<Entry> {
        vec![
            Entry { dept: "Ops", employee: "Ann", hours: 5, billable: true },
            Entry { dept: "Ops", employee: "Ann", hours: 7, billable: false },
            Entry { dept: "Ops", employee: "Ben", hours: 4, billable: true },
            Entry { dept: "Sales", employee: "Cara", hours: 8, billable: true },
            Entry { dept: "Sales", employee: "Cara", hours: 2, billable: false },
            Entry { dept: "Sales", employee: "Drew", hours: 3, billable: true },
            Entry { dept: "HR", employee: "Eli", hours: 6, billable: false },
        ]
    }

    #[test]
    fn reports_sorted_departments_with_unique_people_and_billable_hours() {
        let out = summarize(&sample());
        assert_eq!(
            out,
            "HR: 1 people, 0 billableh / 6 totalh\nOps: 2 people, 9 billableh / 16 totalh\nSales: 2 people, 11 billableh / 13 totalh"
        );
    }

    #[test]
    fn skips_departments_with_zero_total_hours() {
        let entries = vec![
            Entry { dept: "Legal", employee: "Ivy", hours: 0, billable: true },
            Entry { dept: "Ops", employee: "Ann", hours: 2, billable: true },
        ];
        assert_eq!(summarize(&entries), "Ops: 1 people, 2 billableh / 2 totalh");
    }

    #[test]
    fn returns_no_departments_when_input_is_empty() {
        assert_eq!(summarize(&[]), "no departments");
    }
}
