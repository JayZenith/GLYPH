enum Event {
    Signup { email: String },
    Otp { phone: String },
    Ping { device: String, urgent: bool },
    Shipment { url: String, retries: u8 },
    Receipt { email: String, paid: bool },
}

enum Delivery {
    Email { template: &'static str, target: String },
    Sms { kind: &'static str, target: String },
    Push { channel: &'static str, target: String },
    Webhook { topic: &'static str, target: String, attempts: u8 },
}

fn route(event: &Event) -> Delivery {
    match event {
        Event::Signup { email } => Delivery::Email {
            template: "verify",
            target: email.clone(),
        },
        Event::Otp { phone } => Delivery::Sms {
            kind: "alert",
            target: phone.clone(),
        },
        Event::Ping { device, urgent } => {
            if *urgent {
                Delivery::Push {
                    channel: "silent",
                    target: device.clone(),
                }
            } else {
                Delivery::Push {
                    channel: "ring",
                    target: device.clone(),
                }
            }
        }
        Event::Shipment { url, retries } => Delivery::Webhook {
            topic: "order.created",
            target: url.clone(),
            attempts: retries.saturating_add(1),
        },
        Event::Receipt { email, paid } => {
            if *paid {
                Delivery::Email {
                    template: "receipt",
                    target: email.clone(),
                }
            } else {
                Delivery::Email {
                    template: "receipt",
                    target: email.clone(),
                }
            }
        }
    }
}

fn render(delivery: Delivery) -> String {
    match delivery {
        Delivery::Email { template, target } => format!("email:{}:{}", target, template),
        Delivery::Sms { kind, target } => format!("sms:{}:{}", target, kind),
        Delivery::Push { channel, target } => format!("push:{}:{}", target, channel),
        Delivery::Webhook {
            topic,
            target,
            attempts,
        } => format!("webhook:{}:{}:{}", target, topic, attempts),
    }
}

fn main() {
    let events = [
        Event::Signup {
            email: "a@example.com".to_string(),
        },
        Event::Otp {
            phone: "+15550001".to_string(),
        },
        Event::Ping {
            device: "dev42".to_string(),
            urgent: false,
        },
        Event::Shipment {
            url: "https://ops.example/hook".to_string(),
            retries: 2,
        },
        Event::Receipt {
            email: "b@example.com".to_string(),
            paid: true,
        },
    ];

    let lines: Vec<String> = events.iter().map(route).map(render).collect();
    println!("{}", lines.join("\n"));
}
