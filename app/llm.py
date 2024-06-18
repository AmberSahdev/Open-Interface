import json
import os
import time
from pathlib import Path
from typing import Any

from openai import ChatCompletion
from openai import OpenAI
from openai.types.beta.threads.message import Message

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

    function is the function name to call in the executer.
    parameters are the parameters of the above function.
    human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
    done is null if user request is not complete, and it's a string when it's complete that either contains the
        information that the user asked for, or just acknowledges completion of the user requested task. This is going
        to be communicated to the user if it's present.
    """

    # TODO
    # [x] switch to 4o
    # [ ] set response format to json
    # [ ] Remove json pleadings from context.txt
    # [ ] Add assistant mode
    # [ ] Look into function calling - https://platform.openai.com/docs/guides/function-calling
    # [ ] Function calling with assistants api - https://platform.openai.com/docs/assistants/tools/function-calling/quickstart

    def __init__(self):
        self.settings_dict: dict[str, str] = Settings().get_dict()

        self.model = self.settings_dict.get('model')
        if not self.model:
            self.model = 'gpt-4o'

        base_url = self.settings_dict.get('base_url', '')
        if not base_url:
            base_url = 'https://api.openai.com/v1/'
        base_url = base_url.rstrip('/') + '/'

        api_key = self.settings_dict.get('api_key')
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key

        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=base_url)

        self.context = self.read_context_txt_file()

        self.assistant = self.client.beta.assistants.create(
            name="Open Interface Backend",
            instructions=self.context,
            # tools=[],
            model="gpt-4o",
        )

        self.thread = self.client.beta.threads.create()

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
        return self.get_instructions_for_objective_v2(original_user_request, step_num)

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

    def get_instructions_for_objective_v2(self, original_user_request: str, step_num: int = 0) -> dict[str, Any]:
        # Upload screenshot to OpenAI
        openai_file_id_for_screenshot, temp_filename = self.upload_screenshot_and_get_file_id()

        # Format user request to send to LLM
        formatted_user_request = self.format_user_request_for_llm(original_user_request, step_num,
                                                                  openai_file_id_for_screenshot)

        # Read response
        llm_response = self.send_message_to_llm_v2(formatted_user_request)
        json_instructions: dict[str, Any] = self.convert_llm_response_to_json_v2(llm_response)

        # Cleanup file from filesystem and OpenAI
        os.unlink(temp_filename)
        self.client.files.delete(openai_file_id_for_screenshot)

        return json_instructions

    def upload_screenshot_and_get_file_id(self):
        # Files are used to upload documents like images that can be used with features like Assistants
        # Assistants API cannot take base64 images like chat.completions API
        filepath = Screen().get_temp_filename_for_current_screenshot()  # in-memory files don't work with the API because of missing filename attribute

        response = self.client.files.create(
            file=open(filepath, 'rb'),
            purpose='vision'
        )
        return response.id, filepath

    def send_message_to_llm_v2(self, formatted_user_request) -> Message:
        message = self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=formatted_user_request
        )

        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id,
            instructions=''
        )

        while run.status != 'completed':
            print("Waiting for response, sleeping for 0.1")
            time.sleep(0.1)

        if run.status == 'completed':
            # TODO: Apparently right now the API doesn't have a way to retrieve just the last message???
            #  So instead you get all messages and take the latest one
            response = self.client.beta.threads.messages.list(
                thread_id=self.thread.id
            )

            print(f"retunr type: {type(response.data[0])}")
            return response.data[0]
        else:
            print("Run did not complete successfully.")
            return None

    def format_user_request_for_llm(self, original_user_request, step_num, openai_file_id_for_screenshot) -> list[
        dict[str, Any]]:
        request_data: str = json.dumps({
            'original_user_request': original_user_request,
            'step_num': step_num
        })

        content = [
            {
                'type': 'text',
                'text': request_data
            },
            {
                'type': 'image_file',
                'image_file': {
                    'file_id': openai_file_id_for_screenshot
                }
            }
        ]

        return content

    def convert_llm_response_to_json_v2(self, llm_response: ChatCompletion) -> dict[str, Any]:
        llm_response_data: str = llm_response.content[0].text.value.strip()

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
