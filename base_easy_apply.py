"""Shared helpers for LinkedIn / Indeed Easy Apply bots."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium import webdriver

from answer_engine import AnswerEngine, detect_application_language, resolve_resume_path


class BaseEasyApply:
    ERROR_LOG_PATH = Path("error_log.json")
    APPLIED_COMPANIES_LOG_PATH = Path("applied_companies_log.json")
    FAILED_APPLICATIONS_LOG_PATH = Path("failed_applications_log.json")

    def __init__(self, data, start_driver=True):
        self.email = data["email"]
        self.password = data["password"]
        self.keywords_list = data.get("keywords") or []
        self.keywords_to_avoid_list = data.get("keywordsToAvoid") or []
        self.keywords = " OR ".join(self.keywords_list)
        self.keywords_to_avoid = " NOT ".join(self.keywords_to_avoid_list)
        self.locations = data.get("locations") or []
        self.filters = data.get("filters") or {}
        self.context_data = data
        self.current_location_index = 0
        if "user_inputs" not in self.context_data:
            self.context_data["user_inputs"] = {}
        self.answer_engine = None
        self._ai_settings = data.get("aiSettings") or {}
        self._ai_enabled = self._ai_settings.get("enabled", True)
        self.driver = None
        if start_driver:
            firefox_service = FirefoxService(executable_path=data["driver_path"])
            self.driver = webdriver.Firefox(service=firefox_service)
        self.init_logging()

    # ------------------------------------------------------------------
    # Answer engine
    # ------------------------------------------------------------------

    def _get_answer_engine(self):
        if not self._ai_enabled:
            return None
        if self.answer_engine is None:
            try:
                self.answer_engine = AnswerEngine(self.context_data, self._ai_settings)
                self.log_info("Local AI answer engine enabled.")
            except Exception as e:
                self.log_info(f"Could not initialize AI answer engine: {e}")
                self._ai_enabled = False
                return None
        return self.answer_engine

    def _current_answer_bucket(self):
        """Location key used for user_inputs cache."""
        if not self.locations:
            return "default"
        if self.current_location_index >= len(self.locations):
            return self.locations[-1]
        return self.locations[self.current_location_index]

    def _get_cached_answer(self, label_text):
        bucket = self._current_answer_bucket()
        location_inputs = self.context_data["user_inputs"].get(bucket) or {}
        if label_text in location_inputs:
            return location_inputs[label_text]
        return None

    def _save_answer(self, label_text, answer):
        bucket = self._current_answer_bucket()
        if bucket not in self.context_data["user_inputs"]:
            self.context_data["user_inputs"][bucket] = {}
        self.context_data["user_inputs"][bucket][label_text] = answer
        self.update_config_file()
        engine = self.answer_engine
        if engine is not None:
            try:
                from answer_engine import normalize_label

                engine.context_data = self.context_data
                engine.user_inputs = self.context_data.get("user_inputs") or {}
                norm = normalize_label(label_text)
                updated = False
                for i, (q, _a) in enumerate(engine.pairs):
                    if q.lower() == norm.lower():
                        engine.pairs[i] = (q, answer)
                        updated = True
                        break
                if not updated and norm:
                    engine.pairs.append((norm, answer))
            except Exception as e:
                self.log_info(f"Could not update AI memory after save: {e}")

    def resolve_answer(self, label_text, field_type, options=None):
        """Resolve an answer via cache, AI suggestion + confirm, or manual input."""
        cached = self._get_cached_answer(label_text)
        if cached is not None:
            return cached

        if field_type == "file":
            return self._resolve_file_answer(label_text)

        engine = self._get_answer_engine()
        if engine is None:
            return self._manual_prompt(label_text, field_type, options)

        try:
            suggestion = engine.suggest(
                label_text,
                field_type=field_type,
                options=options,
                location=self._current_answer_bucket(),
            )
        except Exception as e:
            self.log_info(f"AI suggestion failed: {e}")
            return self._manual_prompt(label_text, field_type, options)

        if suggestion.answer is None or suggestion.source == "none":
            return self._manual_prompt(label_text, field_type, options)

        print(f"\nQuestion: {label_text}")
        if options:
            print(f"Options: {options}")
        print(f"Suggested ({suggestion.source}, {suggestion.confidence}): {suggestion.answer}")
        choice = input("[Y]es accept / [e]dit / [m]anual: ").strip().lower()

        if choice in ("", "y", "yes"):
            answer = suggestion.answer
            self._save_answer(label_text, answer)
            return answer

        if choice in ("e", "edit"):
            edited = input(f"Edit answer [{suggestion.answer}]: ").strip()
            answer = edited if edited else suggestion.answer
            if field_type == "checkbox":
                answer = str(answer).strip().lower() in ("yes", "y", "true", "1")
            self._save_answer(label_text, answer)
            return answer

        return self._manual_prompt(label_text, field_type, options)

    def _gather_application_text(self, label_text=""):
        """Override in subclasses to include platform-specific page text."""
        return label_text or ""

    def _resolve_file_answer(self, label_text):
        """Attach EN/DE resume based on application language; default English."""
        label_l = (label_text or "").lower()
        is_cover = any(k in label_l for k in ("cover letter", "anschreiben", "motivation"))
        is_resume = any(
            key in label_l for key in ("resume", "cv", "curriculum", "lebenslauf")
        ) or (
            not is_cover
            and any(k in label_l for k in ("upload", "attach", "document"))
        )

        if is_resume and not is_cover:
            app_text = self._gather_application_text(label_text)
            lang = detect_application_language(app_text, label_text)
            resume_path = resolve_resume_path(self.context_data, lang)
            if resume_path:
                self.log_info(f"Attaching {lang.upper()} resume: {resume_path}")
                print(f"\nFile field: {label_text}")
                print(f"Detected application language: {lang} -> {resume_path}")
                choice = input("[Y]es use this CV / [e]dit path / [m]anual: ").strip().lower()
                if choice in ("", "y", "yes"):
                    self._save_answer(label_text, resume_path)
                    return resume_path
                if choice in ("e", "edit"):
                    edited = input(f"File path [{resume_path}]: ").strip() or resume_path
                    self._save_answer(label_text, edited)
                    return edited
        return self._manual_prompt(label_text, "file")

    def _manual_prompt(self, label_text, field_type, options=None):
        if field_type == "checkbox":
            while True:
                user_input = input(
                    f"Do you want to check the box for '{label_text}'? (yes/no): "
                ).strip().lower()
                if user_input in ("yes", "no"):
                    response = user_input == "yes"
                    self._save_answer(label_text, response)
                    return response
        elif field_type in ("radio", "select") and options:
            while True:
                print(f"Please select an option for '{label_text}':")
                for i, option in enumerate(options):
                    print(f"{i + 1}. {option}")
                user_input = input("Enter the number of your choice: ").strip()
                if user_input.isdigit() and 1 <= int(user_input) <= len(options):
                    response = options[int(user_input) - 1]
                    self._save_answer(label_text, response)
                    return response
                print("Invalid input, please try again.")
        elif field_type == "file":
            user_input = input(f"Please provide the file location for '{label_text}': ")
            self._save_answer(label_text, user_input)
            return user_input
        else:
            user_input = input(f"Please provide the answer for '{label_text}': ")
            self._save_answer(label_text, user_input)
            return user_input

    def get_response_for_label(self, label_text):
        return self.resolve_answer(label_text, field_type="text")

    def get_radio_response_for_label(self, label_text, options):
        return self.resolve_answer(label_text, field_type="radio", options=options)

    def get_file_response_for_label(self, label_text):
        return self.resolve_answer(label_text, field_type="file")

    def get_checkbox_response_for_label(self, label_text):
        return self.resolve_answer(label_text, field_type="checkbox")

    def update_config_file(self):
        with open("config.json", "w") as config_file:
            json.dump(self.context_data, config_file, indent=4)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def init_logging(self):
        logging.basicConfig(level=logging.INFO)
        self.error_logger = logging.getLogger("ErrorLogger")
        self.applied_companies = self.load_json(self.APPLIED_COMPANIES_LOG_PATH)
        self.failed_applications = self.load_json(self.FAILED_APPLICATIONS_LOG_PATH)

    def load_json(self, path):
        if path.exists():
            try:
                with path.open("r") as file:
                    return json.load(file)
            except json.JSONDecodeError:
                self.log_error(f"Error decoding JSON from {path}")
                return {}
        return {}

    def save_json(self, path, data):
        with path.open("w") as file:
            json.dump(data, file, indent=4)

    def log_error(self, error_msg):
        self.error_logger.error(error_msg)
        errors = self.load_json(self.ERROR_LOG_PATH)
        errors[str(datetime.now())] = error_msg
        self.save_json(self.ERROR_LOG_PATH, errors)
        self.cleanup_error_log()

    def log_info(self, message):
        logging.info(message)

    def cleanup_error_log(self):
        errors = self.load_json(self.ERROR_LOG_PATH)
        cutoff = datetime.now() - timedelta(days=1)
        errors = {k: v for k, v in errors.items() if datetime.fromisoformat(k) > cutoff}
        self.save_json(self.ERROR_LOG_PATH, errors)

    def log_applied_company(self, company):
        if company:
            self.applied_companies[company] = str(datetime.now())
            self.save_json(self.APPLIED_COMPANIES_LOG_PATH, self.applied_companies)
            self.cleanup_applied_companies_log()

    def cleanup_applied_companies_log(self):
        cutoff = datetime.now() - timedelta(weeks=2)
        self.applied_companies = {
            k: v
            for k, v in self.applied_companies.items()
            if k and v and datetime.fromisoformat(v) > cutoff
        }
        self.save_json(self.APPLIED_COMPANIES_LOG_PATH, self.applied_companies)

    def log_failed_application(self, company):
        self.failed_applications[company] = str(datetime.now())
        self.save_json(self.FAILED_APPLICATIONS_LOG_PATH, self.failed_applications)
        self.cleanup_failed_applications_log()

    def cleanup_failed_applications_log(self):
        cutoff = datetime.now() - timedelta(weeks=2)
        self.failed_applications = {
            k: v
            for k, v in self.failed_applications.items()
            if datetime.fromisoformat(v) > cutoff
        }
        self.save_json(self.FAILED_APPLICATIONS_LOG_PATH, self.failed_applications)

    # ------------------------------------------------------------------
    # Selenium helpers
    # ------------------------------------------------------------------

    def find_element_with_retry(self, by, value, retries=3, delay=2):
        import time

        for _ in range(retries):
            try:
                return self.driver.find_element(by, value)
            except (NoSuchElementException, StaleElementReferenceException):
                time.sleep(delay)
        raise NoSuchElementException(f"Element not found: {by}, {value}")

    def handle_captcha(self):
        input("CAPTCHA detected. Please solve the CAPTCHA manually and then press Enter to continue...")

    def close_session(self):
        self.log_info("End of the session")
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            try:
                self.driver.quit()
            except Exception:
                pass
