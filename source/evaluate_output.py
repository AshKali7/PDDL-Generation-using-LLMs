import os
import openai
import backoff
import argparse
from pathlib import Path
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument('--key', default='harry_ccbft', type=str, help='The name of the OpenAI API key file.')
parser.add_argument('--model', default='', required=True, type=str, help='OpenAI model name.')

args = parser.parse_args()

results = []
fpath = f"../processed_output/{args.model}/solve_result"
for fname in os.listdir(fpath):
    with open(os.path.join(fpath, fname)) as f:
        output = f.read().strip()
        if output.startswith("Error: Running time"):
            results.append("Timeout")
        elif output.startswith("Error:"):
            results.append("Syntax Error")
            print(output)
        elif output == "No solution":
            results.append("No solution")
        else:
            results.append("Success")

result_count = Counter(results)
print(result_count)