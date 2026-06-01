enum Job {
    Create { name: &'static str, template: bool },
    Delete { target: &'static str, force: bool },
    Rename { from: &'static str, to: &'static str },
    Ignore(&'static str),
}

fn describe(job: &Job) -> String {
    match job {
        Job::Create { name, template } => {
            if *template {
                format!("created {}", name)
            } else {
                format!("created {} from template", name)
            }
        }
        Job::Delete { target, force } => {
            if *force {
                format!("skipped {}", target)
            } else {
                format!("deleted {}", target)
            }
        }
        Job::Rename { from, to } => format!("renamed {} => {}", to, from),
        Job::Ignore(name) => format!("deleted {}", name),
    }
}

fn main() {
    let jobs = [
        Job::Create {
            name: "alpha.md",
            template: true,
        },
        Job::Ignore("draft.tmp"),
        Job::Rename {
            from: "old.log",
            to: "old-2024.log",
        },
        Job::Delete {
            target: "cache.bin",
            force: false,
        },
        Job::Create {
            name: "notes.txt",
            template: false,
        },
    ];

    for job in jobs.iter() {
        println!("{}", describe(job));
    }
}
