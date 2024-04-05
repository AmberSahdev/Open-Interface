import json
import os
from pathlib import Path
from typing import Any

from openai import ChatCompletion
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
        settings_dict: dict[str, str] = Settings().get_dict()

        base_url = settings_dict.get('base_url', 'https://api.openai.com/v1/').rstrip('/') + '/'
        api_key = settings_dict.get('api_key')
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        path_to_context_file = Path(__file__).resolve().parent.joinpath('resources', 'context.txt')
        with open(path_to_context_file, 'r') as file:
            self.context = file.read()

        self.context += f' Locally installed apps are {",".join(local_info.locally_installed_apps)}.'
        self.context += f' OS is {local_info.operating_system}.'
        self.context += f' Primary screen size is {Screen().get_size()}.\n'

        if 'default_browser' in settings_dict.keys() and settings_dict['default_browser']:
            self.context += f'\nDefault browser is {settings_dict["default_browser"]}.'

        if 'custom_llm_instructions' in settings_dict:
            self.context += f'\nCustom user-added info: {settings_dict["custom_llm_instructions"]}.'

        self.client = OpenAI()

        self.model = settings_dict.get('model')
        if not self.model:
            self.model = 'gpt-4-vision-preview'
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        message: list[dict[str, Any]] = self.create_message_for_llm(original_user_request, step_num)
        llm_response = self.send_message_to_llm(message)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json(llm_response)

        return json_instructions

    def create_message_for_llm(self, original_user_request, step_num) -> list[dict[str, Any]]:
        base64_img: str = Screen().get_screenshot_in_base64()

        request_data: str = json.dumps({
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

    def send_message_to_llm(self, message) -> ChatCompletion:
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

    def convert_llm_response_to_json(self, llm_response: ChatCompletion) -> dict[str, Any]:
        llm_response_data: str = llm_response.choices[0].message.content.strip()

        # Our current LLM model does not guarantee a JSON response hence we manually parse the JSON part of the response
        # Check for updates here - https://platform.openai.com/docs/guides/text-generation/json-mode
        start_index = llm_response_data.find('{')
        end_index = llm_response_data.rfind('}')

        try:
            json_response = json.loads(llm_response_data[start_index:end_index + 1].strip())
        except Exception as e:
            print(f'Error while parsing JSON response - {e}')
            json_response = {}

        return json_response
