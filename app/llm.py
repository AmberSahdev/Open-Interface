import json
import os

from openai import OpenAI

from utils import local_info
from utils.screen import Screen
from utils.settings import Settings


class LLM:
    """
    LLM Request
    {
    	"original_user_request": ...,
    	"step_num": ...,
    	"screenshot": ...
    }

    step_num is the count of times we've interacted with the LLM for this user request.
        If it's 0, we know it's a fresh user request.
    	If it's greater than 0, then we know we are already in the middle of a request.
    	Therefore, if the number is positive and from the screenshot it looks like request is complete, then return an
    	    empty list in steps and a string in done. Don't keep looping the same request.

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
    done is null if user request is not complete, and it's a string when it's complete that either contains the
        information that the user asked for, or just acknowledges completion of the user requested task. This is going
        to be communicated to the user if it's present.

    Note: Use code below to check whether gpt4v has assistant support yet.
        from openai import OpenAI
        client = OpenAI()
        assistant = client.beta.assistants.create(
            name="bot",
            instructions="bot",
            model="gpt-4-vision-preview",
            tools=[{"type": "code_interpreter"}]
        )
    """

    def __init__(self):
        settings_dict = Settings().get_dict()
        if settings_dict['api_key']:
            os.environ["OPENAI_API_KEY"] = settings_dict['api_key']

        with open('./resources/context.txt', 'r') as file:
            self.context = file.read()

        if settings_dict['default_browser']:
            self.context += f'\nDefault browser is {settings_dict["default_browser"]}.'

        self.context += f' Locally installed apps are {",".join(local_info.locally_installed_apps)}.'
        self.context += f' OS is {local_info.operating_system}.'
        self.context += f' Primary screen size is {Screen().get_size()}.\n'

        self.client = OpenAI()
        self.model = 'gpt-4-vision-preview'

    def get_instructions_for_objective(self, original_user_request, step_num=0):
        message = self.create_message_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions = self.convert_llm_response_to_json(llm_response)

        return json_instructions

    def create_message_for_llm(self, original_user_request, step_num):
        base64_img = Screen().get_screenshot_in_base64()

        request_data = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num
        })

        # We have to add context every request for now which is expensive because our chosen model doesn't have a
        #   stateful/Assistant mode yet.
        message = [
            {'type': 'text', 'text': self.context + request_data},
            {'type': 'image_url',
             'image_url': {
                 'url': f'data:image/jpeg;base64,{base64_img}'
             }
             }
        ]

        return message

    def send_message_to_llm(self, message):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    'role': 'user',
                    'content': message,
                }
            ],
            max_tokens=800,
        )
        return response

    def convert_llm_response_to_json(self, llm_response):
        llm_response_data = llm_response.choices[0].message.content.strip()

        # Our current LLM model does not guarantee a JSON response, hence we manually parse the JSON part of the response
        # Check for updates here - https://platform.openai.com/docs/guides/text-generation/json-mode
        start_index = llm_response_data.find('{')
        end_index = llm_response_data.rfind('}')

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'llm_response_data[start_index:end_index + 1] - {llm_response_data[start_index:end_index + 1]}')
            print(f'Error while parsing JSON response - {e}')

            # TODO: Temporary for debugging
            with open("faulty_json_recieved.json", "w") as f:
                f.write(llm_response_data[start_index:end_index + 1].strip())

            json_response = {}

        return json_response
