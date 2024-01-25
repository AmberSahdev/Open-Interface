import json

from openai import OpenAI

from utils.screen import Screen
from utils import local_info

class LLM:
    """
    LLM Request
    {
    	"original_user_request": ...,
    	"step_num": ...,
    	"screenshot": ...
    }

    step_num is the count of times we've interacted with the LLM for this user request. If it's 0 we know it's a fresh user request,
    	if it's greater than 0 then we know we are already in the middle of a request.
    	Therefore, if the number is positive and from the screenshot it looks like request is complete, then return an empty list in steps and a string in done. Don't keep looping the same request.

    Expected LLM Response
    {
    	"steps": [
    		{
    			"function": "...",
    			"parameters": {
    				"key1": "value1",
    				...
    			},
    			"human_readable_justification": "..."
    		},
    		{...},
    		...
    	],
    	"done": ...
    }

    function is the function name to call in the executor.
    parameters are the parameters of the above function.
    human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
    done is None if user request is not complete, and it's a string when it's complete that either contains the information that the user asked for, or just acknowledges completion of the user requested task. This is going to be communicated to the user if it's present.
    """

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4-vision-preview"

        with open('context.txt', 'r') as file:
            self.context = file.read()

        self.context += f"\nDefault browser is {local_info.default_browser}."
        self.context += f" Locally installed apps are {','.join(local_info.locally_installed_apps)}."
        self.context += f" Primary screen size is {Screen().get_size()}.\n"


    def get_instructions_for_objective(self, original_user_request, step_num=0):
        message = self.create_message_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions = self.convert_llm_response_to_json(llm_response)

        return json_instructions

    def create_message_for_llm(self, original_user_request, step_num):
        base64_img = Screen().get_screenshot_in_base64()

        request_data = json.dumps({
            "original_user_request": original_user_request,
            "step_num": step_num
        })

        message = [
            {"type": "text", "text": self.context + request_data},
            {"type": "image_url",
             "image_url": {
                 "url": f"data:image/jpeg;base64,{base64_img}"
             }
             }
        ]

        return message

    def send_message_to_llm(self, message):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": message,
                }
            ],
            max_tokens=800,
        )
        return response

    def convert_llm_response_to_json(self, llm_response):
        llm_response_data = llm_response.choices[0].message.content.strip()

        # Our current LLM model does not guarantee a JSON response, hence we manually parse the JSON part of the response
        start_index = llm_response_data.find("{")
        end_index = llm_response_data.rfind("}")

        #json_response = eval(llm_response_data[start_index:end_index + 1])
        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f"llm_response_data[start_index:end_index + 1] - {llm_response_data[start_index:end_index + 1]}")
            print(f"Error: {e}")
            json_response = {}

        return json_response
