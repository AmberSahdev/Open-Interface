from interpreter import Interpreter
from llm import LLM
from ui import UI

class Core:
    def __init__(self):
        self.llm = LLM()
        self.interpreter = Interpreter()
        self.ui = UI(self)

    def run(self):
        print("Make sure to give the application Accessibility permissions in settings (to control mouse and keyboard), and Screen Recording permissions to take screenshots.")
        self.ui.run()

        #while True:
        #    user_request = input("\nEnter your request: ").strip() # TODO: replace this with getting the input from the UI text box
        #    self.execute(user_request)

    def execute(self, user_request, step_num=0):
        """
            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        # TODO: put this in a thread and then make a stop() function that can stop execution and then put that stop button in the UI
        try:
            instructions = self.llm.get_instructions_for_objective(user_request, step_num)

            # Send to Interpreter and Executor
            self.ui.display_current_status
            success = self.interpreter.process(instructions["steps"], self.ui.display_current_status)

            if not success:
                return "Unable to execute the request"
        except Exception as e:
            print(f"Exception Unable to execute the request - {e}")
            return "Unable to execute the request"

        if instructions["done"]:
            # Communicate Results
            print(instructions["done"])
            return instructions["done"]
        else:
            # if not done, continue to next phase
            self.execute(user_request, step_num + 1)


if __name__ == "__main__":
    Core().run()
