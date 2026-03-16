import sqlite3
import time
import uuid
from multiprocessing import Queue
from typing import Optional, Any, cast

from agent_memory import create_agent_memory
from agent_memory import mark_anchor_unreliable
from agent_memory import record_action
from agent_memory import record_failure
from openai import OpenAIError

from interpreter import Interpreter
from llm import LLM, build_session_history_snapshot
from session_store import SessionStore
from utils.i18n import t
from utils.settings import Settings
from utils.screen import Screen
from verifier import StepVerifier

DEFAULT_SESSION_TITLE = '默认会话'
NEW_SESSION_TITLE = '新会话'
MAX_CONSECUTIVE_VERIFICATION_FAILURES = 3


class Core:
    def __init__(self):
        self.status_queue = Queue()
        self.interrupt_execution = False
        self.request_sequence = 0
        self.active_request_token: Optional[int] = None
        self.cancelled_request_tokens: set[int] = set()
        self.settings = Settings()
        self.settings_dict = self.settings.get_dict()
        self.storage_paths = self.settings.get_storage_paths()
        self.startup_issue: Optional[dict[str, Any]] = None
        self.session_store: Optional[SessionStore] = None
        self.active_session_id: Optional[str] = None
        self.interpreter: Optional[Interpreter] = None
        self.step_verifier = StepVerifier()

        try:
            self.session_store = SessionStore(self.settings.get_session_history_db_path())
            self.session_store.initialize()
            self.active_session_id = self._ensure_active_session_id()
            self.interpreter = Interpreter(self.status_queue, self.session_store)
        except Exception as e:
            self.session_store = None
            self.active_session_id = None
            self.interpreter = None
            self.startup_issue = self._build_database_issue(
                t('core.database_startup_error_message'),
                t('core.database_error_hint'),
                error=e,
            )
            self._emit_runtime_status(issue=self.startup_issue)

        self.llm: Optional[LLM] = None
        if self.session_store is not None:
            try:
                self.llm = LLM()
            except OpenAIError as e:
                self.startup_issue = self._build_config_issue(e)
                self._emit_runtime_status(issue=self.startup_issue)
            except Exception as e:
                self.startup_issue = self._build_config_issue(e)
                self._emit_runtime_status(issue=self.startup_issue)

    def execute_user_request(self, user_request: str, request_origin: str = 'new_request') -> None:
        self.stop_previous_request()
        time.sleep(0.1)
        request_token = self._begin_new_request()
        try:
            request_context = self._build_request_context(
                user_request,
                request_token=request_token,
                request_origin=request_origin,
            )
        except Exception as e:
            self._finalize_request_token(request_token)
            issue = self._build_request_issue(e, session_id=self.active_session_id)
            self._emit_runtime_status(issue=issue)
            return

        self._emit_runtime_status(
            t('core.requesting_model_initial'),
            session_id=request_context['session_id'],
        )
        self.execute(request_context['prompt'], request_context=request_context)

    def get_active_session_id(self) -> str:
        return self._ensure_active_session_id()

    def switch_active_session(self, session_id: str) -> bool:
        self._require_session_store()
        store = cast(SessionStore, self.session_store)
        target_session_id = str(session_id or '').strip()
        if target_session_id == '':
            raise ValueError(t('core.invalid_session_id'))

        if target_session_id == getattr(self, 'active_session_id', None):
            return False

        session = store.get_session(target_session_id)
        if session is None:
            raise ValueError(t('core.session_not_found'))

        self.active_session_id = session['id']
        store.set_last_active_session_id(self.active_session_id)
        return True

    def create_session_and_activate(self, title: Optional[str] = None) -> dict[str, Any]:
        self._require_session_store()
        store = cast(SessionStore, self.session_store)
        session_title = title or NEW_SESSION_TITLE
        session = store.create_session(session_title)
        self.active_session_id = session['id']
        store.set_last_active_session_id(self.active_session_id)
        return session

    def stop_previous_request(self, announce: bool = False) -> None:
        self.interrupt_execution = True
        active_request_token = self.active_request_token
        if active_request_token is not None:
            self.cancelled_request_tokens.add(active_request_token)
        if announce:
            self._emit_runtime_status(
                t('core.interrupt_requested'),
                session_id=self.active_session_id,
            )

    def restart_last_request(self) -> Optional[str]:
        self._require_session_store()
        store = cast(SessionStore, self.session_store)
        session_id = self._ensure_active_session_id()
        messages = store.list_messages(session_id)

        for message in reversed(messages):
            if str(message.get('role') or '') != 'user':
                continue

            content = str(message.get('content') or '').strip()
            if content == '':
                continue

            self._emit_runtime_status(
                t('core.restarting_last_request'),
                session_id=session_id,
            )
            self.execute_user_request(content, request_origin='retry_last_request')
            return content

        self._emit_runtime_status(
            t('core.no_previous_user_request'),
            session_id=session_id,
        )
        return None

    def reload_runtime_settings(self) -> dict[str, Any]:
        old_llm = getattr(self, 'llm', None)
        old_settings_dict = dict(getattr(self, 'settings_dict', {}))

        try:
            settings_store = getattr(self, 'settings', None)
            if settings_store is None:
                settings_store = Settings()
                self.settings = settings_store

            self.settings_dict = settings_store.get_dict()
            self.storage_paths = settings_store.get_storage_paths()
            new_llm = LLM()
        except Exception as e:
            self.settings_dict = old_settings_dict
            self.llm = old_llm

            failure_issue = {
                'level': 'error',
                'category': 'config_reload',
                'message': str(e),
            }
            try:
                failure_issue = self._build_config_issue(e)
            except Exception:
                pass

            if hasattr(self, 'startup_issue'):
                self.startup_issue = failure_issue

            if hasattr(self, 'status_queue'):
                try:
                    self._emit_runtime_status(issue=failure_issue)
                except Exception:
                    pass

            return {
                'ok': False,
                'issue': failure_issue,
                'error': str(e),
            }

        self.llm = new_llm
        self.startup_issue = None

        if old_llm is not None and old_llm is not new_llm:
            try:
                old_llm.cleanup()
            except Exception:
                pass

        self._emit_runtime_status(
            t('core.runtime_settings_reloaded'),
            session_id=getattr(self, 'active_session_id', None),
        )
        return {'ok': True}

    def execute(
        self,
        user_request: str,
        step_num: int = 0,
        request_context: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """
            This function might recurse.

            user_request: The original user request
            step_number: the number of times we've called the LLM for this request.
                Used to keep track of whether it's a fresh request we're processing (step number 0), or if we're already
                in the middle of one.
                Without it the LLM kept looping after finishing the user request.
                Also, it is needed because the LLM we are using doesn't have a stateful/assistant mode.
        """
        if request_context is None:
            request_token = self._begin_new_request()
            try:
                request_context = self._build_request_context(user_request, request_token=request_token)
            except Exception:
                self._finalize_request_token(request_token)
                raise

        prompt = request_context['prompt']

        if not self.llm:
            issue = self.startup_issue or self._build_config_issue(RuntimeError(t('core.model_unavailable_message')))
            status = issue['message']
            self._store_status_message(request_context, status, issue=issue)
            self._finalize_request(request_context)
            return status

        interrupted_status = self._abort_if_interrupted(request_context)
        if interrupted_status is not None:
            return interrupted_status

        try:
            if step_num > 0:
                self._emit_runtime_status(
                    t('core.requesting_model_followup'),
                    session_id=request_context['session_id'],
                )

            instructions = self.llm.get_instructions_for_objective(
                prompt,
                step_num,
                request_context=request_context,
            )

            interrupted_status = self._abort_if_interrupted(request_context)
            if interrupted_status is not None:
                return interrupted_status

            if instructions == {}:
                # Sometimes LLM sends malformed JSON response, in that case retry once more.
                retry_prompt = prompt + ' Please reply in valid JSON'
                instructions = self.llm.get_instructions_for_objective(
                    retry_prompt,
                    step_num,
                    request_context=request_context,
                )

                interrupted_status = self._abort_if_interrupted(request_context)
                if interrupted_status is not None:
                    return interrupted_status

            self._attach_frame_context(request_context, instructions)
            steps = instructions.get('steps')
            if not isinstance(steps, list):
                steps = []
            if len(steps) > 1:
                steps = steps[:1]
                instructions['steps'] = steps

            if len(steps) == 0 and not instructions.get('done'):
                status = '模型没有返回可执行步骤，任务已停止。'
                self._store_status_message(request_context, status)
                self._finalize_request(request_context)
                return status

            disable_local_step_verification = self._is_local_step_verification_disabled()
            verification_failed = False

            for step in steps:
                interrupted_status = self._abort_if_interrupted(request_context)
                if interrupted_status is not None:
                    return interrupted_status

                interpreter = self.interpreter
                if interpreter is None:
                    raise RuntimeError(t('core.database_runtime_error_message'))
                assert interpreter is not None

                before_image = None
                if not disable_local_step_verification:
                    before_image = self._capture_before_step(step)

                current_step_index = int(request_context['next_step_index'])
                success = interpreter.process_command(step, request_context)
                request_context['next_step_index'] = request_context['next_step_index'] + 1

                interrupted_status = self._abort_if_interrupted(request_context)
                if interrupted_status is not None:
                    return interrupted_status

                if not success:
                    self._record_agent_execution_failure(
                        step,
                        request_context,
                        current_step_index,
                        interpreter,
                    )
                    status = t('core.unable_to_execute_request')
                    self._store_status_message(request_context, status)
                    self._finalize_request(request_context)
                    return status

                if disable_local_step_verification:
                    verification_result = self._build_skipped_verification_result(step)
                    self._remember_step_result(
                        step,
                        request_context,
                        interpreter,
                        verification_result,
                        current_step_index,
                    )
                    time.sleep(1.0)

                    interrupted_status = self._abort_if_interrupted(request_context)
                    if interrupted_status is not None:
                        return interrupted_status

                    continue

                verification_result = self._verify_step(step, interpreter, before_image)
                self._remember_step_result(
                    step,
                    request_context,
                    interpreter,
                    verification_result,
                    current_step_index,
                )
                if verification_result['status'] == 'failed':
                    verification_failed = True
                    self._emit_runtime_status(
                        '步骤已执行，但界面没有明显变化，正在重新观察。',
                        session_id=request_context['session_id'],
                    )
                    break

        except Exception as e:
            issue = self._build_request_issue(e, session_id=request_context['session_id'])
            status = issue['message']
            self._store_status_message(request_context, status, issue=issue)
            self._finalize_request(request_context)
            return status

        if verification_failed:
            if self._has_exceeded_verification_failures(request_context):
                status = '多次执行后仍无法验证界面变化，已停止本次任务。'
                self._store_status_message(request_context, status)
                self._finalize_request(request_context)
                return status

            interrupted_status = self._abort_if_interrupted(request_context)
            if interrupted_status is not None:
                return interrupted_status

            return self.execute(prompt, step_num + 1, request_context=request_context)

        interrupted_status = self._abort_if_interrupted(request_context)
        if interrupted_status is not None:
            return interrupted_status

        if instructions['done']:
            # Communicate Results
            self._store_assistant_message(request_context, instructions['done'])
            self._emit_runtime_status('', session_id=request_context['session_id'])
            self.play_ding_on_completion()
            self._finalize_request(request_context)
            return instructions['done']
        else:
            # if not done, continue to next phase
            interrupted_status = self._abort_if_interrupted(request_context)
            if interrupted_status is not None:
                return interrupted_status

            self._emit_runtime_status(
                t('core.fetching_further_instructions'),
                session_id=request_context['session_id'],
            )
            return self.execute(prompt, step_num + 1, request_context=request_context)

    def _attach_frame_context(
        self,
        request_context: dict[str, Any],
        instructions: dict[str, Any],
    ) -> None:
        frame_context = instructions.get('frame_context')
        if isinstance(frame_context, dict):
            request_context['frame_context'] = frame_context

    def _ensure_active_session_id(self) -> str:
        self._require_session_store()
        store = cast(SessionStore, self.session_store)

        if getattr(self, 'active_session_id', None):
            active_session_id = str(self.active_session_id)
            session = store.get_session(active_session_id)
            if session is not None:
                self.active_session_id = active_session_id
                store.set_last_active_session_id(self.active_session_id)
                return str(self.active_session_id)

        last_active_session_id = store.get_last_active_session_id()
        session = None
        if last_active_session_id is not None:
            session = store.get_session(last_active_session_id)

        if session is None:
            session = store.get_most_recent_session()

        if session is None:
            session = store.create_session(DEFAULT_SESSION_TITLE)

        self.active_session_id = session['id']
        store.set_last_active_session_id(self.active_session_id)
        return str(self.active_session_id)

    def _build_request_context(
        self,
        user_request: str,
        request_token: Optional[int] = None,
        request_origin: str = 'new_request',
    ) -> dict[str, Any]:
        self._require_session_store()
        store = cast(SessionStore, self.session_store)
        session_id = self._ensure_active_session_id()
        request_id = str(uuid.uuid4())
        session_messages = store.list_messages(session_id)
        prompt = user_request
        session_history_snapshot = build_session_history_snapshot(session_messages)

        if self.llm is not None:
            begin_request = getattr(self.llm, 'begin_request', None)
            if callable(begin_request):
                begin_request()

        user_message = store.create_message(
            session_id,
            'user',
            user_request,
            request_id=request_id,
        )
        self._emit_message_persisted(user_message)

        return {
            'prompt': prompt,
            'request_id': request_id,
            'request_token': request_token,
            'session_id': session_id,
            'user_request': user_request,
            'user_message_id': user_message['id'],
            'interrupted_recorded': False,
            'request_finalized': False,
            'next_step_index': 1,
            'agent_memory': create_agent_memory(),
            'step_history': [],
            'session_history_snapshot': session_history_snapshot,
            'request_origin': str(request_origin or 'new_request').strip() or 'new_request',
        }

    def _capture_before_step(self, step: dict[str, Any]) -> Optional[Any]:
        function_name = str(step.get('function') or '').strip()
        if function_name == 'sleep':
            return None
        return Screen().get_screenshot()

    def _is_local_step_verification_disabled(self) -> bool:
        runtime_settings = self.settings_dict.get('runtime')
        if not isinstance(runtime_settings, dict):
            return False
        return bool(runtime_settings.get('disable_local_step_verification', False))

    def _build_skipped_verification_result(self, step: dict[str, Any]) -> dict[str, Any]:
        return {
            'status': 'skipped',
            'reason': 'local_step_verification_disabled',
            'function': str(step.get('function') or '').strip(),
            'expected_outcome': str(step.get('expected_outcome') or '').strip(),
            'global_change_ratio': 0.0,
            'local_change_ratio': None,
        }

    def _verify_step(
        self,
        step: dict[str, Any],
        interpreter: Interpreter,
        before_image: Optional[Any],
    ) -> dict[str, Any]:
        function_name = str(step.get('function') or '').strip()
        if function_name != 'sleep':
            time.sleep(0.35)

        after_image = None
        if before_image is not None:
            after_image = Screen().get_screenshot()

        execution_snapshot = interpreter.get_last_execution_snapshot()
        verification_parameters = dict(execution_snapshot.get('parameters') or {})
        coordinate_resolution = execution_snapshot.get('coordinate_resolution')
        if isinstance(coordinate_resolution, dict):
            verification_parameters['coordinate_resolution'] = coordinate_resolution
        verification_result = self.step_verifier.verify_step(
            step,
            verification_parameters,
            before_image,
            after_image,
        )
        print(f'Verification result: {verification_result}')
        return verification_result

    def _remember_step_result(
        self,
        step: dict[str, Any],
        request_context: dict[str, Any],
        interpreter: Interpreter,
        verification_result: dict[str, Any],
        step_index: int,
    ) -> None:
        agent_memory = request_context.get('agent_memory')
        if not isinstance(agent_memory, dict):
            agent_memory = None

        execution_snapshot = interpreter.get_last_execution_snapshot()
        parameters = step.get('parameters')
        if not isinstance(parameters, dict):
            parameters = execution_snapshot.get('parameters')

        function_name = str(step.get('function') or execution_snapshot.get('function_name') or '').strip()
        if isinstance(agent_memory, dict):
            record_action(
                agent_memory,
                function_name=function_name,
                parameters=parameters,
                verification_status=str(verification_result.get('status') or ''),
                verification_reason=str(verification_result.get('reason') or ''),
            )

        self._append_step_history_entry(
            request_context,
            step_index=step_index,
            step=step,
            function_name=function_name,
            parameters=parameters,
            execution_status='succeeded',
            verification_status=str(verification_result.get('status') or ''),
            verification_reason=str(verification_result.get('reason') or ''),
            error_message=None,
        )

        if verification_result.get('status') != 'failed' or not isinstance(agent_memory, dict):
            return

        record_failure(
            agent_memory,
            function_name=function_name,
            reason=str(verification_result.get('reason') or 'verification_failed'),
            parameters=parameters,
        )

        anchor_id = parameters.get('target_anchor_id') if isinstance(parameters, dict) else None
        if anchor_id is not None:
            mark_anchor_unreliable(agent_memory, anchor_id)

    def _record_agent_execution_failure(
        self,
        step: dict[str, Any],
        request_context: dict[str, Any],
        step_index: int,
        interpreter: Interpreter,
    ) -> None:
        agent_memory = request_context.get('agent_memory')
        if not isinstance(agent_memory, dict):
            agent_memory = None

        parameters = step.get('parameters')
        if not isinstance(parameters, dict):
            parameters = {}

        function_name = str(step.get('function') or '').strip()
        execution_snapshot = interpreter.get_last_execution_snapshot()
        error_message = str(execution_snapshot.get('error_message') or 'execution_failed').strip()
        if isinstance(agent_memory, dict):
            record_failure(
                agent_memory,
                function_name=function_name,
                reason=error_message,
                parameters=parameters,
            )

        self._append_step_history_entry(
            request_context,
            step_index=step_index,
            step=step,
            function_name=function_name,
            parameters=parameters,
            execution_status='failed',
            verification_status='not_run',
            verification_reason='execution_failed',
            error_message=error_message,
        )

        anchor_id = parameters.get('target_anchor_id')
        if anchor_id is not None and isinstance(agent_memory, dict):
            mark_anchor_unreliable(agent_memory, anchor_id)

    def _append_step_history_entry(
        self,
        request_context: dict[str, Any],
        step_index: int,
        step: dict[str, Any],
        function_name: str,
        parameters: dict[str, Any] | None,
        execution_status: str,
        verification_status: str,
        verification_reason: str,
        error_message: Optional[str],
    ) -> None:
        step_history = request_context.get('step_history')
        if not isinstance(step_history, list):
            request_context['step_history'] = []
            step_history = request_context['step_history']

        step_history.append({
            'step_index': step_index,
            'function': function_name,
            'parameters': dict(parameters or {}),
            'human_readable_justification': str(step.get('human_readable_justification') or '').strip(),
            'expected_outcome': str(step.get('expected_outcome') or '').strip(),
            'execution_status': str(execution_status or '').strip(),
            'verification_status': str(verification_status or '').strip(),
            'verification_reason': str(verification_reason or '').strip(),
            'error_message': None if error_message is None else str(error_message).strip(),
        })

    def _has_exceeded_verification_failures(self, request_context: dict[str, Any]) -> bool:
        agent_memory = request_context.get('agent_memory')
        if not isinstance(agent_memory, dict):
            return False

        failure_count = int(agent_memory.get('consecutive_verification_failures') or 0)
        return failure_count >= MAX_CONSECUTIVE_VERIFICATION_FAILURES

    def _store_assistant_message(
        self,
        request_context: dict[str, Any],
        message: str,
    ) -> None:
        store = cast(Optional[SessionStore], self.session_store)
        if store is None:
            raise RuntimeError(t('core.database_runtime_error_message'))

        message_record = store.create_message(
            request_context['session_id'],
            'assistant',
            message,
            request_id=request_context['request_id'],
        )
        self._emit_message_persisted(message_record)

    def _store_status_message(
        self,
        request_context: Optional[dict[str, Any]],
        message: str,
        issue: Optional[dict[str, Any]] = None,
    ) -> None:
        if request_context is None or self.session_store is None:
            self._emit_runtime_status(message=message, issue=issue)
            return

        store = cast(SessionStore, self.session_store)
        message_record = store.create_message(
            request_context['session_id'],
            'status',
            message,
            request_id=request_context['request_id'],
        )
        self._emit_message_persisted(message_record)
        self._emit_runtime_status(message=message, session_id=request_context['session_id'], issue=issue)

    def _emit_runtime_status(
        self,
        message: str = '',
        session_id: Optional[str] = None,
        issue: Optional[dict[str, Any]] = None,
    ) -> None:
        event = {
            'type': 'runtime_status',
            'message': message,
            'session_id': session_id,
        }
        if issue is not None:
            event.update(issue)
            if event.get('message', '') == '':
                event['message'] = issue.get('message', '')
            if event.get('session_id') is None:
                event['session_id'] = issue.get('session_id')
        self.status_queue.put(event)

    def _begin_new_request(self) -> int:
        self.request_sequence = self.request_sequence + 1
        request_token = self.request_sequence
        self.active_request_token = request_token
        self.interrupt_execution = False
        self.cancelled_request_tokens.discard(request_token)
        return request_token

    def _is_request_interrupted(self, request_context: Optional[dict[str, Any]]) -> bool:
        if request_context is None:
            return self.interrupt_execution

        request_token = request_context.get('request_token')
        if request_token is None:
            return self.interrupt_execution

        return int(request_token) in self.cancelled_request_tokens

    def _abort_if_interrupted(self, request_context: Optional[dict[str, Any]]) -> Optional[str]:
        if not self._is_request_interrupted(request_context):
            return None

        status = t('core.interrupted')
        if isinstance(request_context, dict) and not bool(request_context.get('interrupted_recorded')):
            request_context['interrupted_recorded'] = True
            self._store_status_message(request_context, status)
        elif request_context is None:
            self._emit_runtime_status(status, session_id=self.active_session_id)

        self._finalize_request(request_context)
        return status

    def _finalize_request(self, request_context: Optional[dict[str, Any]]) -> None:
        if not isinstance(request_context, dict):
            return
        if bool(request_context.get('request_finalized')):
            return

        request_context['request_finalized'] = True
        request_token = request_context.get('request_token')
        if request_token is None:
            return

        self._finalize_request_token(int(request_token))

    def _finalize_request_token(self, request_token: int) -> None:
        self.cancelled_request_tokens.discard(request_token)
        if self.active_request_token == request_token:
            self.active_request_token = None
            self.interrupt_execution = False

    def get_startup_issue(self) -> Optional[dict[str, Any]]:
        return self.startup_issue

    def is_database_error(self, error: Exception) -> bool:
        if self.session_store is None:
            return True

        if isinstance(error, sqlite3.Error):
            return True

        error_text = str(error).lower()
        database_markers = [
            'database',
            'sqlite',
            'readonly',
            'disk image',
            'session_history.db',
        ]
        for marker in database_markers:
            if marker in error_text:
                return True

        return False

    def build_session_operation_issue(self, action: str, error: Exception) -> dict[str, Any]:
        if self.is_database_error(error):
            return self._build_database_issue(
                t('core.database_runtime_error_message'),
                t('core.database_operation_error_hint'),
                error=error,
                session_id=self.active_session_id,
            )

        title_key = 'app.switch_session_failed_title'
        message_key = 'app.switch_session_failed_message'
        hint_key = 'app.switch_session_failed_hint'
        if action == 'create_session':
            title_key = 'app.create_session_failed_title'
            message_key = 'app.create_session_failed_message'
            hint_key = 'app.create_session_failed_hint'

        return {
            'level': 'error',
            'category': 'session_operation',
            'title': t(title_key),
            'message': t(message_key),
            'hint': t(hint_key),
            'details': str(error),
            'session_id': self.active_session_id,
        }

    def build_session_view_issue(self, error: Exception) -> dict[str, Any]:
        if self.is_database_error(error):
            return self._build_database_issue(
                t('app.session_view_hydration_failed_message'),
                t('app.session_view_hydration_failed_hint'),
                error=error,
                session_id=self.active_session_id,
            )

        return {
            'level': 'error',
            'category': 'startup',
            'title': t('app.session_view_hydration_failed_title'),
            'message': t('app.session_view_hydration_failed_message'),
            'hint': t('app.session_view_hydration_failed_hint'),
            'details': str(error),
            'session_id': self.active_session_id,
        }

    def _require_session_store(self) -> None:
        if self.session_store is not None:
            return

        raise RuntimeError(t('core.database_runtime_error_message'))

    def _build_config_issue(self, error: Exception) -> dict[str, Any]:
        config_path = self.storage_paths.get('config_db')
        if config_path is None or str(config_path).strip() == '':
            config_path = self.storage_paths.get('session_history_db', '')

        return {
            'level': 'error',
            'category': 'config',
            'title': t('core.config_error_title'),
            'message': t('core.config_error_message'),
            'hint': t('core.config_error_hint', settings_path=config_path),
            'path': config_path,
            'details': str(error),
            'session_id': self.active_session_id,
        }

    def _build_database_issue(
        self,
        message: str,
        hint: str,
        error: Exception,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            'level': 'error',
            'category': 'database',
            'title': t('core.database_error_title'),
            'message': message,
            'hint': hint,
            'path': self.storage_paths['session_history_db'],
            'details': str(error),
            'session_id': session_id,
        }

    def _build_request_issue(
        self,
        error: Exception,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if self.is_database_error(error):
            return self._build_database_issue(
                t('core.database_runtime_error_message'),
                t('core.database_operation_error_hint'),
                error=error,
                session_id=session_id,
            )

        return {
            'level': 'error',
            'category': 'request',
            'title': t('core.request_error_title'),
            'message': self._build_request_error_message(error),
            'hint': t('core.request_error_hint'),
            'details': self._format_request_error_details(error),
            'session_id': session_id,
        }

    def _build_request_error_message(self, error: Exception) -> str:
        base_message = t('core.request_error_message')
        short_reason = str(error).strip()
        if short_reason == '':
            return base_message

        return f'{base_message} {short_reason}'

    def _format_request_error_details(self, error: Exception) -> str:
        details = [str(error)]

        llm = getattr(self, 'llm', None)
        if llm is not None:
            model_name = str(getattr(llm, 'model_name', '') or '').strip()
            if model_name != '':
                details.append(f'model={model_name}')

            model_settings_dict = getattr(llm, 'model_settings_dict', {})
            if isinstance(model_settings_dict, dict):
                base_url = str(model_settings_dict.get('base_url') or '').strip()
                if base_url != '':
                    details.append(f'base_url={base_url}')

        status_code = getattr(error, 'status_code', None)
        if status_code is not None:
            details.append(f'status_code={status_code}')

        request_id = getattr(error, 'request_id', None)
        if request_id is not None:
            details.append(f'request_id={request_id}')

        return ' | '.join(detail for detail in details if detail != '')

    def _emit_message_persisted(self, message_record: dict[str, Any]) -> None:
        self.status_queue.put({
            'type': 'message_persisted',
            'session_id': message_record.get('session_id'),
            'message': message_record,
        })

    def play_ding_on_completion(self) -> None:
        # Play ding sound to signal completion
        runtime_settings = self.settings_dict.get('runtime')
        if isinstance(runtime_settings, dict) and runtime_settings.get('play_ding_on_completion'):
            print('\a')

    def cleanup(self) -> None:
        if self.llm is not None:
            self.llm.cleanup()
