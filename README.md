
Pipeline Description: (https://docs.google.com/document/d/1G2q9VHmLB9TpZHBJ88TisGf7KTQqaT0pjQw9Ole_CQY)

### Env Setup
- Install dependencies
```
pip install -r requirements.txt
```
- Config OpenAI API key:
- put your key under `source/run_gpt.py`

### Execute the pipelie
- ``` python run_coin.py --model MODEL --method METHOD --split SPLIT [--det] [--oc] ```
-  Example command ``` python run_coin.py --model gpt-4-1106-preview --method pddl --split dev --oc ```
  
-  `model`: OpenAI model names such as gpt-3.5-turbo-1106 or gpt-4-1106-preview
-  `method`: one of direct (Action-gen) or pddl (PDDL-gen and PDDL-edit)
-  `split`: one of dev or test, or a singular number to specify a specifc example of that index
-  `det`: must be used when method is pddl; if specified, use PDDL-edit, else PDDL-gen
-  `oc`: whether to overwrite existing cache; if not specified, will use the previous cache










