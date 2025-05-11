# calc.ai

A transformer-based calculator.

## Quickstart

> [!NOTE]
> This project uses the `uv` package/project manager.  See the
> [`uv` docs](https://docs.astral.sh/uv/) on how to install it on your system.

Clone this repo and then initialize the virtual environment with

```bash
uv sync --extra cpu
source .venv/bin/activate
```

The first thing to do is train a "calculator language model" (CLM).  The
`samples/` directory contains training data of varying levels of complexity,
ranging from integers to complex expressions such as

```
-(49 / 18) - 15 - 35 + 24
```

You can train a CLM either straight from a single data set or in stages.  The
`train-model` command has a `--retrain`/`-r` option that performs supervised
fine tuning on a pre-trained model.  This multi-stage training will look like:

```bash
# Train the model so it can recognize the basic CLM grammar.  Two epochs are
# usually enough to get 100% validation accuracy.
calc.ai train-model -e 2 samples/depth0.jsonl

# Train the model to solve progressively more complex expressions.
calc.ai train-model -r models/model-001.pt -e 10 samples/depth1.jsonl
calc.ai train-model -r models/model-002.pt -e 10 samples/depth2.jsonl
```

The main way to interact with the model is via the calc.ai REPL:

```bash
calc.ai repl
```

This uses the last trained model by default.  You can pick another model with
`--model`.

### Training Reports

A training report will be stored in `models/report-###/` after each training
run.  The report will show training loss over time as well as the model's
validation metrics.  It reports two metrics:

* Accuracy
  * The percentage of validation samples where the model produces the correct
    answer, e.g., `1 + 2 = 3`.
* Percent Invalid
  * The percentage of validation samples where the model produced something that
    could not be parsed.

The ideal case is that the accuracy is 100% and the percent invalid samples is
0%.  Usually the CLM learns to output valid strings within an epoch or two.  The
accuracy is a different story since it's learning patterns in the training data,
not the rules for addition, multiplication, etc.

## Training Data

The training data in the [`samples/`](samples/) directory was generated using
the `calc.ai generate-data` command.  The following arguments were used for each
sample file:

| File | `generate-data` Arguments |
|------|-----------|
|[`depth0.jsonl`](samples/depth0.jsonl)|`-m 5000 --numbers-only`|
|[`depth1.jsonl`](samples/depth1.jsonl)|`-n 5000 -d 1 -m 50`|
|[`depth2.jsonl`](samples/depth2.jsonl)|`-n 5000 -d 2 -m 50 --generate-solutions`|
|[`depth3.jsonl`](samples/depth3.jsonl)|`-n 5000 -d 3 -m 50 --generate-solutions`|

## Grammars

### Interpreter Grammar

The grammar below is used by the interpreter that generates and validates the
language model's output.  The language model itself may, or may not, be able to
parse this grammar.  It depends entirely on how the model is trained.

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
NEWLINE = ? newline character ?;
```

### CLM Grammar

The CLM is trained to understand a simple markup language that splits up the
inputs and outputs of the CLM into distinct sections.  In general, it extends
the interpreter grammar since the CLM is supposed to be able to process the same
text.

```ebnf
clm_input = expr_tag;                              (* Expected CLM input structure.  *)
clm_output = expr_tag, [ steps_tag ], result_tag;  (* Expected CLM output structure. *)

(*
    An expression tag will contain the arithmetic expression that the CLM is
    being asked to solve.
*)
expr_tag = "{expr=}", INTERPRETER_LINE, { INTERPRETER_LINE }, "{=expr}";

(*
    A steps tag will contain the steps needed to solve provided arithmetic
    expression.  It has an identical structure to the expression tag.
*)
steps_tag = "{steps=}", INTERPRETER_LINE, { INTERPRETER_LINE }, "{=steps}";

(*
    A result tag will contain the final calculation result.  This must be a
    number.
*)
result_tag = "{result=}", number, "{=result}";
integer = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9";
number = [ "-" ], integer, { integer };

NEWLINE = ? newline character ?;
INTERPRETER_LINE = ? calculator interpreter line ?;
```
