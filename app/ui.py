import json
import threading
import webbrowser
from multiprocessing import Queue
from pathlib import Path
from typing import Any

# import speech_recognition as sr
import ttkbootstrap as ttk
from PIL import Image, ImageTk

from models.catalog import (
    DEFAULT_CLAUDE_MODEL_NAME,
    DEFAULT_PROVIDER_ID,
    RECOMMENDED_QWEN_VISION_MODEL,
    CLAUDE_PROVIDER_ID,
    OPENAI_PROVIDER_ID,
    QWEN_PROVIDER_ID,
    get_default_base_url_for_provider,
    get_default_model_for_provider,
    get_model_catalog_for_provider,
    get_provider_catalog,
    requires_qwen_reasoning,
    supports_qwen_reasoning_toggle,
)
from utils.i18n import get_current_language, get_language_label, get_language_options, set_current_language, t
from utils.settings import (
    DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS,
    DEFAULT_REASONING_DEPTH,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    Settings,
)
from version import version


DEFAULT_WINDOW_WIDTH = 1180
DEFAULT_WINDOW_HEIGHT = 760
MIN_WINDOW_WIDTH = 980
MIN_WINDOW_HEIGHT = 640
SIDEBAR_WIDTH = 280
MESSAGE_WRAP_LENGTH = 640
PARAMETERS_PREVIEW_MAX_LENGTH = 280
REASONING_DEPTH_OPTIONS = ['none', 'low', 'medium', 'high', 'xhigh']


def open_link(url) -> None:
    webbrowser.open_new(url)


class UI:
    def __init__(self):
        self.main_window = self.MainWindow()

    def run(self) -> None:
        self.main_window.mainloop()

    def display_current_status(self, text: str) -> None:
        self.main_window.enqueue_ui_update('set_runtime_status', text)

    def load_session_list(self, sessions: list[dict[str, Any]]) -> None:
        self.main_window.enqueue_ui_update('load_session_list', sessions)

    def hydrate_session_view(
        self,
        active_session_id: str | None,
        sessions: list[dict[str, Any]],
        timeline_entries: list[dict[str, Any]],
        runtime_status: str = '',
    ) -> None:
        self.main_window.enqueue_ui_update('hydrate_session_view', {
            'active_session_id': active_session_id,
            'sessions': sessions,
            'timeline_entries': timeline_entries,
            'runtime_status': runtime_status,
        })

    def load_message_history(self, messages: list[dict[str, Any]]) -> None:
        self.main_window.enqueue_ui_update('load_timeline_history', messages)

    def load_timeline_history(self, entries: list[dict[str, Any]]) -> None:
        self.main_window.enqueue_ui_update('load_timeline_history', entries)

    def append_message_item(self, message: dict[str, Any]) -> None:
        self.main_window.enqueue_ui_update('append_message_item', message)

    def append_execution_log_item(self, execution_log: dict[str, Any]) -> None:
        self.main_window.enqueue_ui_update('append_execution_log_item', execution_log)

    def set_runtime_status(self, status_payload: Any) -> None:
        self.main_window.enqueue_ui_update('set_runtime_status', status_payload)

    class AdvancedSettingsWindow(ttk.Toplevel):
        def __init__(self, parent):
            super().__init__(parent)
            self.destroy()
            UI.SettingsWindow(parent)

    class SettingsWindow(ttk.Toplevel):
        def __init__(self, parent):
            super().__init__(parent)
            self.title(t('settings.title'))
            self.minsize(560, 720)
            self.available_themes = ['darkly', 'cyborg', 'journal', 'solar', 'superhero']
            self.custom_model_option_label = t('advanced.custom_model_option')
            self.provider_catalog = get_provider_catalog()
            self.provider_ids = [str(item['id']) for item in self.provider_catalog]
            self.provider_id_to_label = {
                str(item['id']): str(item['label'])
                for item in self.provider_catalog
            }
            self.provider_label_to_id = {
                str(item['label']): str(item['id'])
                for item in self.provider_catalog
            }
            self.provider_forms: dict[str, dict[str, Any]] = {}
            self.pending_theme_name = 'superhero'
            self.settings = Settings()
            self.create_widgets()

            settings_dict = self.settings.get_dict()
            self.load_settings(settings_dict)

        def create_widgets(self) -> None:
            self.main_container = ttk.Frame(self)
            self.main_container.pack(fill='both', expand=True)

            self.settings_canvas = ttk.Canvas(self.main_container, highlightthickness=0)
            self.settings_scrollbar = ttk.Scrollbar(
                self.main_container,
                orient='vertical',
                command=self.settings_canvas.yview,
            )
            self.settings_canvas.configure(yscrollcommand=self.settings_scrollbar.set)
            
            self.settings_canvas.pack(side='left', fill='both', expand=True, padx=(16, 0), pady=16)
            self.settings_scrollbar.pack(side='right', fill='y', pady=16)

            content_frame = ttk.Frame(self.settings_canvas)
            self.settings_window = self.settings_canvas.create_window(
                (0, 0), window=content_frame, anchor='nw'
            )

            # Bind configure events to update scrollregion
            content_frame.bind('<Configure>', lambda e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox('all')))
            self.settings_canvas.bind('<Configure>', lambda e: self.settings_canvas.itemconfigure(self.settings_window, width=e.width))

            providers_label = ttk.Label(content_frame, text='[Providers]', bootstyle='primary')
            providers_label.pack(anchor=ttk.W)

            active_provider_label = ttk.Label(content_frame, text=t('settings.active_provider'))
            active_provider_label.pack(anchor=ttk.W, pady=(8, 0))
            self.active_provider_var = ttk.StringVar(value=self.provider_id_to_label[DEFAULT_PROVIDER_ID])
            self.active_provider_combobox = ttk.Combobox(
                content_frame,
                textvariable=self.active_provider_var,
                values=[self.provider_id_to_label[provider_id] for provider_id in self.provider_ids],
                state='readonly',
                width=38,
            )
            self.active_provider_combobox.pack(anchor=ttk.W)

            self.active_provider_help_label = ttk.Label(
                content_frame,
                text=t('settings.provider_activation_help'),
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            self.active_provider_help_label.pack(anchor=ttk.W, pady=(4, 8))

            self.create_openai_provider_section(content_frame)
            self.create_qwen_provider_section(content_frame)
            self.create_claude_provider_section(content_frame)

            runtime_label = ttk.Label(content_frame, text='[Runtime]', bootstyle='primary')
            runtime_label.pack(anchor=ttk.W, pady=(12, 0))

            language_label = ttk.Label(content_frame, text='Language:')
            language_label.pack(anchor=ttk.W, pady=(8, 0))
            self.language_options = get_language_options()
            self.language_labels = [label for _, label in self.language_options]
            self.language_var = ttk.StringVar()
            self.language_combobox = ttk.Combobox(
                content_frame,
                textvariable=self.language_var,
                values=self.language_labels,
                state='readonly',
                width=38,
            )
            self.language_combobox.pack(anchor=ttk.W)

            self.play_ding = ttk.IntVar()
            play_ding_checkbox = ttk.Checkbutton(
                content_frame,
                text=t('settings.play_ding'),
                variable=self.play_ding,
                bootstyle='round-toggle',
            )
            play_ding_checkbox.pack(anchor=ttk.W, pady=(8, 0))

            self.disable_local_step_verification_var = ttk.IntVar(value=0)
            disable_local_step_verification_checkbox = ttk.Checkbutton(
                content_frame,
                text=t('settings.disable_local_step_verification'),
                variable=self.disable_local_step_verification_var,
                bootstyle='round-toggle',
            )
            disable_local_step_verification_checkbox.pack(anchor=ttk.W, pady=(8, 0))

            self.disable_local_step_verification_help_label = ttk.Label(
                content_frame,
                text=t('settings.disable_local_step_verification_help'),
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            self.disable_local_step_verification_help_label.pack(anchor=ttk.W, pady=(4, 0))

            request_timeout_label = ttk.Label(content_frame, text=t('settings.request_timeout_seconds'))
            request_timeout_label.pack(anchor=ttk.W, pady=(8, 0))
            self.request_timeout_entry = ttk.Entry(content_frame, width=42)
            self.request_timeout_entry.pack(anchor=ttk.W)

            self.save_model_prompt_images_var = ttk.IntVar(value=0)
            save_model_prompt_images_checkbox = ttk.Checkbutton(
                content_frame,
                text=t('settings.save_model_prompt_images'),
                variable=self.save_model_prompt_images_var,
                bootstyle='round-toggle',
            )
            save_model_prompt_images_checkbox.pack(anchor=ttk.W, pady=(8, 0))

            self.prompt_image_help_label = ttk.Label(
                content_frame,
                text=t('settings.save_model_prompt_images_help'),
                bootstyle='secondary',
                wraplength=360,
                justify='left',
            )
            self.prompt_image_help_label.pack(anchor=ttk.W, pady=(4, 0))

            self.save_prompt_text_dumps_var = ttk.IntVar(value=0)
            save_prompt_text_dumps_checkbox = ttk.Checkbutton(
                content_frame,
                text=t('settings.save_prompt_text_dumps'),
                variable=self.save_prompt_text_dumps_var,
                bootstyle='round-toggle',
            )
            save_prompt_text_dumps_checkbox.pack(anchor=ttk.W, pady=(8, 0))

            self.prompt_text_dump_help_label = ttk.Label(
                content_frame,
                text=t('settings.save_prompt_text_dumps_help'),
                bootstyle='secondary',
                wraplength=360,
                justify='left',
            )
            self.prompt_text_dump_help_label.pack(anchor=ttk.W, pady=(4, 0))

            appearance_label = ttk.Label(content_frame, text='[Appearance]', bootstyle='primary')
            appearance_label.pack(anchor=ttk.W, pady=(12, 0))

            label_theme = ttk.Label(content_frame, text=t('settings.ui_theme'))
            label_theme.pack(anchor=ttk.W, pady=(8, 0))
            self.theme_var = ttk.StringVar()
            self.theme_combobox = ttk.Combobox(
                content_frame,
                textvariable=self.theme_var,
                values=self.available_themes,
                state='readonly',
                width=38,
            )
            self.theme_combobox.pack(anchor=ttk.W)
            self.theme_combobox.set('superhero')
            self.theme_combobox.bind('<<ComboboxSelected>>', self.on_theme_change)

            self.theme_help_label = ttk.Label(
                content_frame,
                text=t('settings.theme_apply_after_save'),
                bootstyle='secondary',
                wraplength=360,
                justify='left',
            )
            self.theme_help_label.pack(anchor=ttk.W, pady=(4, 0))

            advanced_label = ttk.Label(content_frame, text='[Advanced]', bootstyle='primary')
            advanced_label.pack(anchor=ttk.W, pady=(12, 0))

            label_llm = ttk.Label(content_frame, text=t('settings.custom_llm_guidance'))
            label_llm.pack(anchor=ttk.W, pady=(8, 0))

            self.llm_instructions_text = ttk.Text(content_frame, height=8, width=52)
            self.llm_instructions_text.pack(anchor=ttk.W, pady=(0, 8))

            self.feedback_label = ttk.Label(
                content_frame,
                text='',
                bootstyle='danger',
                wraplength=460,
                justify='left',
            )
            self.feedback_label.pack(anchor=ttk.W, pady=(4, 8))

            save_button = ttk.Button(content_frame, text=t('settings.save_settings'), bootstyle='success', command=self.save_button)
            save_button.pack(anchor=ttk.W, pady=(2, 8))

            link_label = ttk.Label(content_frame, text=t('settings.setup_instructions'), bootstyle='primary')
            link_label.pack(anchor=ttk.W)
            link_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface?tab=readme-ov-file#setup-%EF%B8%8F'))

            update_label = ttk.Label(content_frame, text=t('settings.check_updates'), bootstyle='primary')
            update_label.pack(anchor=ttk.W)
            update_label.bind('<Button-1>', lambda e: open_link(
                'https://github.com/AmberSahdev/Open-Interface/releases/latest'))

            version_label = ttk.Label(content_frame, text=t('settings.version', version=str(version)), font=('Helvetica', 10))
            version_label.pack(side="bottom", pady=10)

            def _on_mousewheel(event):
                if hasattr(event, 'delta') and event.delta != 0:
                    if abs(event.delta) >= 120:
                        delta = int(-1 * (event.delta / 120))
                    else:
                        delta = int(-1 * event.delta)
                    self.settings_canvas.yview_scroll(delta, 'units')
            
            def _bind_mousewheel(widget):
                widget.bind("<MouseWheel>", _on_mousewheel)
                for child in widget.winfo_children():
                    _bind_mousewheel(child)
            
            _bind_mousewheel(content_frame)
            self.settings_canvas.bind("<MouseWheel>", _on_mousewheel)

        def load_settings(self, settings_dict: dict[str, Any]) -> None:
            active_provider = str(settings_dict.get('active_provider') or DEFAULT_PROVIDER_ID)
            self.active_provider_var.set(self.provider_id_to_label.get(active_provider, self.provider_id_to_label[DEFAULT_PROVIDER_ID]))

            providers = settings_dict.get('providers')
            if not isinstance(providers, dict):
                providers = {}

            for provider_id in self.provider_ids:
                provider_settings = providers.get(provider_id)
                if not isinstance(provider_settings, dict):
                    provider_settings = {}
                self.load_provider_form(provider_id, provider_settings)

            runtime_settings = settings_dict.get('runtime')
            if not isinstance(runtime_settings, dict):
                runtime_settings = {}
            appearance_settings = settings_dict.get('appearance')
            if not isinstance(appearance_settings, dict):
                appearance_settings = {}
            advanced_settings = settings_dict.get('advanced')
            if not isinstance(advanced_settings, dict):
                advanced_settings = {}

            language_code = str(appearance_settings.get('language') or get_current_language())
            self.language_var.set(get_language_label(language_code))

            play_ding_enabled = bool(runtime_settings.get('play_ding_on_completion', True))
            self.play_ding.set(1 if play_ding_enabled else 0)

            disable_local_step_verification = bool(runtime_settings.get('disable_local_step_verification', False))
            self.disable_local_step_verification_var.set(1 if disable_local_step_verification else 0)

            save_model_prompt_images = bool(advanced_settings.get('save_model_prompt_images', False))
            self.save_model_prompt_images_var.set(1 if save_model_prompt_images else 0)

            save_prompt_text_dumps = bool(advanced_settings.get('save_prompt_text_dumps', False))
            self.save_prompt_text_dumps_var.set(1 if save_prompt_text_dumps else 0)

            request_timeout_seconds = runtime_settings.get('request_timeout_seconds', DEFAULT_REQUEST_TIMEOUT_SECONDS)
            self.request_timeout_entry.insert(0, str(request_timeout_seconds))

            custom_instructions = str(advanced_settings.get('custom_llm_instructions') or '')
            self.llm_instructions_text.insert('1.0', custom_instructions)

            current_theme = str(appearance_settings.get('theme') or 'superhero')
            self.theme_combobox.set(current_theme)
            self.pending_theme_name = current_theme

            self.update_openai_reasoning_controls_state()
            self.update_qwen_thinking_controls_state()
            self.update_claude_thinking_controls_state()

        def create_openai_provider_section(self, parent) -> None:
            section_label = ttk.Label(parent, text='OpenAI', bootstyle='info')
            section_label.pack(anchor=ttk.W, pady=(8, 0))
            section_frame = ttk.Frame(parent)
            section_frame.pack(fill='x', expand=True)

            form = self.create_provider_common_fields(
                section_frame,
                OPENAI_PROVIDER_ID,
                t('settings.openai_base_url_help', base_url=get_default_base_url_for_provider(OPENAI_PROVIDER_ID)),
                t('settings.openai_model_help'),
            )
            self.provider_forms[OPENAI_PROVIDER_ID] = form

            form['enable_reasoning_var'] = ttk.IntVar(value=0)
            form['enable_reasoning_checkbox'] = ttk.Checkbutton(
                section_frame,
                text=t('settings.enable_reasoning'),
                variable=form['enable_reasoning_var'],
                bootstyle='round-toggle',
                command=self.on_openai_reasoning_toggle,
            )
            form['enable_reasoning_checkbox'].pack(anchor=ttk.W, pady=(8, 0))

            reasoning_depth_label = ttk.Label(section_frame, text=t('settings.reasoning_depth'))
            reasoning_depth_label.pack(anchor=ttk.W, pady=(8, 0))
            form['reasoning_depth_var'] = ttk.StringVar(value=DEFAULT_REASONING_DEPTH)
            form['reasoning_depth_combobox'] = ttk.Combobox(
                section_frame,
                textvariable=form['reasoning_depth_var'],
                values=REASONING_DEPTH_OPTIONS,
                state='disabled',
                width=38,
            )
            form['reasoning_depth_combobox'].pack(anchor=ttk.W)
            form['reasoning_help_label'] = ttk.Label(
                section_frame,
                text=t('settings.reasoning_depth_openai_only'),
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            form['reasoning_help_label'].pack(anchor=ttk.W, pady=(4, 0))

        def create_qwen_provider_section(self, parent) -> None:
            section_label = ttk.Label(parent, text='Qwen', bootstyle='info')
            section_label.pack(anchor=ttk.W, pady=(12, 0))
            section_frame = ttk.Frame(parent)
            section_frame.pack(fill='x', expand=True)

            form = self.create_provider_common_fields(
                section_frame,
                QWEN_PROVIDER_ID,
                t('settings.base_url_help', base_url=get_default_base_url_for_provider(QWEN_PROVIDER_ID)),
                t('settings.qwen_model_help', model=RECOMMENDED_QWEN_VISION_MODEL),
            )
            self.provider_forms[QWEN_PROVIDER_ID] = form

            form['thinking_var'] = ttk.IntVar(value=0)
            form['thinking_checkbox'] = ttk.Checkbutton(
                section_frame,
                text=t('settings.enable_qwen_thinking'),
                variable=form['thinking_var'],
                bootstyle='round-toggle',
            )
            form['thinking_checkbox'].pack(anchor=ttk.W, pady=(8, 0))
            form['thinking_help_label'] = ttk.Label(
                section_frame,
                text=t('settings.qwen_thinking_help'),
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            form['thinking_help_label'].pack(anchor=ttk.W, pady=(4, 0))

        def create_claude_provider_section(self, parent) -> None:
            section_label = ttk.Label(parent, text='Claude', bootstyle='info')
            section_label.pack(anchor=ttk.W, pady=(12, 0))
            section_frame = ttk.Frame(parent)
            section_frame.pack(fill='x', expand=True)

            form = self.create_provider_common_fields(
                section_frame,
                CLAUDE_PROVIDER_ID,
                t('settings.base_url_help_claude', base_url=get_default_base_url_for_provider(CLAUDE_PROVIDER_ID)),
                t('settings.claude_model_help', model=DEFAULT_CLAUDE_MODEL_NAME),
            )
            self.provider_forms[CLAUDE_PROVIDER_ID] = form

            form['thinking_var'] = ttk.IntVar(value=0)
            form['thinking_checkbox'] = ttk.Checkbutton(
                section_frame,
                text=t('settings.enable_claude_thinking'),
                variable=form['thinking_var'],
                bootstyle='round-toggle',
                command=self.on_claude_thinking_toggle,
            )
            form['thinking_checkbox'].pack(anchor=ttk.W, pady=(8, 0))

            thinking_budget_label = ttk.Label(section_frame, text=t('settings.claude_thinking_budget'))
            thinking_budget_label.pack(anchor=ttk.W, pady=(8, 0))
            form['thinking_budget_var'] = ttk.StringVar(value=str(DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS))
            form['thinking_budget_entry'] = ttk.Entry(
                section_frame,
                textvariable=form['thinking_budget_var'],
                width=42,
            )
            form['thinking_budget_entry'].pack(anchor=ttk.W)
            form['thinking_help_label'] = ttk.Label(
                section_frame,
                text=t('settings.claude_thinking_help_disabled'),
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            form['thinking_help_label'].pack(anchor=ttk.W, pady=(4, 0))

        def create_provider_common_fields(
            self,
            parent,
            provider_id: str,
            base_url_help_text: str,
            model_help_text: str,
        ) -> dict[str, Any]:
            label_api = ttk.Label(parent, text=t('settings.provider_api_key'))
            label_api.pack(anchor=ttk.W, pady=(8, 0))
            api_key_entry = ttk.Entry(parent, width=42)
            api_key_entry.pack(anchor=ttk.W)

            base_url_label = ttk.Label(parent, text=t('advanced.custom_base_url'))
            base_url_label.pack(anchor=ttk.W, pady=(8, 0))
            base_url_entry = ttk.Entry(parent, width=42)
            base_url_entry.pack(anchor=ttk.W)
            base_url_help_label = ttk.Label(
                parent,
                text=base_url_help_text,
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            base_url_help_label.pack(anchor=ttk.W, pady=(4, 0))

            model_picker_label = ttk.Label(parent, text=t('advanced.select_model'))
            model_picker_label.pack(anchor=ttk.W, pady=(8, 0))
            model_picker_var = ttk.StringVar(value=self.custom_model_option_label)
            model_combobox = ttk.Combobox(
                parent,
                textvariable=model_picker_var,
                state='readonly',
                width=38,
            )
            model_combobox.pack(anchor=ttk.W)
            model_combobox.bind(
                '<<ComboboxSelected>>',
                lambda event, selected_provider_id=provider_id: self.on_provider_model_selected(selected_provider_id),
            )

            model_label = ttk.Label(parent, text=t('advanced.custom_model_name'))
            model_label.pack(anchor=ttk.W, pady=(8, 0))
            model_var = ttk.StringVar(value=get_default_model_for_provider(provider_id))
            custom_model_entry = ttk.Entry(
                parent,
                textvariable=model_var,
                width=38,
            )
            custom_model_entry.pack(anchor=ttk.W)
            custom_model_entry.bind(
                '<KeyRelease>',
                lambda event, selected_provider_id=provider_id: self.on_provider_custom_model_changed(selected_provider_id),
            )
            model_help_label = ttk.Label(
                parent,
                text=model_help_text,
                bootstyle='secondary',
                wraplength=460,
                justify='left',
            )
            model_help_label.pack(anchor=ttk.W, pady=(4, 0))

            form = {
                'provider_id': provider_id,
                'api_key_entry': api_key_entry,
                'base_url_entry': base_url_entry,
                'base_url_help_label': base_url_help_label,
                'model_picker_var': model_picker_var,
                'model_combobox': model_combobox,
                'model_var': model_var,
                'custom_model_entry': custom_model_entry,
                'model_help_label': model_help_label,
                'model_option_values': [],
            }
            self.refresh_model_options_for_provider(provider_id)
            return form

        def get_language_code_from_label(self, language_label: str) -> str:
            for language_code, label in self.language_options:
                if label == language_label:
                    return language_code
            return get_current_language()

        def set_feedback(self, message: str, is_error: bool) -> None:
            style = 'danger'
            if not is_error:
                style = 'success'
            self.feedback_label.config(text=message, bootstyle=style)

        def on_theme_change(self, event=None) -> None:
            theme = self.theme_var.get().strip()
            if theme == '':
                return

            self.pending_theme_name = theme

        def on_openai_reasoning_toggle(self) -> None:
            self.update_openai_reasoning_controls_state()

        def on_claude_thinking_toggle(self) -> None:
            self.update_claude_thinking_controls_state()

        def on_provider_model_selected(self, provider_id: str) -> None:
            form = self.provider_forms[provider_id]
            selected_model = str(form['model_picker_var'].get()).strip()
            if selected_model == '' or selected_model == self.custom_model_option_label:
                self.update_provider_controls(provider_id)
                return

            form['model_var'].set(selected_model)
            self.update_provider_controls(provider_id)

        def on_provider_custom_model_changed(self, provider_id: str) -> None:
            form = self.provider_forms[provider_id]
            typed_model_name = str(form['model_var'].get()).strip()
            selected_model = str(form['model_picker_var'].get()).strip()
            if typed_model_name == '' or selected_model == self.custom_model_option_label:
                self.update_provider_controls(provider_id)
                return

            if typed_model_name != selected_model:
                form['model_picker_var'].set(self.custom_model_option_label)
            self.update_provider_controls(provider_id)

        def refresh_model_options_for_provider(self, provider_id: str) -> None:
            form = self.provider_forms.get(provider_id)
            if form is None:
                return

            model_option_values = [
                str(item['id'])
                for item in get_model_catalog_for_provider(provider_id, include_deprecated=True)
            ]
            form['model_option_values'] = model_option_values
            form['model_combobox'].configure(values=[self.custom_model_option_label] + model_option_values)

        def sync_model_picker_to_current_model(self, provider_id: str) -> None:
            form = self.provider_forms[provider_id]
            model_name = str(form['model_var'].get()).strip()
            model_option_values = form.get('model_option_values') or []
            if model_name in model_option_values:
                form['model_picker_var'].set(model_name)
                return

            form['model_picker_var'].set(self.custom_model_option_label)

        def update_provider_controls(self, provider_id: str) -> None:
            self.sync_model_picker_to_current_model(provider_id)

            if provider_id == OPENAI_PROVIDER_ID:
                self.update_openai_reasoning_controls_state()
                return

            if provider_id == QWEN_PROVIDER_ID:
                self.update_qwen_thinking_controls_state()
                return

            if provider_id == CLAUDE_PROVIDER_ID:
                self.update_claude_thinking_controls_state()

        def update_openai_reasoning_controls_state(self) -> None:
            form = self.provider_forms.get(OPENAI_PROVIDER_ID)
            if form is None:
                return

            if form['enable_reasoning_var'].get() == 1:
                form['reasoning_depth_combobox'].configure(state='readonly')
                return

            form['reasoning_depth_combobox'].configure(state='disabled')

        def update_qwen_thinking_controls_state(self) -> None:
            form = self.provider_forms.get(QWEN_PROVIDER_ID)
            if form is None:
                return

            model_name = str(form['model_var'].get()).strip()
            if requires_qwen_reasoning(model_name):
                form['thinking_var'].set(1)
                form['thinking_checkbox'].configure(state='disabled')
                form['thinking_help_label'].config(text=t('settings.qwen_thinking_required'))
                return

            if supports_qwen_reasoning_toggle(model_name):
                form['thinking_checkbox'].configure(state='normal')
                form['thinking_help_label'].config(text=t('settings.qwen_thinking_supported'))
                return

            form['thinking_var'].set(0)
            form['thinking_checkbox'].configure(state='disabled')
            form['thinking_help_label'].config(text=t('settings.qwen_thinking_unsupported'))

        def update_claude_thinking_controls_state(self) -> None:
            form = self.provider_forms.get(CLAUDE_PROVIDER_ID)
            if form is None:
                return

            if form['thinking_var'].get() == 1:
                form['thinking_budget_entry'].configure(state='normal')
                form['thinking_help_label'].config(text=t('settings.claude_thinking_help_enabled'))
                return

            form['thinking_budget_entry'].configure(state='disabled')
            form['thinking_help_label'].config(text=t('settings.claude_thinking_help_disabled'))

        def load_provider_form(self, provider_id: str, provider_settings: dict[str, Any]) -> None:
            form = self.provider_forms[provider_id]
            form['api_key_entry'].delete(0, 'end')
            form['api_key_entry'].insert(0, str(provider_settings.get('api_key') or ''))

            form['base_url_entry'].delete(0, 'end')
            form['base_url_entry'].insert(
                0,
                str(provider_settings.get('base_url') or get_default_base_url_for_provider(provider_id)),
            )

            form['model_var'].set(str(provider_settings.get('model') or get_default_model_for_provider(provider_id)))
            self.refresh_model_options_for_provider(provider_id)
            self.sync_model_picker_to_current_model(provider_id)

            if provider_id == OPENAI_PROVIDER_ID:
                reasoning_settings = provider_settings.get('reasoning')
                if not isinstance(reasoning_settings, dict):
                    reasoning_settings = {}
                form['enable_reasoning_var'].set(1 if bool(reasoning_settings.get('enabled', False)) else 0)
                reasoning_depth = str(reasoning_settings.get('depth') or DEFAULT_REASONING_DEPTH).strip().lower()
                if reasoning_depth not in REASONING_DEPTH_OPTIONS:
                    reasoning_depth = DEFAULT_REASONING_DEPTH
                form['reasoning_depth_var'].set(reasoning_depth)
                return

            if provider_id == QWEN_PROVIDER_ID:
                thinking_settings = provider_settings.get('thinking')
                if not isinstance(thinking_settings, dict):
                    thinking_settings = {}
                form['thinking_var'].set(1 if bool(thinking_settings.get('enabled', False)) else 0)
                return

            if provider_id == CLAUDE_PROVIDER_ID:
                thinking_settings = provider_settings.get('thinking')
                if not isinstance(thinking_settings, dict):
                    thinking_settings = {}
                form['thinking_var'].set(1 if bool(thinking_settings.get('enabled', False)) else 0)
                budget_tokens = thinking_settings.get('budget_tokens', DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS)
                form['thinking_budget_var'].set(str(budget_tokens))

        def get_active_provider_id_from_form(self) -> str:
            selected_label = self.active_provider_var.get().strip()
            provider_id = self.provider_label_to_id.get(selected_label)
            if provider_id in self.provider_ids:
                return str(provider_id)
            return DEFAULT_PROVIDER_ID

        def resolve_provider_model_name(self, provider_id: str) -> str:
            form = self.provider_forms[provider_id]
            model_name = str(form['model_var'].get()).strip()
            if model_name != '':
                return model_name

            selected_model = str(form['model_picker_var'].get()).strip()
            if selected_model != '' and selected_model != self.custom_model_option_label:
                return selected_model

            return ''

        def build_openai_provider_settings(self) -> dict[str, Any]:
            form = self.provider_forms[OPENAI_PROVIDER_ID]
            model_name = self.resolve_provider_model_name(OPENAI_PROVIDER_ID)
            if model_name == '':
                raise ValueError(t('settings.provider_model_required', provider='OpenAI'))

            base_url = str(form['base_url_entry'].get()).strip()
            if base_url == '':
                base_url = get_default_base_url_for_provider(OPENAI_PROVIDER_ID)

            reasoning_depth = str(form['reasoning_depth_var'].get()).strip().lower()
            if reasoning_depth not in REASONING_DEPTH_OPTIONS:
                reasoning_depth = DEFAULT_REASONING_DEPTH

            return {
                'api_key': str(form['api_key_entry'].get()).strip(),
                'base_url': base_url,
                'model': model_name,
                'reasoning': {
                    'enabled': bool(form['enable_reasoning_var'].get()),
                    'depth': reasoning_depth,
                },
            }

        def build_qwen_provider_settings(self) -> dict[str, Any]:
            form = self.provider_forms[QWEN_PROVIDER_ID]
            model_name = self.resolve_provider_model_name(QWEN_PROVIDER_ID)
            if model_name == '':
                raise ValueError(t('settings.provider_model_required', provider='Qwen'))

            base_url = str(form['base_url_entry'].get()).strip()
            if base_url == '':
                base_url = get_default_base_url_for_provider(QWEN_PROVIDER_ID)

            thinking_enabled = bool(form['thinking_var'].get())
            if requires_qwen_reasoning(model_name):
                thinking_enabled = True
            elif not supports_qwen_reasoning_toggle(model_name):
                thinking_enabled = False

            return {
                'api_key': str(form['api_key_entry'].get()).strip(),
                'base_url': base_url,
                'model': model_name,
                'thinking': {
                    'enabled': thinking_enabled,
                },
            }

        def build_claude_provider_settings(self) -> dict[str, Any]:
            form = self.provider_forms[CLAUDE_PROVIDER_ID]
            model_name = self.resolve_provider_model_name(CLAUDE_PROVIDER_ID)
            if model_name == '':
                raise ValueError(t('settings.provider_model_required', provider='Claude'))

            base_url = str(form['base_url_entry'].get()).strip()
            if base_url == '':
                base_url = get_default_base_url_for_provider(CLAUDE_PROVIDER_ID)

            budget_text = str(form['thinking_budget_var'].get()).strip()
            budget_tokens = DEFAULT_CLAUDE_THINKING_BUDGET_TOKENS
            if budget_text != '':
                try:
                    budget_tokens = int(budget_text)
                except Exception:
                    raise ValueError(t('settings.claude_thinking_budget_invalid'))
            if budget_tokens <= 0:
                raise ValueError(t('settings.claude_thinking_budget_invalid'))

            return {
                'api_key': str(form['api_key_entry'].get()).strip(),
                'base_url': base_url,
                'model': model_name,
                'thinking': {
                    'enabled': bool(form['thinking_var'].get()),
                    'budget_tokens': budget_tokens,
                },
            }

        def save_button(self) -> None:
            theme = self.pending_theme_name or self.theme_var.get().strip()
            request_timeout_text = self.request_timeout_entry.get().strip()
            if request_timeout_text == '':
                request_timeout_seconds = DEFAULT_REQUEST_TIMEOUT_SECONDS
            else:
                try:
                    request_timeout_seconds = float(request_timeout_text)
                except Exception:
                    self.set_feedback(t('settings.request_timeout_invalid'), is_error=True)
                    return

            try:
                provider_settings = {
                    OPENAI_PROVIDER_ID: self.build_openai_provider_settings(),
                    QWEN_PROVIDER_ID: self.build_qwen_provider_settings(),
                    CLAUDE_PROVIDER_ID: self.build_claude_provider_settings(),
                }
            except ValueError as e:
                self.set_feedback(str(e), is_error=True)
                return

            settings_dict = {
                'active_provider': self.get_active_provider_id_from_form(),
                'providers': provider_settings,
                'runtime': {
                    'request_timeout_seconds': request_timeout_seconds,
                    'play_ding_on_completion': bool(self.play_ding.get()),
                    'disable_local_step_verification': bool(self.disable_local_step_verification_var.get()),
                },
                'appearance': {
                    'theme': theme,
                    'language': self.get_language_code_from_label(self.language_var.get()),
                },
                'advanced': {
                    'custom_llm_instructions': self.llm_instructions_text.get('1.0', 'end-1c').strip(),
                    'save_model_prompt_images': bool(self.save_model_prompt_images_var.get()),
                    'save_prompt_text_dumps': bool(self.save_prompt_text_dumps_var.get()),
                },
            }

            try:
                saved_settings = self.settings.save_settings(settings_dict)
            except Exception as e:
                self.set_feedback(str(e), is_error=True)
                return

            appearance_settings = saved_settings.get('appearance')
            language_code = get_current_language()
            if isinstance(appearance_settings, dict):
                language_code = str(appearance_settings.get('language') or get_current_language())
            set_current_language(language_code, persist=False)

            self.set_feedback(t('core.runtime_settings_reloaded'), is_error=False)

            if hasattr(self.master, 'apply_translations'):
                self.master.apply_translations()

            if hasattr(self.master, 'user_request_queue'):
                self.master.user_request_queue.put({'type': 'settings_updated'})

            self.after(120, self.destroy)

            try:
                self.master.schedule_theme_change(theme)
            except Exception:
                pass

    class MainWindow(ttk.Window):
        def __init__(self):
            settings = Settings()
            settings_dict = settings.get_dict()
            appearance_settings = settings_dict.get('appearance')
            if not isinstance(appearance_settings, dict):
                appearance_settings = {}
            set_current_language(appearance_settings.get('language'))
            theme = appearance_settings.get('theme', 'superhero')

            try:
                super().__init__(themename=theme)
            except:
                super().__init__()  # https://github.com/AmberSahdev/Open-Interface/issues/35

            self.last_message_key = None
            self.last_message_kwargs = {}
            self.active_session_id = None
            self.session_list_data: list[dict[str, Any]] = []
            self.message_history_data: list[dict[str, Any]] = []
            self.timeline_history_data: list[dict[str, Any]] = []
            self.current_runtime_status_payload: Any = ''

            self.title(t('general.app_title'))
            self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x_position = max((screen_width - DEFAULT_WINDOW_WIDTH) // 2, 0)
            y_position = max((screen_height - DEFAULT_WINDOW_HEIGHT) // 2, 0)
            self.geometry(f'{DEFAULT_WINDOW_WIDTH}x{DEFAULT_WINDOW_HEIGHT}+{x_position}+{y_position}')

            # PhotoImage object needs to persist as long as the app does, hence it's a class object.
            path_to_icon_png = Path(__file__).resolve().parent.joinpath('resources', 'icon.png')
            # path_to_microphone_png = Path(__file__).resolve().parent.joinpath('resources', 'microphone.png')
            self.logo_img = ImageTk.PhotoImage(Image.open(path_to_icon_png).resize((50, 50)))
            # self.mic_icon = ImageTk.PhotoImage(Image.open(path_to_microphone_png).resize((18, 18)))

            # This adds app icon in linux which pyinstaller can't
            self.tk.call('wm', 'iconphoto', self._w, self.logo_img)

            ###
            # MP Queue to facilitate communication between UI and Core.
            # Put user requests received from UI text box into this queue which will then be dequeued in App to be sent
            # to core.
            self.user_request_queue = Queue()

            # Put messages to display on the UI here so we can dequeue them in the main thread
            self.message_display_queue = Queue()
            # Set up periodic UI processing
            self.after(200, self.process_message_display_queue)
            ###

            self.create_widgets()
            self.apply_translations()

        def change_theme(self, theme_name: str) -> None:
            selected_theme = str(theme_name or '').strip()
            if selected_theme == '':
                return

            current_theme_name = ''
            try:
                current_theme_name = self.style.theme.name
            except Exception:
                current_theme_name = ''

            if selected_theme == current_theme_name:
                return

            try:
                self.style.theme_use(selected_theme)
            except Exception as e:
                self.set_runtime_status({
                    'level': 'error',
                    'title': t('settings.theme_apply_failed_title'),
                    'message': t('settings.theme_apply_failed_message'),
                    'hint': t('settings.theme_apply_failed_hint'),
                    'details': str(e),
                })

        def schedule_theme_change(self, theme_name: str) -> None:
            selected_theme = str(theme_name or '').strip()
            if selected_theme == '':
                return

            self.after(120, lambda: self.change_theme(selected_theme))

        def create_widgets(self) -> None:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)
            self.rowconfigure(2, weight=1)

            self.toolbar_frame = ttk.Frame(self, padding=(18, 14, 18, 10))
            self.toolbar_frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E))
            self.toolbar_frame.columnconfigure(1, weight=1)

            self.logo_label = ttk.Label(self.toolbar_frame, image=self.logo_img)
            self.logo_label.grid(column=0, row=0, rowspan=2, sticky=ttk.W, padx=(0, 12))

            self.app_title_label = ttk.Label(
                self.toolbar_frame,
                text=t('general.app_title'),
                font=('Helvetica', 18),
                bootstyle='primary',
            )
            self.app_title_label.grid(column=1, row=0, sticky=ttk.W)

            self.heading_label = ttk.Label(
                self.toolbar_frame,
                text=t('main.heading'),
                bootstyle='secondary',
                wraplength=420,
            )
            self.heading_label.grid(column=1, row=1, sticky=ttk.W)

            self.language_options = get_language_options()
            self.language_var = ttk.StringVar(value=get_language_label(get_current_language()))
            self.language_selector = ttk.Combobox(
                self.toolbar_frame,
                textvariable=self.language_var,
                values=[label for _, label in self.language_options],
                state='readonly',
                width=10,
            )
            self.language_selector.bind('<<ComboboxSelected>>', self.on_language_selected)
            self.language_selector.grid(column=2, row=0, sticky=ttk.E, padx=(12, 8))

            self.settings_button = ttk.Button(
                self.toolbar_frame,
                text=t('main.settings'),
                bootstyle='info-outline',
                command=self.open_settings,
            )
            self.settings_button.grid(column=3, row=0, sticky=ttk.E, padx=(0, 8))

            self.stop_button = ttk.Button(
                self.toolbar_frame,
                text=t('main.interrupt'),
                bootstyle='danger-outline',
                command=self.interrupt_request,
            )
            self.stop_button.grid(column=4, row=0, sticky=ttk.E)

            self.restart_button = ttk.Button(
                self.toolbar_frame,
                text=t('main.restart_request'),
                bootstyle='warning-outline',
                command=self.restart_request,
            )
            self.restart_button.grid(column=5, row=0, sticky=ttk.E, padx=(8, 0))

            # --- Separator between toolbar and content ---
            self.toolbar_separator = ttk.Separator(self, orient='horizontal')
            self.toolbar_separator.grid(column=0, row=1, sticky=(ttk.W, ttk.E), padx=18)

            self.content_frame = ttk.Frame(self, padding=(18, 12, 18, 18))
            self.content_frame.grid(column=0, row=2, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.content_frame.columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
            self.content_frame.columnconfigure(1, weight=0)  # vertical separator column
            self.content_frame.columnconfigure(2, weight=1)
            self.content_frame.rowconfigure(0, weight=1)

            self.sidebar_frame = ttk.Frame(self.content_frame, padding=(0, 0, 14, 0))
            self.sidebar_frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.sidebar_frame.columnconfigure(0, weight=1)
            self.sidebar_frame.rowconfigure(1, weight=1)

            self.session_list_label = ttk.Label(
                self.sidebar_frame,
                text=t('main.session_list'),
                font=('Helvetica', 14),
                bootstyle='primary',
            )
            self.session_list_label.grid(column=0, row=0, sticky=ttk.W)

            self.session_list_canvas_frame = ttk.Frame(self.sidebar_frame)
            self.session_list_canvas_frame.grid(column=0, row=1, sticky=(ttk.W, ttk.E, ttk.N, ttk.S), pady=(12, 12))
            self.session_list_canvas_frame.columnconfigure(0, weight=1)
            self.session_list_canvas_frame.rowconfigure(0, weight=1)

            self.session_list_canvas = ttk.Canvas(self.session_list_canvas_frame, highlightthickness=0)
            self.session_list_canvas.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.session_list_scrollbar = ttk.Scrollbar(
                self.session_list_canvas_frame,
                orient='vertical',
                command=self.session_list_canvas.yview,
            )
            self.session_list_scrollbar.grid(column=1, row=0, sticky=(ttk.N, ttk.S))
            self.session_list_canvas.configure(yscrollcommand=self.session_list_scrollbar.set)

            self.session_list_inner = ttk.Frame(self.session_list_canvas)
            self.session_list_window = self.session_list_canvas.create_window(
                (0, 0),
                window=self.session_list_inner,
                anchor='nw',
            )
            self.session_list_inner.bind('<Configure>', self.on_session_list_inner_configure)
            self.session_list_canvas.bind('<Configure>', self.on_session_list_canvas_configure)

            # Bind mousewheel for session list scrolling
            self.session_list_canvas.bind('<MouseWheel>', self._on_session_list_mousewheel)
            self.session_list_inner.bind('<MouseWheel>', self._on_session_list_mousewheel)

            self.new_session_button = ttk.Button(
                self.sidebar_frame,
                text=t('main.new_session'),
                bootstyle='secondary',
                command=self.create_session,
            )
            self.new_session_button.grid(column=0, row=2, sticky=(ttk.W, ttk.E))

            # --- Vertical separator between sidebar and detail ---
            self.vertical_separator = ttk.Separator(self.content_frame, orient='vertical')
            self.vertical_separator.grid(column=1, row=0, sticky=(ttk.N, ttk.S), padx=(0, 14))

            self.detail_frame = ttk.Frame(self.content_frame)
            self.detail_frame.grid(column=2, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.detail_frame.columnconfigure(0, weight=1)
            self.detail_frame.rowconfigure(2, weight=1)

            self.chat_header_frame = ttk.Frame(self.detail_frame, padding=(0, 0, 0, 10))
            self.chat_header_frame.grid(column=0, row=0, sticky=(ttk.W, ttk.E))
            self.chat_header_frame.columnconfigure(0, weight=1)

            self.chat_title_label = ttk.Label(
                self.chat_header_frame,
                text=t('main.new_session_placeholder'),
                font=('Helvetica', 16),
                bootstyle='primary',
            )
            self.chat_title_label.grid(column=0, row=0, sticky=ttk.W)

            self.chat_subtitle_label = ttk.Label(
                self.chat_header_frame,
                text=t('main.chat_subtitle'),
                bootstyle='secondary',
            )
            self.chat_subtitle_label.grid(column=0, row=1, sticky=ttk.W, pady=(4, 0))

            self.runtime_feedback_frame = ttk.Frame(self.detail_frame, padding=(12, 10))
            self.runtime_feedback_frame.grid(column=0, row=1, sticky=(ttk.W, ttk.E), pady=(0, 10))
            self.runtime_feedback_frame.columnconfigure(0, weight=1)

            self.runtime_feedback_title_label = ttk.Label(
                self.runtime_feedback_frame,
                text='',
                font=('Helvetica', 12),
                bootstyle='danger',
            )
            self.runtime_feedback_title_label.grid(column=0, row=0, sticky=ttk.W)

            self.runtime_feedback_message_label = ttk.Label(
                self.runtime_feedback_frame,
                text='',
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            self.runtime_feedback_message_label.grid(column=0, row=1, sticky=ttk.W, pady=(4, 0))

            self.runtime_feedback_path_label = ttk.Label(
                self.runtime_feedback_frame,
                text='',
                bootstyle='secondary',
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            self.runtime_feedback_path_label.grid(column=0, row=2, sticky=ttk.W, pady=(4, 0))

            self.runtime_feedback_hint_label = ttk.Label(
                self.runtime_feedback_frame,
                text='',
                bootstyle='warning',
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            self.runtime_feedback_hint_label.grid(column=0, row=3, sticky=ttk.W, pady=(4, 0))

            self.runtime_feedback_details_label = ttk.Label(
                self.runtime_feedback_frame,
                text='',
                bootstyle='secondary',
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            self.runtime_feedback_details_label.grid(column=0, row=4, sticky=ttk.W, pady=(4, 0))
            self.runtime_feedback_frame.grid_remove()

            self.message_history_frame = ttk.Frame(self.detail_frame)
            self.message_history_frame.grid(column=0, row=2, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.message_history_frame.columnconfigure(0, weight=1)
            self.message_history_frame.rowconfigure(1, weight=1)

            self.history_label = ttk.Label(
                self.message_history_frame,
                text=t('main.history_title'),
                font=('Helvetica', 13),
                bootstyle='primary',
            )
            self.history_label.grid(column=0, row=0, sticky=ttk.W, pady=(0, 10))

            self.message_history_canvas_frame = ttk.Frame(self.message_history_frame)
            self.message_history_canvas_frame.grid(column=0, row=1, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.message_history_canvas_frame.columnconfigure(0, weight=1)
            self.message_history_canvas_frame.rowconfigure(0, weight=1)

            self.message_history_canvas = ttk.Canvas(self.message_history_canvas_frame, highlightthickness=0)
            self.message_history_canvas.grid(column=0, row=0, sticky=(ttk.W, ttk.E, ttk.N, ttk.S))
            self.message_history_scrollbar = ttk.Scrollbar(
                self.message_history_canvas_frame,
                orient='vertical',
                command=self.message_history_canvas.yview,
            )
            self.message_history_scrollbar.grid(column=1, row=0, sticky=(ttk.N, ttk.S))
            self.message_history_canvas.configure(yscrollcommand=self.message_history_scrollbar.set)

            self.message_history_inner = ttk.Frame(self.message_history_canvas)
            self.message_history_window = self.message_history_canvas.create_window(
                (0, 0),
                window=self.message_history_inner,
                anchor='nw',
            )
            self.message_history_inner.bind('<Configure>', self.on_message_history_inner_configure)
            self.message_history_canvas.bind('<Configure>', self.on_message_history_canvas_configure)

            # Bind mousewheel for message history scrolling
            self.message_history_canvas.bind('<MouseWheel>', self._on_message_history_mousewheel)
            self.message_history_inner.bind('<MouseWheel>', self._on_message_history_mousewheel)

            # --- Separator above input area ---
            self.input_separator = ttk.Separator(self.detail_frame, orient='horizontal')
            self.input_separator.grid(column=0, row=3, sticky=(ttk.W, ttk.E), pady=(10, 0))

            self.input_frame = ttk.Frame(self.detail_frame, padding=(0, 12, 0, 10))
            self.input_frame.grid(column=0, row=4, sticky=(ttk.W, ttk.E))
            self.input_frame.columnconfigure(0, weight=1)

            self.input_label = ttk.Label(
                self.input_frame,
                text=t('main.input_title'),
                font=('Helvetica', 13),
                bootstyle='primary',
            )
            self.input_label.grid(column=0, row=0, sticky=ttk.W, pady=(0, 8))

            self.request_text = ttk.Text(self.input_frame, height=5)
            self.request_text.grid(column=0, row=1, sticky=(ttk.W, ttk.E))
            self.request_text.bind('<Return>', self.on_request_text_enter)
            self.request_text.bind('<KP_Enter>', self.on_request_text_enter)

            self.submit_button = ttk.Button(
                self.input_frame,
                text=t('main.submit'),
                bootstyle='success',
                command=self.execute_user_request,
            )
            self.submit_button.grid(column=0, row=2, sticky=ttk.E, pady=(10, 0))

            # --- Separator above runtime status ---
            self.status_separator = ttk.Separator(self.detail_frame, orient='horizontal')
            self.status_separator.grid(column=0, row=5, sticky=(ttk.W, ttk.E), pady=(6, 0))

            self.runtime_status_frame = ttk.Frame(self.detail_frame, padding=(0, 8, 0, 4))
            self.runtime_status_frame.grid(column=0, row=6, sticky=(ttk.W, ttk.E))
            self.runtime_status_frame.columnconfigure(0, weight=1)

            self.runtime_status_label = ttk.Label(
                self.runtime_status_frame,
                text=t('main.runtime_status'),
                font=('Helvetica', 13),
                bootstyle='primary',
            )
            self.runtime_status_label.grid(column=0, row=0, sticky=ttk.W)

            self.message_display = ttk.Label(
                self.runtime_status_frame,
                text=t('main.runtime_idle'),
                bootstyle='secondary',
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            self.message_display.grid(column=0, row=1, sticky=(ttk.W, ttk.E), pady=(4, 0))

            self.load_session_list([])
            self.load_message_history([])

        def on_session_list_inner_configure(self, event=None) -> None:
            self.session_list_canvas.configure(scrollregion=self.session_list_canvas.bbox('all'))

        def on_session_list_canvas_configure(self, event) -> None:
            self.session_list_canvas.itemconfigure(self.session_list_window, width=event.width)

        def on_message_history_inner_configure(self, event=None) -> None:
            self.message_history_canvas.configure(scrollregion=self.message_history_canvas.bbox('all'))

        def on_message_history_canvas_configure(self, event) -> None:
            self.message_history_canvas.itemconfigure(self.message_history_window, width=event.width)

        # --- MouseWheel scrolling helpers ---
        def _on_session_list_mousewheel(self, event) -> None:
            if hasattr(event, 'delta') and event.delta != 0:
                if abs(event.delta) >= 120:
                    delta = int(-1 * (event.delta / 120))
                else:
                    delta = int(-1 * event.delta)
                self.session_list_canvas.yview_scroll(delta, 'units')

        def _on_message_history_mousewheel(self, event) -> None:
            if hasattr(event, 'delta') and event.delta != 0:
                if abs(event.delta) >= 120:
                    delta = int(-1 * (event.delta / 120))
                else:
                    delta = int(-1 * event.delta)
                self.message_history_canvas.yview_scroll(delta, 'units')

        def _bind_mousewheel_recursive(self, widget, handler) -> None:
            """Recursively bind mousewheel event to a widget and all its descendants."""
            widget.bind('<MouseWheel>', handler)
            for child in widget.winfo_children():
                self._bind_mousewheel_recursive(child, handler)

        def on_request_text_enter(self, event=None):
            shift_key_mask = 0x0001
            if event is not None and event.state & shift_key_mask:
                return None

            self.execute_user_request()
            return 'break'

        def _bind_session_click(self, widget: Any, session_id: Any) -> None:
            if session_id is None:
                return

            widget.bind(
                '<Button-1>',
                lambda event, target_session_id=str(session_id): self.on_session_selected(event, target_session_id),
            )
            try:
                widget.configure(cursor='hand2')
            except Exception:
                pass

        def on_session_selected(self, event=None, session_id: str = '') -> None:
            self.request_switch_session(session_id)

        def request_switch_session(self, session_id: str) -> None:
            target_session_id = str(session_id or '').strip()
            if target_session_id == '' or target_session_id == self.active_session_id:
                return

            self.user_request_queue.put({
                'type': 'switch_session',
                'session_id': target_session_id,
            })

        def create_session(self) -> None:
            self.user_request_queue.put({'type': 'create_session'})

        def load_session_list(self, sessions: list[dict[str, Any]]) -> None:
            self.session_list_data = list(sessions)

            for child in self.session_list_inner.winfo_children():
                child.destroy()

            active_session = None
            if self.active_session_id is not None:
                for session in self.session_list_data:
                    if session.get('id') == self.active_session_id:
                        active_session = session
                        break

            if len(self.session_list_data) == 0:
                empty_label = ttk.Label(
                    self.session_list_inner,
                    text=t('main.no_sessions'),
                    bootstyle='secondary',
                    wraplength=SIDEBAR_WIDTH - 40,
                    justify='left',
                )
                empty_label.pack(fill='x', padx=10, pady=10)
                self._update_active_session_header(None)
                return

            for session in self.session_list_data:
                session_id = session.get('id')
                is_active = session.get('id') == self.active_session_id
                card_bootstyle = 'info' if is_active else 'secondary'
                title_style = 'primary' if is_active else 'default'

                card = ttk.LabelFrame(
                    self.session_list_inner,
                    bootstyle=card_bootstyle,
                    padding=(14, 12),
                )
                card.pack(fill='x', padx=6, pady=5)
                self._bind_session_click(card, session_id)

                title_label = ttk.Label(
                    card,
                    text=session.get('title') or t('main.new_session_placeholder'),
                    font=('Helvetica', 12, 'bold') if is_active else ('Helvetica', 12),
                    bootstyle=title_style,
                    wraplength=SIDEBAR_WIDTH - 70,
                    justify='left',
                )
                title_label.pack(anchor='w')
                self._bind_session_click(title_label, session_id)

                updated_at = session.get('updated_at') or ''
                if updated_at != '':
                    updated_label = ttk.Label(
                        card,
                        text=t('main.session_updated', updated_at=updated_at),
                        bootstyle='secondary',
                        font=('Helvetica', 9),
                        wraplength=SIDEBAR_WIDTH - 70,
                        justify='left',
                    )
                    updated_label.pack(anchor='w', pady=(6, 0))
                    self._bind_session_click(updated_label, session_id)

                # Bind mousewheel so scrolling works over session cards
                self._bind_mousewheel_recursive(card, self._on_session_list_mousewheel)

            self._update_active_session_header(active_session)

        def hydrate_session_view(self, payload: dict[str, Any]) -> None:
            self.active_session_id = payload.get('active_session_id')
            self.last_message_key = None
            self.last_message_kwargs = {}
            self.load_session_list(list(payload.get('sessions') or []))
            self.load_timeline_history(list(payload.get('timeline_entries') or []))
            self.set_runtime_status(str(payload.get('runtime_status') or ''))

        def load_message_history(self, messages: list[dict[str, Any]]) -> None:
            self.load_timeline_history(messages)

        def load_timeline_history(self, entries: list[dict[str, Any]]) -> None:
            normalized_entries: list[dict[str, Any]] = []
            for entry in entries:
                normalized_entries.append(self._normalize_timeline_item(entry))

            self.timeline_history_data = self._sort_timeline_items(normalized_entries)
            self.message_history_data = list(self.timeline_history_data)
            self._render_timeline_history()

        def append_message_item(self, message: dict[str, Any]) -> None:
            self.timeline_history_data.append(self._normalize_timeline_item(message))
            self.timeline_history_data = self._sort_timeline_items(self.timeline_history_data)
            self.message_history_data = list(self.timeline_history_data)
            self._render_timeline_history()

        def append_execution_log_item(self, execution_log: dict[str, Any]) -> None:
            self.timeline_history_data.append(self._normalize_timeline_item(execution_log))
            self.timeline_history_data = self._sort_timeline_items(self.timeline_history_data)
            self.message_history_data = list(self.timeline_history_data)
            self._render_timeline_history()

        def _render_timeline_history(self) -> None:
            for child in self.message_history_inner.winfo_children():
                child.destroy()

            if len(self.timeline_history_data) == 0:
                empty_label = ttk.Label(
                    self.message_history_inner,
                    text=t('main.no_messages'),
                    bootstyle='secondary',
                    wraplength=MESSAGE_WRAP_LENGTH,
                    justify='center',
                    anchor='center',
                )
                empty_label.pack(fill='x', padx=12, pady=40)
                return

            for timeline_item in self.timeline_history_data:
                self._render_timeline_item(timeline_item)

            # Bind mousewheel to all timeline children for smooth scrolling
            self._bind_mousewheel_recursive(self.message_history_inner, self._on_message_history_mousewheel)

            self.after_idle(self.scroll_message_history_to_bottom)

        def _render_timeline_item(self, timeline_item: dict[str, Any]) -> None:
            timeline_type = timeline_item.get('timeline_type') or 'message'
            if timeline_type == 'execution_log':
                self._render_execution_log_item(timeline_item)
                return

            self._render_message_item(timeline_item)

        def _render_message_item(self, message: dict[str, Any]) -> None:
            role = message.get('role') or 'assistant'
            is_user = role == 'user'

            row_frame = ttk.Frame(self.message_history_inner)
            row_frame.pack(fill='x', padx=8, pady=5)

            bubble_style = 'info' if is_user else 'secondary'
            bubble = ttk.LabelFrame(row_frame, bootstyle=bubble_style, padding=(14, 10))
            bubble.pack(anchor='e' if is_user else 'w', fill='x')

            role_label = ttk.Label(
                bubble,
                text=self.get_message_role_text(role),
                font=('Helvetica', 11, 'bold'),
                bootstyle='primary' if is_user else 'info',
            )
            role_label.pack(anchor='w')

            content_label = ttk.Label(
                bubble,
                text=message.get('content', ''),
                wraplength=MESSAGE_WRAP_LENGTH,
                justify='left',
            )
            content_label.pack(anchor='w', pady=(6, 0))

        def _render_execution_log_item(self, execution_log: dict[str, Any]) -> None:
            row_frame = ttk.Frame(self.message_history_inner)
            row_frame.pack(fill='x', padx=8, pady=5)

            card = ttk.LabelFrame(row_frame, bootstyle='warning', padding=(14, 10))
            card.pack(anchor='w', fill='x')

            title_label = ttk.Label(
                card,
                text=t('main.execution_step_title', step_index=execution_log.get('step_index', 0)),
                font=('Helvetica', 11),
                bootstyle='warning',
            )
            title_label.pack(anchor='w')

            status_label = ttk.Label(
                card,
                text=t('main.execution_status', status=self.get_execution_status_text(execution_log.get('status', ''))),
                bootstyle='secondary',
            )
            status_label.pack(anchor='w', pady=(2, 0))

            justification = execution_log.get('justification') or ''
            if justification != '':
                justification_label = ttk.Label(
                    card,
                    text=justification,
                    wraplength=MESSAGE_WRAP_LENGTH,
                    justify='left',
                )
                justification_label.pack(anchor='w', pady=(4, 0))

            function_name = execution_log.get('function_name') or ''
            if function_name != '':
                function_label = ttk.Label(
                    card,
                    text=t('main.execution_function', function_name=function_name),
                    bootstyle='secondary',
                    wraplength=MESSAGE_WRAP_LENGTH,
                    justify='left',
                )
                function_label.pack(anchor='w', pady=(4, 0))

            parameters_text = self.format_parameters_text(execution_log.get('parameters_json'))
            if parameters_text != '':
                parameters_label = ttk.Label(
                    card,
                    text=t('main.execution_parameters', parameters=parameters_text),
                    bootstyle='secondary',
                    wraplength=MESSAGE_WRAP_LENGTH,
                    justify='left',
                )
                parameters_label.pack(anchor='w', pady=(4, 0))

            error_message = execution_log.get('error_message') or ''
            if error_message != '':
                error_label = ttk.Label(
                    card,
                    text=t('main.execution_error', error_message=error_message),
                    bootstyle='danger',
                    wraplength=MESSAGE_WRAP_LENGTH,
                    justify='left',
                )
                error_label.pack(anchor='w', pady=(4, 0))

        def _normalize_timeline_item(self, item: dict[str, Any]) -> dict[str, Any]:
            normalized_item = dict(item)
            timeline_type = normalized_item.get('timeline_type')
            if timeline_type in ('message', 'execution_log'):
                return normalized_item

            if 'role' in normalized_item or 'content' in normalized_item:
                normalized_item['timeline_type'] = 'message'
                return normalized_item

            normalized_item['timeline_type'] = 'execution_log'
            return normalized_item

        def _sort_timeline_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return sorted(items, key=self._timeline_sort_key)

        def _timeline_sort_key(self, item: dict[str, Any]) -> tuple[str, int, int]:
            created_at = item.get('created_at') or ''
            timeline_type = item.get('timeline_type') or 'message'
            type_order = 0 if timeline_type == 'message' else 1
            step_index = item.get('step_index')
            if step_index is None:
                return created_at, type_order, -1

            return created_at, type_order, int(step_index)

        def format_parameters_text(self, parameters_json: Any) -> str:
            if parameters_json is None:
                return ''

            if isinstance(parameters_json, str):
                text = parameters_json
                try:
                    parsed = json.loads(parameters_json)
                    text = json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    text = parameters_json
            else:
                text = json.dumps(parameters_json, ensure_ascii=False)

            if len(text) <= PARAMETERS_PREVIEW_MAX_LENGTH:
                return text

            return text[:PARAMETERS_PREVIEW_MAX_LENGTH] + '...'

        def _show_runtime_issue(self, issue: dict[str, Any]) -> None:
            title = str(issue.get('title') or '').strip()
            message = str(issue.get('message') or '').strip()
            path = str(issue.get('path') or '').strip()
            hint = str(issue.get('hint') or '').strip()
            details = str(issue.get('details') or '').strip()

            if title == '' and path == '' and hint == '' and details == '':
                self.runtime_feedback_frame.grid_remove()
                return

            self.runtime_feedback_title_label.config(text=title)
            self.runtime_feedback_message_label.config(text=message)

            if path == '':
                self.runtime_feedback_path_label.config(text='')
            else:
                self.runtime_feedback_path_label.config(text=t('main.runtime_issue_path', path=path))

            if hint == '':
                self.runtime_feedback_hint_label.config(text='')
            else:
                self.runtime_feedback_hint_label.config(text=t('main.runtime_issue_hint', hint=hint))

            if details == '':
                self.runtime_feedback_details_label.config(text='')
            else:
                self.runtime_feedback_details_label.config(text=t('main.runtime_issue_details', details=details))

            self.runtime_feedback_frame.grid()

        def _hide_runtime_issue(self) -> None:
            self.runtime_feedback_title_label.config(text='')
            self.runtime_feedback_message_label.config(text='')
            self.runtime_feedback_path_label.config(text='')
            self.runtime_feedback_hint_label.config(text='')
            self.runtime_feedback_details_label.config(text='')
            self.runtime_feedback_frame.grid_remove()

        def set_runtime_status(self, status_payload: Any) -> None:
            self.current_runtime_status_payload = status_payload

            if isinstance(status_payload, dict):
                status_issue = dict(status_payload)
                message = str(status_issue.get('message') or '')
                should_show_issue = (
                    str(status_issue.get('title') or '').strip() != ''
                    or str(status_issue.get('path') or '').strip() != ''
                    or str(status_issue.get('hint') or '').strip() != ''
                    or str(status_issue.get('details') or '').strip() != ''
                )
                if should_show_issue:
                    self._show_runtime_issue(status_issue)
                else:
                    self._hide_runtime_issue()
            else:
                message = str(status_payload or '')
                if message == '':
                    self._hide_runtime_issue()

            if message == '':
                message = t('main.runtime_idle')

            self.message_display.config(text=message)

        def get_execution_status_text(self, status: str) -> str:
            if status == 'succeeded':
                return t('main.execution_status.succeeded')
            if status == 'failed':
                return t('main.execution_status.failed')
            if status == 'interrupted':
                return t('main.execution_status.interrupted')
            if status == 'started':
                return t('main.execution_status.started')
            return status

        def get_message_role_text(self, role: str) -> str:
            if role == 'user':
                return t('main.role.user')
            if role == 'assistant':
                return t('main.role.assistant')
            if role == 'system':
                return t('main.role.system')
            if role == 'status':
                return t('main.role.status')
            return role

        def _update_active_session_header(self, session: dict[str, Any] | None) -> None:
            if session is None:
                self.chat_title_label.config(text=t('main.new_session_placeholder'))
                self.chat_subtitle_label.config(text=t('main.chat_subtitle'))
                return

            self.chat_title_label.config(text=session.get('title') or t('main.new_session_placeholder'))

            updated_at = session.get('updated_at') or ''
            if updated_at == '':
                self.chat_subtitle_label.config(text=t('main.chat_subtitle'))
                return

            self.chat_subtitle_label.config(text=t('main.session_updated', updated_at=updated_at))

        def scroll_message_history_to_bottom(self) -> None:
            self.message_history_canvas.yview_moveto(1.0)

        def get_language_code_from_label(self, language_label: str) -> str:
            for language_code, label in self.language_options:
                if label == language_label:
                    return language_code
            return get_current_language()

        def refresh_language_selector(self) -> None:
            self.language_options = get_language_options()
            labels = [label for _, label in self.language_options]
            self.language_selector['values'] = labels
            self.language_var.set(get_language_label(get_current_language()))

        def apply_translations(self) -> None:
            self.title(t('general.app_title'))
            self.app_title_label.config(text=t('general.app_title'))
            self.heading_label.config(text=t('main.heading'))
            self.submit_button.config(text=t('main.submit'))
            self.settings_button.config(text=t('main.settings'))
            self.stop_button.config(text=t('main.interrupt'))
            self.restart_button.config(text=t('main.restart_request'))
            self.session_list_label.config(text=t('main.session_list'))
            self.new_session_button.config(text=t('main.new_session'))
            self.history_label.config(text=t('main.history_title'))
            self.input_label.config(text=t('main.input_title'))
            self.runtime_status_label.config(text=t('main.runtime_status'))
            self.refresh_language_selector()

            self.load_session_list(self.session_list_data)
            self.load_message_history(self.message_history_data)

            if self.last_message_key is not None:
                self.update_message(t(self.last_message_key, **self.last_message_kwargs), preserve_translation_key=True)
            else:
                self.set_runtime_status(self.current_runtime_status_payload)

        def on_language_selected(self, event=None) -> None:
            selected_language = self.get_language_code_from_label(self.language_var.get())
            set_current_language(selected_language, persist=True)
            self.apply_translations()

        def open_settings(self) -> None:
            UI.SettingsWindow(self)

        def interrupt_request(self) -> None:
            self.user_request_queue.put({'type': 'interrupt_request'})

        def restart_request(self) -> None:
            self.user_request_queue.put({'type': 'restart_request'})

        def display_input(self) -> str:
            user_input = self.request_text.get('1.0', 'end-1c')
            self.request_text.delete('1.0', ttk.END)
            return user_input.strip()

        def execute_user_request(self) -> None:
            # Puts the user request received from the UI into the MP queue being read in App to be sent to Core.
            user_request = self.display_input()

            if user_request == '' or user_request is None:
                return

            self.last_message_key = 'main.fetching_instructions'
            self.last_message_kwargs = {}
            self.update_message(t('main.fetching_instructions'), preserve_translation_key=True)

            self.user_request_queue.put(user_request)

        def start_voice_input_thread(self) -> None:
            # Start voice input in a separate thread
            threading.Thread(target=self.voice_input, daemon=True).start()

        def voice_input(self) -> None:
            # Function to handle voice input
            # Currently commented out because the speech_recognition library doesn't compile well on MacOS.
            # TODO: Replace with an alternative library
            """
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self.update_message('Listening...')
                # This might also help with asking for mic permissions on Macs
                recognizer.adjust_for_ambient_noise(source)
                try:
                    audio = recognizer.listen(source, timeout=4)
                    try:
                        text = recognizer.recognize_google(audio)
                        self.entry.delete(0, ttk.END)
                        self.entry.insert(0, text)
                        self.update_message('')
                    except sr.UnknownValueError:
                        self.update_message('Could not understand audio')
                    except sr.RequestError as e:
                        self.update_message(f'Could not request results - {e}')
                except sr.WaitTimeoutError:
                    self.update_message('Didn\'t hear anything')
            """

        def update_message(self, message: str, preserve_translation_key: bool = False) -> None:
            # Update the message display with the provided text.
            # Ensure thread safety when updating the Tkinter GUI.
            if not preserve_translation_key:
                self.last_message_key = None
                self.last_message_kwargs = {}

            try:
                self.enqueue_ui_update('set_runtime_status', message)
            except Exception as e:
                print(f"Error updating message: {e}")

        def enqueue_ui_update(self, action: str, payload: Any) -> None:
            if threading.current_thread() is threading.main_thread():
                self.handle_ui_update(action, payload)
                return

            self.message_display_queue.put({
                'action': action,
                'payload': payload,
            })

        def handle_ui_update(self, action: str, payload: Any) -> None:
            if action == 'set_runtime_status':
                self.set_runtime_status(payload)
                return

            if action == 'hydrate_session_view':
                self.hydrate_session_view(dict(payload))
                return

            if action == 'load_session_list':
                self.load_session_list(list(payload))
                return

            if action == 'load_timeline_history':
                self.load_timeline_history(list(payload))
                return

            if action == 'append_message_item':
                self.append_message_item(dict(payload))
                return

            if action == 'append_execution_log_item':
                self.append_execution_log_item(dict(payload))
                return

        def process_message_display_queue(self):
            try:
                while not self.message_display_queue.empty():
                    message = self.message_display_queue.get_nowait()
                    if isinstance(message, dict):
                        self.handle_ui_update(message.get('action', ''), message.get('payload'))
                    else:
                        self.set_runtime_status(str(message))
            except Exception as e:
                print(f"Error processing message_display_queue: {e}")

            # Call this function every 100ms
            self.after(200, self.process_message_display_queue)
