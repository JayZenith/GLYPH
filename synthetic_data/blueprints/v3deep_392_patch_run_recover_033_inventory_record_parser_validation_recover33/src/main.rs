const INPUT: &str = r#"
# sku|name|qty|price|category
A12|Widget|5|12.50|tools
B7|Bolt|10|0.99|hardware
|MissingSku|3|1.00|misc
C99|BadQty|0|3.10|tools
D4|Tape|3|4.25|tools
E5|BadPrice|2|-1.00|tools
F6|BadCategory|1|2.00|
BADLINE
"#;

#[derive(Debug)]
struct Record {
    sku: String,
    name: String,
    qty: u32,
    price: f64,
    category: String,
}

fn parse_line(line: &str) -> Option<Record> {
    let parts: Vec<&str> = line.split('|').collect();
    if parts.len() < 5 {
        return None;
    }

    let sku = parts[0].to_string();
    let name = parts[1].to_string();
    let qty = parts[2].parse::<u32>().ok()?;
    let price = parts[3].parse::<f64>().ok()?;
    let category = parts[4].to_string();

    Some(Record {
        sku,
        name,
        qty,
        price,
        category,
    })
}

fn main() {
    let mut valid = Vec::new();
    let mut totals: Vec<(String, usize)> = Vec::new();

    for line in INPUT.lines() {
        if let Some(rec) = parse_line(line) {
            match totals.iter_mut().find(|(cat, _)| *cat == rec.category) {
                Some((_, count)) => *count += 1,
                None => totals.push((rec.category.clone(), 1)),
            }
            valid.push(rec);
        }
    }

    println!("VALID {}", valid.len());
    for rec in valid {
        println!(
            "{} {} qty={} price={:.2} category={}",
            rec.sku, rec.name, rec.qty, rec.price, rec.category
        );
    }
    println!("TOTALS");
    for (cat, count) in totals {
        println!("{}: {}", cat, count);
    }
}
