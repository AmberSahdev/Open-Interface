class Core:
	def __init__():
		self.llm = LLM()
		

	def run():
		while True:
			user_request = input()
			execute(user_request)
			
			
	def execute(user_request, subsequent_app_request=""):
		# Send to LLM
		instructions = self.llm.get_instructions_for_objective(user_request, subsequent_app_request)

		# Send to Interpreter and Executor 
		# GPTToLocalInterface.py

		if done:
			# TODO: Communicate Results 
		else:
			# if not done, continue to next phase
			execute(user_request, instructions["subsequent_app_request"])