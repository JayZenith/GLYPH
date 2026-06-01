use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub region: &'static str,
    pub agent: &'static str,
    pub resolved: u32,
    pub reopened: u32,
    pub escalated: bool,
}

pub fn build_report(entries: &[Entry]) -> String {
    let mut groups: BTreeMap<&str, (u32, u32, u32, Vec<&str>)> = BTreeMap::new();

    for e in entries {
        let bucket = groups.entry(e.region).or_insert((0, 0, 0, Vec::new()));
        bucket.0 += 1;
        bucket.1 += e.resolved;
        if e.escalated {
            bucket.2 += 1;
        }
        bucket.3.push(e.agent);
    }

    let mut out = String::new();
    let mut first = true;
    for (region, (tickets, resolved, escalations, agents)) in groups {
        if !first {
            out.push('\n');
        }
        first = false;
        let avg = if tickets == 0 { 0 } else { resolved / tickets };
        out.push_str(&format!(
            "{region}: tickets={tickets}, resolved={resolved}, avg={avg}, escalations={escalations}, agents={} ",
            agents.join("|")
        ));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grouped_summary_is_sorted_and_filtered() {
        let entries = [
            Entry { region: "west", agent: "Mia", resolved: 4, reopened: 1, escalated: false },
            Entry { region: "east", agent: "Ava", resolved: 3, reopened: 0, escalated: true },
            Entry { region: "west", agent: "Noah", resolved: 0, reopened: 2, escalated: true },
            Entry { region: "east", agent: "Ava", resolved: 2, reopened: 1, escalated: false },
            Entry { region: "north", agent: "Zoe", resolved: 5, reopened: 0, escalated: false },
            Entry { region: "west", agent: "Mia", resolved: 1, reopened: 0, escalated: false },
        ];

        let expected = concat!(
            "east: tickets=2, resolved=5, reopened=1, avg=2, escalations=1, agents=Ava\n",
            "north: tickets=1, resolved=5, reopened=0, avg=5, escalations=0, agents=Zoe\n",
            "west: tickets=3, resolved=5, reopened=3, avg=1, escalations=1, agents=Mia|Noah"
        );

        assert_eq!(build_report(&entries), expected);
    }

    #[test]
    fn duplicate_agents_are_deduped_and_sorted_per_region() {
        let entries = [
            Entry { region: "south", agent: "Kai", resolved: 2, reopened: 0, escalated: false },
            Entry { region: "south", agent: "Ana", resolved: 1, reopened: 2, escalated: true },
            Entry { region: "south", agent: "Kai", resolved: 3, reopened: 1, escalated: false },
        ];

        let expected = "south: tickets=3, resolved=6, reopened=3, avg=2, escalations=1, agents=Ana|Kai";
        assert_eq!(build_report(&entries), expected);
    }

    #[test]
    fn empty_input_returns_empty_string() {
        assert_eq!(build_report(&[]), "");
    }
}
