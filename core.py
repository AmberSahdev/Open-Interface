from interpreter import Interpreter
from llm import LLM


class Core:
    def __init__(self):
        self.llm = LLM()
        self.interpreter = Interpreter()

    def run(self):
        print("Make sure to give the application Accessibility permissions in settings (to control mouse and keyboard), and Screen Recording permissions to take screenshots.")
        while True:
            user_request = input("\nEnter your request: ").strip()
            self.execute(user_request)

    def execute(self, user_request, step_num=0):
        """
            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        try:
            instructions = self.llm.get_instructions_for_objective(user_request, step_num)

            # Send to Interpreter and Executor
            success = self.interpreter.process(instructions["steps"])

            if not success:
                return "Unable to execute the request"
        except:
            return "Unable to execute the request"

        if instructions["done"]:
            # Communicate Results
            print(instructions["done"])
        else:
            # if not done, continue to next phase
            self.execute(user_request, step_num + 1)


Core().run()
