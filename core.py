from multiprocessing import Queue

from interpreter import Interpreter
from llm import LLM


class Core:
    def __init__(self):
        self.llm = LLM()
        self.interpreter = Interpreter()

        self.status_queue = Queue()
        self.executor_process = None
        self.interrupt_execution = False  # TODO: create a button to set this

    def run(self):
        print(
            "Make sure to give the application Accessibility permissions in settings (to control mouse and keyboard), and Screen Recording permissions to take screenshots.")

        # while True:
        #    user_request = input("\nEnter your request: ").strip() # TODO: replace this with getting the input from the UI text box
        #    self.execute(user_request)

    def execute_user_request(self, user_request):
        self.stop_user_request()  # Stop previous request
        # self.executor_process = Process(target=self.execute, args=(user_request,))
        # self.executor_process.start()
        self.execute(user_request)

    def stop_user_request(self):
        if self.executor_process and self.executor_process.is_alive():
            self.executor_process.terminate()  # Terminate the process
            self.executor_process = None

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

            # success = self.interpreter.process_commands(instructions["steps"], self.status_queue)
            for step in instructions["steps"]:
                if self.interrupt_execution:
                    self.interrupt_execution = False
                    print("Interrupted Execution")
                    return "Interrupted"
                else:
                    success = self.interpreter.process_command(step, self.status_queue)

                    if not success:
                        return "Unable to execute the request"

        except Exception as e:
            print(f"Exception Unable to execute the request - {e}")
            return "Unable to execute the request"

        if instructions["done"]:
            # Communicate Results
            print(instructions["done"])
            self.status_queue.put(instructions["done"])
            return instructions["done"]
        else:
            # if not done, continue to next phase
            self.execute(user_request, step_num + 1)


if __name__ == "__main__":
    Core().run()
