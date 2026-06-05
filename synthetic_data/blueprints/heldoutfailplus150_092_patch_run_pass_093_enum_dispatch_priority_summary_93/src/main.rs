enum Job {
    Retry { attempts: u8, label: &'static str },
    Deploy { env: &'static str, hotfix: bool },
    Audit { blocked: bool, area: &'static str },
    Cleanup { nightly: bool, target: &'static str },
    Unknown,
}

fn summarize(job: &Job) -> String {
    match job {
        Job::Retry { label, .. } => format!("{} [retry]", label),
        Job::Deploy { env, .. } => format!("{} [{}]", env, "deploy"),
        Job::Audit { area, blocked } => {
            if *blocked {
                format!("blocked {} [blocked]", area)
            } else {
                format!("audit {} [normal]", area)
            }
        }
        Job::Cleanup { target, nightly } => {
            if *nightly {
                format!("{} [normal]", target)
            } else {
                format!("{} [maintenance]", target)
            }
        }
        Job::Unknown => "unknown [normal]".to_string(),
    }
}

fn main() {
    let jobs = vec![
        Job::Retry {
            attempts: 1,
            label: "cache",
        },
        Job::Deploy {
            env: "ship",
            hotfix: true,
        },
        Job::Cleanup {
            nightly: true,
            target: "sweep",
        },
        Job::Audit {
            blocked: true,
            area: "migration",
        },
        Job::Deploy {
            env: "refresh",
            hotfix: false,
        },
        Job::Unknown,
        Job::Audit {
            blocked: false,
            area: "docs cleanup",
        },
        Job::Retry {
            attempts: 4,
            label: "hotfix",
        },
        Job::Retry {
            attempts: 2,
            label: "deploy",
        },
    ];

    for (idx, job) in jobs.iter().enumerate() {
        println!("{}: {}", idx, summarize(job));
    }
}
