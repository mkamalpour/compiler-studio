"""Small, valid lessons and generators for the supported built-in languages."""

import random
from .samples import ricepy_sample, calculator_sample

TOPICS = {
    "Variables": "Give values a name. int is a whole number, string is text, and bool is true or false.",
    "Conditions": "Use if and else to describe choices. RicePy++ ends the complete choice with a semicolon.",
    "Loops": "A while loop describes repetition. The checker verifies its structure; it does not run the loop.",
    "Functions": "Group a calculation into a function, then call it with := to assign its result.",
    "Classes": "Group variables and functions inside a class using begin and end.",
    "Arrays & pointers": "Arrays hold indexed values. A pointer declaration uses * before its name.",
    "Complete program": "Combine variables, functions, classes and a loop. Try a simpler topic first if you are new.",
}
LEVELS = ("Simple", "Standard", "Advanced")

STARTER = '''# Change a value, then click Analyze code.
int score = 42;
string message = "Hello, Compiler Studio!";
bool ready = true;
'''


def make_example(language="RicePy++", topic="Variables", level="Simple", seed=None):
    if language not in {"RicePy++", "MiniCalc"} or (topic not in TOPICS and not (language == "MiniCalc" and topic == "Arithmetic")) or level not in LEVELS:
        raise ValueError("Choose an available language, topic and difficulty.")
    rng = random.Random(seed)
    count = LEVELS.index(level) + 1
    number = rng.randint(2, 25)
    if language == "MiniCalc":
        if level == "Simple":
            return f"{number} + {rng.randint(1, 9)}\n"
        return calculator_sample(seed) if level == "Standard" else f"({calculator_sample(seed).strip()}) + ({calculator_sample(rng.randint(0, 10000)).strip()})\n"
    if topic == "Variables":
        lines = [f"int score = {number};", 'string message = "Hello!";', "bool ready = true;"]
        if count > 1:
            lines += ["double price = 12.50;", "int hexValue = 0xFF;"]
        if count > 2:
            lines += ["const int limit = 100;", "global int total = score + 5;"]
        return "# Variables: names and their values\n" + "\n".join(lines) + "\n"
    if topic == "Conditions":
        middle = "" if count == 1 else ' elif (score == 10) {\n    score = score + 1;\n}'
        condition = "score > 10" if count < 3 else "score > 10 && score < 100"
        return f"int score = {number};\nif ({condition}) {{\n    score = score - 1;\n}}{middle} else {{\n    score = 0;\n}};\n"
    if topic == "Loops":
        extra = "" if count == 1 else "    if (count == 3) { continue; };\n"
        if count == 3:
            extra += "    if (count > 15) { break; };\n"
        return f"int count = 0;\nwhile (count < {number}) {{\n    count = count + 1;\n{extra}}};\n"
    if topic == "Functions":
        more = "" if count == 1 else "\nint function twice(value: int) {\n    return value * 2;\n}\nanswer := twice(answer);\n"
        if count == 3:
            more += '\nstring function greeting() {\n    return "Hello!";\n}\nstring message;\nmessage := greeting();\n'
        return f"int function add(a: int, b: int) {{\n    return a + b;\n}}\nint answer;\nanswer := add({number}, 2);\n{more}"
    if topic == "Classes":
        method = "" if count == 1 else "    int function twice(value: int) {\n        return value * 2;\n    }\n"
        extra = "    string label = \"Counter\";\n" if count == 3 else ""
        return f"class Counter\nbegin\n    int value = {number};\n{extra}{method}end\n"
    if topic == "Arrays & pointers":
        extra = "" if count == 1 else "int* pointer = null;\nvalues[1] = values[0] + 1;\n"
        if count == 3:
            extra += "int index = 0;\nwhile (index < 2) {\n    values[index] = index * 2;\n    index = index + 1;\n};\n"
        return f"int values[{number}];\nvalues[0] = 10;\n{extra}"
    if count == 1:
        return f"int count = 0;\nint function addOne(value: int) {{\n    return value + 1;\n}}\nwhile (count < {number}) {{\n    count := addOne(count);\n}};\n"
    program = ricepy_sample(seed)
    if count == 3:
        program += '\nstring function greeting() {\n    return "Hello!";\n}\nstring message;\nmessage := greeting();\n'
    return program
