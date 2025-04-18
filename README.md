# calc.ai
Transformer-based Calculator

## Training Data

The training data in the [`samples/`](samples/) directory was generated using
the `calc.ai generate-data` command.  The following arguments were used for each
sample file:

| File | `generate-data` Arguments |
|------|-----------|
|[`depth1.jsonl`](samples/depth1.jsonl)|`-n 5000 -d 1 -m 50`|
|[`depth2.jsonl`](samples/depth2.jsonl)|`-n 5000 -d 2 -m 50 --generate-solutions`|
|[`depth3.jsonl`](samples/depth3.jsonl)|`-n 5000 -d 3 -m 50 --generate-solutions`|

## Calculator Grammar

```ebnf
script = { line }, EOF;

(*
    A line can either be an expression like "1 + 2" or an assignment like
    "x = 3 + 4".
*)
line = [ variable, { whitespace }, "=" ], { whitespace }, expression, NEWLINE;

(*
    Expressions follow the BEDMAS precedence. This means starting with
    addition/subtraction for rule matching.
*)
expression = addsub;
addsub = muldiv, { ( "+" | "-" ), muldiv };
muldiv = exp, { ( "*" | "/" ), exp };
exp = unary, { "^", unary };

unary = [ "+" | "-" ], ( number | variable | ( "(", expression, ")" ) );

alpha = ? lower case a-z ?;
integer = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9";
number = integer, { integer };
variable = alpha, { alpha }, { number };

EOF = ? end-of-file ?;
NEWLINE = ? newline character ?
```
