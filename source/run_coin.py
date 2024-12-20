import requests, sys
import time
import os
import random
random.seed(29)
from textworld_express import TextWorldExpressEnv
from run_gpt import run_chatgpt
import argparse
from pathlib import Path
import pickle
import backoff
import urllib3
import json
from fix_json import fix_json

urllib3.disable_warnings()

parser = argparse.ArgumentParser()
parser.add_argument('--model', default='gpt-4-1106-preview', type=str, help='OpenAI model name.')
parser.add_argument('--method', default='', required=True, type=str, help='direct|pddl')
parser.add_argument('--det', action='store_true', help='Whether to deterministically edit the problem file. Assumes method is pddl.')
parser.add_argument('--oc', action='store_true', help='Whether to overwrite the cache.')
parser.add_argument('--split', default='dev', required=True, type=str, help='Dev set includes seed of 0-9, test set includes seed of 10-109.')

args = parser.parse_args()


# Initialize game generator
env = TextWorldExpressEnv(envStepLimit=100)

# Set the game generator to generate a particular game (cookingworld, twc, or coin)
NUM_LOCATIONS = 11
MAX_STEPS = 30
env.load(gameName="coin", gameParams=f"numLocations={NUM_LOCATIONS},numDistractorItems=0,includeDoors=1,limitInventorySize=0")
MAX_RETRY = 3

@backoff.on_exception(backoff.expo, (ConnectionResetError, requests.exceptions.ConnectionError))
def post_pddl(data):

    # Send job request to solve endpoint
    resp = requests.post('https://solver.planning.domains:5001/package/dual-bfws-ffparser/solve',
                        verify=False, json=data).json()
    #timeout = 5
    
    print("Output of job request", resp)
    print("resp[]", resp['result']) 

    # Query the result in the job
    celery_result=requests.post('https://solver.planning.domains:5001' + resp['result'])
    print("celery_result", celery_result)

    while celery_result.json().get("status","")== 'PENDING':
        # Query the result every 0.5 seconds while the job is executing
        celery_result=requests.post('https://solver.planning.domains:5001' + resp['result'])
        time.sleep(0.5)

    result = celery_result.json()['result']
    print("Printing response:", result)
    return result

def llm_direct(past_prompt, obs, valid_actions):
    if not past_prompt:
        past_prompt = [
            {"role": "user", "content": "You will play a game where your goal is to collect a coin. I will provide you with a description of the environment, and you will take one of the valid actions. Ready?"},
            {"role": "assistant", "content": "Absolutely, I'm ready! Please describe the environment."},
        ]
    prompt = past_prompt + [
        {"role": "user", "content": obs + "\n\n" + "Your valid actions are: " + str(valid_actions) + "\n\n" + "Which action do you take?"},
    ]
    output = run_chatgpt(prompt, model=args.model, temperature=1)
    taken_action = ""
    for valid_action in valid_actions:
        if valid_action in output:
            taken_action = valid_action
            break
    prompt += [
        {"role": "assistant", "content": taken_action},
    ]
    return prompt, [taken_action]

def llm_pddl(past_prompt, obs, valid_actions, prev_pf=""):
    def apply_edit(prev_pf, edit_json):
        #print(prev_pf)
        output = []
        o_start = False
        i_start = False
        # Manually cascade location replace
        #loc_replace = {}
        #for s,t in edit_json["objects"]["replace"].items():
        #    if s.endswith(" - location") and t.endswith(" - location"):
        #        loc_replace[s[:-len(" - location")]] = t[:-len(" - location")]

        for line in prev_pf.split("\n"):
            if "(:object" in line:
                o_start = True
                output.append(line)
            elif o_start and line.strip() == ")":
                o_start = False
                if "add" in edit_json["objects"]:
                    for to_add in edit_json["objects"]["add"]:
                        output.append("    " + to_add)
                output.append(line)
            elif o_start:
                if "replace" in edit_json["objects"] and line.strip() in edit_json["objects"]["replace"]:
                    line = edit_json["objects"]["replace"][line.strip()]
                    output.append("    " + line)
                elif "delete" in edit_json["objects"] and line.strip() in edit_json["objects"]["delete"]:
                    continue
                else:
                    output.append(line)
            elif "(:init" in line:
                i_start = True
                output.append(line)
            elif i_start and line.strip() == ")":
                i_start = False
                if "add" in edit_json["init"]:
                    for to_add in edit_json["init"]["add"]:
                        output.append("    " + to_add)
                output.append(line)
            elif i_start:
                if "replace" in edit_json["init"] and line.strip() in edit_json["init"]["replace"]:
                    line = edit_json["init"]["replace"][line.strip()]
                    try:
                        output.append("    " + line)
                    except TypeError:
                        continue
                elif "delete" in edit_json["init"] and line.strip() in edit_json["init"]["delete"]:
                    continue
                else:
                    output.append(line)
            else:
                output.append(line)
        
        output_str = "\n".join(output)
        # Manually cascade location replace using a crude replace
        #for s, t in loc_replace.items():
        #    output_str = output_str.replace(s, t)
        
        return output_str


    if not args.det:
        prompt_file = "coin_prompt.txt"
        new_wording = "Your task is to go to a location you have not been yet. Generate a problem file."
    else:
        prompt_file = "coin_det_prompt.txt"
        new_wording = "You will modify the above problem file using add, delate, and replace operations (in a JSON format). You SHOULD NOT provide a problem file directly."
    if not past_prompt:
        prompt = [
            {"role": "user", "content": open(prompt_file, "r").read() + obs + "\n\n" + new_wording},
        ]
    else:
        prompt = []
        for i, message in enumerate(past_prompt):
            # remove previous display of PF
            if i < len(past_prompt) - 2 and message["content"].startswith("After your previous edits"):
                continue
            if i < len(past_prompt) - 2 and message["content"] == "OK, I will base my edit on this problem file.":
                continue
            prompt.append(message)
        prompt += [
            {"role": "user", "content": obs + "\n\n" + new_wording},
        ]
    #print(prompt)
    #raise SystemExit()
    
    df = open("coin_df.pddl", "r").read()
    cache_name = "cache_coin.pkl"
    try:
        cache = pickle.load(open(cache_name, "rb"))
    except FileNotFoundError:
        pickle.dump({}, open(cache_name, "wb"))
        cache = pickle.load(open(cache_name, "rb"))
    if not args.oc:
        output = cache[(NUM_LOCATIONS, episode_id, step_id)]
    else:
        retry_count = 0
        has_plan = False
        while not has_plan and retry_count < MAX_RETRY:
            force_json = True if args.det else False
            output = run_chatgpt(prompt, model=args.model, temperature=1, force_json=force_json)
            cache[(NUM_LOCATIONS, episode_id, step_id)] = output
            pickle.dump(cache, open("cache.pkl", "wb"))

            #print(output)
            def parse(output):
                processed_output = []
                begin = False
                for line in output.split("\n"):
                    if line.startswith("(define "):
                        begin = True
                    if begin:
                        processed_output.append(line)
                    if line.startswith(")"):
                        break
                return "\n".join(processed_output)
            #raise SystemExit
            if args.det:
                print("Printing Output here: " ,output)
                out_json = json.loads(output)
                try:
                    pf = apply_edit(prev_pf, out_json)
                except KeyError:
                    retry_count += 1
                    print("Edit JSON invalid. Retrying...")
                    continue
            else:
                pf = parse(output)
            print("Printing pf:", pf)
            #raise SystemExit

            data = {'domain': df,
                'problem': pf}
            print("Printing data: ", data)
            resp = post_pddl(data)
            #print(resp)
            try:
                actions_output = resp['output']['plan']
                actions_output = actions_output.lower()
                actions = actions_output.split("\n")
                actions = list(filter(None, actions))
                print("actions", actions)
                #if actions == ['(reach-goal)']:
                #    raise KeyError
                if actions == []:
                    raise KeyError
                has_plan = True
                prev_pf = pf
            except (KeyError,TypeError):
                retry_count += 1
                print("No plan found. Retrying...")
                continue
            #    return prompt, []
            #print(actions)
    if not has_plan:
        return prompt, [], prev_pf
    if not args.det:
        prompt += [
            {"role": "assistant", "content": pf},
        ]
    else:
        prompt += [
            {"role": "assistant", "content": output},
            {"role": "user", "content": "After your previous edits, the current problem file is:\n\n" + pf + "\n\n" + "Please make more edits based on this problem file."},
            {"role": "assistant", "content": "OK, I will base my edit on this problem file."},
        ]
    if isinstance(actions[0], str):
        if '(reach-goal)' in actions:
            actions.remove('(reach-goal)')
    elif isinstance(actions[0], dict):
        actions = [x['name'] for x in actions]
    def map_actions(action):
        # move action
        # (move kitchen corridor west)
        if "(move " in action:
            action = action.replace("(", "").replace(")", "").split(" ")
            action = action[0] + " " + action[-1]
        # open door action
        # open_door l1
        elif "(open_door " in action:
            _, source, target = action.replace("(", "").replace(")", "").split(" ")
            direction = ""
            for line in pf.split("\n"):
                if "(connected" in line:
                    loc_source = line.split("(connected ")[1].split(" ")[0]
                    loc_target = line.split("(connected ")[1].split(" ")[1]
                    if loc_source == source and loc_target == target:
                        direction = line.split("(connected ")[1].split(" ")[2].split(")")[0]
                        break
            action = "open door to " + direction
        return action
    print("before map actions", actions)
    actions = list(map(map_actions, actions))
    print("after map actions", actions)
    #raise SystemExit

    #taken_action = actions[0]
    return prompt, actions, prev_pf

# Then, randomly generate and play 10 games within the defined parameters
steps_to_success = []
if args.split == "dev":
    seeds = range(0,10)
elif args.split == "test":
    seeds = range(10,60)
else:
    seeds = range(int(args.split), int(args.split) + 1)
#play 1 game only
seeds = 1
#for episode_id in range(0,10):
for episode_id in range(1):
    # First step
    obs, infos = env.reset(seed=episode_id, gameFold="train", generateGoldPath=True)
    print("obs :",obs)
    print("infos :", infos)

    print("Gold path: " + str(env.getGoldActionSequence()))
    # Display the observations from the environment.
    def summarize_obs(obs):
        # If obs only has one line, return it
        if len(obs.split('\n')) == 1:
            return obs
        # Only keep where you are and location informtion
        else:
            return obs.split('\n')[0].split(". ")[0] + ". " + obs.split('\n')[1]
    #print("Obs is: " + obs)
    brief_obs = "Action: look around\n" + summarize_obs(obs)
    print(brief_obs)
    past_prompt = []
    action_queue = []
    obs_queue = []
    if args.det:
        prev_pf = open("coin_init_pf.pddl", "r").read()
    for step_id in range(0, MAX_STEPS):
        print("Step " + str(step_id))
        # If there is a coin, just take it
        if " coin" in obs:
            taken_action = "take coin"
        else:
            # Select a valid action
            valid_actions = sorted(infos['validActions'])
            valid_actions.remove('look around')
            valid_actions.remove('inventory')
            if args.method == "random":
                taken_action = random.choice(valid_actions)
            else:
                # Check action queue for remaining actions
                if not action_queue:
                    if obs_queue:
                        brief_obs = "\n".join(obs_queue)
                        obs_queue = []
                    if args.method == "direct":
                        past_prompt, actions = llm_direct(past_prompt, brief_obs, valid_actions)
                    elif args.method == "pddl":
                        if args.det:
                            past_prompt, actions, prev_pf = llm_pddl(past_prompt, brief_obs, valid_actions, prev_pf)

                            print("Priting some checks now:")
                            print(past_prompt)
                            print(actions)
                            print(prev_pf)
                        else:
                            #try:
                            past_prompt, actions, _ = llm_pddl(past_prompt, brief_obs, valid_actions)
                            if not actions:
                                steps_to_success.append(-1)
                                break
                    action_queue += actions
                if action_queue:
                    taken_action = action_queue.pop(0)
                    # if planned action is invalid, allow it
                    #if taken_action not in valid_actions:
                    #    raise ValueError("Invalid action")
                    #    steps_to_success.append(-1)
                    #    break
                else:
                    #raise ValueError("No plan is found")
                    steps_to_success.append(-1)
                    break
                    print("No plan is found. ", "Taking random action")
                    taken_action = random.choice(valid_actions)

        # Take that action
        obs, reward, done, infos = env.step(taken_action)
        brief_obs = "Action: " + taken_action + "\n" + summarize_obs(obs)
        obs_queue.append(brief_obs)

        # Display action and the game's feedback.
        print(">", taken_action)
        print(brief_obs)
        if done:
            steps_to_success.append(step_id)
            break
    else:
        steps_to_success.append(-1)

print(steps_to_success)
# print portion of numbers larger than or equal to zero
print(sum(x >= 0 for x in steps_to_success) / len(steps_to_success))