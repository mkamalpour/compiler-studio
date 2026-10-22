"""Generate syntactically valid examples without executing target-language code."""

import random


def ricepy_sample(seed=None):
    rng = random.Random(seed)
    limit, increment = rng.randint(3, 25), rng.randint(1, 7)
    return f'''# Generated RicePy++ example
""" Lexical analysis and grammatical analysis share one token stream. """
global int count = 0;
const double scale = 2.5;
int values[10];
int* pointer = null;

int function add(left: int, right: int) {{
    return left + right;
}}

class Calculator
begin
    int total = 0;
    int function twice(value: int) {{
        return value * 2;
    }}
end

while (count < {limit}) {{
    count = count + {increment};
    if (count == 2) {{
        continue;
    }} elif (count > 20) {{
        break;
    }} else {{
        values[0] = count;
    }};
}};

count := add(count, 0x0A);
'''


def calculator_sample(seed=None):
    rng = random.Random(seed)
    return f"({rng.randint(1, 30)} + {rng.randint(1, 30)}) * {rng.randint(1, 9)}\n"
