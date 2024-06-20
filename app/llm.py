from pathlib import Path
from typing import Any

from models.factory import ModelFactory
from utils import local_info
from utils.screen import Screen
from utils.settings import Settings

DEFAULT_MODEL_NAME = "gpt-4o"


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

    function is the function name to call in the executer.
    parameters are the parameters of the above function.
    human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
    done is null if user request is not complete, and it's a string when it's complete that either contains the
        information that the user asked for, or just acknowledges completion of the user requested task. This is going
        to be communicated to the user if it's present.
    """

    def __init__(self):
        self.settings_dict: dict[str, str] = Settings().get_dict()
        model_name, base_url, api_key = self.get_settings_values()

        self.model_name = model_name
        context = self.read_context_txt_file()

        self.model = ModelFactory.create_model(self.model_name, base_url, api_key, context)

    def get_settings_values(self) -> tuple[str, str, str]:
        model_name = self.settings_dict.get('model')
        if not model_name:
            model_name = DEFAULT_MODEL_NAME

        base_url = self.settings_dict.get('base_url', '')
        if not base_url:
            base_url = 'https://api.openai.com/v1/'
        base_url = base_url.rstrip('/') + '/'

        api_key = self.settings_dict.get('api_key')

        return model_name, base_url, api_key

    def read_context_txt_file(self) -> str:
        # Construct context for the assistant by reading context.txt and adding extra system information
        context = ''
        path_to_context_file = Path(__file__).resolve().parent.joinpath('resources', 'context.txt')
        with open(path_to_context_file, 'r') as file:
            context += file.read()

        context += f' Locally installed apps are {",".join(local_info.locally_installed_apps)}.'
        context += f' OS is {local_info.operating_system}.'
        context += f' Primary screen size is {Screen().get_size()}.\n'

        if 'default_browser' in self.settings_dict.keys() and self.settings_dict['default_browser']:
            context += f'\nDefault browser is {self.settings_dict["default_browser"]}.'

        if 'custom_llm_instructions' in self.settings_dict:
            context += f'\nCustom user-added info: {self.settings_dict["custom_llm_instructions"]}.'

        return context

    def get_instructions_for_objective(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        return self.model.get_instructions_for_objective(original_user_request, step_num)

    def cleanup(self):
        self.model.cleanup()
