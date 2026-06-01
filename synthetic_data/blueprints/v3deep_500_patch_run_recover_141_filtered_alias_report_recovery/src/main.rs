struct Person {
    name: &'static str,
    alias: Option<&'static str>,
    active: bool,
}

fn main() {
    let people = vec![
        Person { name: "Ada", alias: Some("Al"), active: true },
        Person { name: "Bob", alias: None, active: true },
        Person { name: "Cy", alias: Some("cee"), active: false },
        Person { name: "Dee", alias: Some("dee"), active: true },
        Person { name: "Eve", alias: Some(""), active: true },
    ];

    let aliases = people
        .iter()
        .filter(|p| p.alias.is_some())
        .map(|p| p.alias.unwrap_or(p.name).to_string())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join(", ");

    println!("active aliases: {aliases}");
}
