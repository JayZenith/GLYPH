# GLYPH Trace Language 
A structured trace format for agentic LLM reasoning, planning, tool use, and responses.

## Core Idea
A GLYPH trace is a sequence of structured blocks:
system
tool
user
plan
act
result
response

The model:
1. receives instructions
2. plans
3. acts/tools/reasons
4. receives results
5. responds

## Primitive Types
### Numbers
123
0xFF
3.14
Same as JS numbers

### Strings
No quotes if no spaces
hello

Quotes if spaces:
"hello world"

Special quotes for long text:
「multi-line text」


### Arrays
[ a • b • c ]

Equivalent:

["a", "b", "c"]

### Objects
{
    a ↦ b •
    c ↦ d
}

Equivalent:

{
  "a": "b",
  "c": "d"
}


### Operators 
#### 🏷 Tag Operator
Assigns a semantic ID to an expression.

"weather is sunny" 🏷 weather_info

Later references can point to it.

Think:
variable name

#### ※ Reference Operator
References previously tagged expressions.
※ weather_info

Can reference multiple:
※ [weather_info • rationale]

#### ⊨ Satisfies Operator
Marks that an expression satisfies a todo item.
call ↦ {...} ⊨ 1

Meaning:
this completed todo item 1

#### 𝑝 Confidence Operator
Confidence score for reasoning.
"Probably unsafe." 𝑝 0.7

Range:
0.0 → 1.0

### Structures
#### System
System instruction.
system「You are a helpful assistant.」🏷 sys1

#### tool
Tool definition.
tool {
    name ↦ get_weather •
    params ↦ {
        zip ↦ {
            type ↦ string
        }
    }
}


#### user
User input.

user「What is the weather?」🏷 usr1

#### todo
Internal task tracking.

todo {
    1 ↦ "Get weather." •
    2 ↦ "Respond to user."
}


Conceptually:

{
  "1": "Get weather.",
  "2": "Respond to user."
}

#### plan
planning phase

plan {
    todo ↦ {
        1 ↦ "Get weather." •
        2 ↦ "Respond."
    } •

    rationale ↦ "Need weather data first."
}


#### act
Reasoning and tool use phase.

##### Tool Call
act {
    call ↦ {
        tool ↦ get_weather •
        zip ↦ "94103" •
        id ↦ weather_result
    } ⊨ 1
}


##### Thinking
act {
    think ↦ (
        "68F is mild weather."
        🏷 rationale
        𝑝 0.9
        ※ weather_result
        ⊨ 2
    )
}

Important: 
tags apply to expressions
NOT blocks

Bad mental model:
act {} is tagged

Correct mental model: the thought string/result is tagged


##### result
Inserted tool result.

result {
    data ↦ "68F and cloudy."
} 🏷 weather_result

##### response
Final user-facing response. 
response「Wear a light sweater today.」
※ [weather_result • rationale]
⊨ 3


##### Full Trace
system「You are helpful.」🏷 sys1

tool {
    name ↦ get_weather
}

user「What should I wear today?」🏷 usr1

plan {
    todo ↦ {
        1 ↦ "Fetch weather." •
        2 ↦ "Determine clothing." •
        3 ↦ "Respond to user."
    }
}

act {
    call ↦ {
        tool ↦ get_weather •
        zip ↦ "94103" •
        id ↦ weather_result
    } ⊨ 1
}

result {
    data ↦ "68F and cloudy."
} 🏷 weather_result

act {
    think ↦ (
        "Light sweater weather."
        🏷 rationale
        𝑝 0.9
        ※ weather_result
        ⊨ 2
    )
}

response「Wear a light sweater.」
※ [weather_result • rationale]
⊨ 3
