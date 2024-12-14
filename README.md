
Pipeline Description: (https://docs.google.com/document/d/1G2q9VHmLB9TpZHBJ88TisGf7KTQqaT0pjQw9Ole_CQY)

### Env Setup
- Install dependencies
```
pip install -r requirements.txt
```
- Config OpenAI API key:
- put your key under `source/run_gpt.py` and `config/api_config.json`

### Generate World (Domain) Models - Domain PDDL file
To leverage an LLM to construct a domain model, you need to provide the following information:
- Natural language descriptions of all the actions. Example: `prompts/logistics/action_model.json`.
- A description of the domain. Example: `prompts/logistics/domain_desc.txt`.
- Information of the object types and hierarchy. Example: `prompts/logistics/hierarchy_requirements.json`.

Then, in the script `construct_action_models.py`, specify the domain and the LLM model (and other configurations if needed). When this script is executed, the LLM will generate PDDL models for all actions in turn. Includes a simple PDDL syntax validator (`pddl_syntax_validator.py`) in Python.

- command ``` python construct_action_models.py```

### Generate the Problem PDDL file and Execute the pipeline
- ``` python run_coin.py --model MODEL --method METHOD --split SPLIT [--det] [--oc] ```
- Example command ``` python run_coin.py --model gpt-4-1106-preview --method pddl --split dev --oc ```
  
-  `model`: OpenAI model names such as gpt-3.5-turbo-1106 or gpt-4-1106-preview
-  `method`: one of direct (Action-gen) or pddl (PDDL-gen and PDDL-edit)
-  `split`: one of dev or test, or a singular number to specify a specifc example of that index
-  `det`: must be used when method is pddl; if specified, use PDDL-edit, else PDDL-gen
-  `oc`: whether to overwrite existing cache; if not specified, will use the previous cache










