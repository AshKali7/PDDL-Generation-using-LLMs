from openai import OpenAI

client = OpenAI(api_key="")
import backoff


#@backoff.on_exception(backoff.expo, (OpenAI.error.RateLimitError, OpenAI.error.APIError, OpenAI.error.Timeout, OpenAI.error.ServiceUnavailableError))
def run_chatgpt(message, model, force_json=False, temperature=0):
    output_format = "json_object" if force_json else "text"

    ret = client.chat.completions.create(model=model,
    messages=message,
    max_tokens = 1000,
    response_format = {"type": output_format})
    #print(ret)
    #print(dict(ret.choices[0].message)['content'])
    gen_text = dict(ret.choices[0].message)['content']
    return gen_text