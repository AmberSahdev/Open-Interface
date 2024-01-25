"""
LLM Request 
{
	"original_user_request": ...,
	"subsequent_app_request": ...,
	"screenshot": ...
}

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
	"subsequent_app_request": ...,
	"done": ...
}

subsequent_app_request in the request is empty on the first run and subsequently filled in by the response as needed.
It is used by LLMs to checkpoint their progress and recieve new screenshots after reaching a certain point in execution.

function is the function name to call in the executor.
parameters are the parameters of the above function. 
human_readable_justification is what we can use to debug in case program fails somewhere or to explain to user why we're doing what we're doing.
"""

class LLM:
	def __init__():
		self.client = OpenAI()
		self.model = "gpt-4-vision-preview"


        with open('context.txt', 'r') as file:
            self.context = file.read()

        # TODO: Add local info here such as screen size, etc to the context

	def get_instructions_for_objective(original_user_request, subsequent_app_request=""):
		message = create_message_for_llm(original_user_request, subsequent_app_request)
		llm_response = send_message_to_llm(message)
		json_instructions = convert_llm_response_to_json(llm_response)

		return json_instructions


	def create_message_for_llm(original_user_request, subsequent_app_request=""):
		base64_img = Screen().get_screenshot_in_base64()

		request_data = json.dumps({
            "original_user_request": original_user_request,
            "subsequent_app_request": subsequent_app_request
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

	def send_message_to_llm(message):
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

    def convert_llm_response_to_json(llm_response):
    	llm_response_data = llm_response.choices[0].message.content.strip()

    	# Our current LLM model does not guarantee a JSON response, hence we manually parse the JSON part of the response
        start_index = llm_response_data.find("{")
        end_index = llm_response_data.rfind("}")
        json_response = eval(llm_response_data[start_index:end_index+1])

    	return json_response
