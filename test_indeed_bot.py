"""Unit tests for Indeed Easy Apply bot helpers (no live browser)."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from indeed_bot import EasyApplyIndeed


SAMPLE_CONFIG = {
    "email": "test@example.com",
    "password": "secret",
    "keywords": ["TypeScript", "React"],
    "keywordsToAvoid": ["Java"],
    "locations": ["Switzerland"],
    "driver_path": "/usr/local/bin/geckodriver",
    "sortBy": "R",
    "filters": {},
    "aiSettings": {"enabled": False},
    "user_inputs": {},
    "resumes": {
        "en": str(Path("resumes/Resume_Gabriel_Clemente.pdf").resolve()),
        "de": str(Path("resumes/Lebenslauf_Gabriel_Clemente.pdf").resolve()),
        "default": "en",
    },
    "indeed": {
        "enabled": True,
        "baseUrl": "https://ch.indeed.com",
        "locations": ["Zurich", "Zug"],
        "filters": {
            "easyApplyOnly": True,
            "fromage": 7,
            "remotejob": True,
        },
    },
}


class TestIndeedUrlBuilder(unittest.TestCase):
    def setUp(self):
        with patch("base_easy_apply.webdriver.Firefox"):
            with patch("base_easy_apply.FirefoxService"):
                self.bot = EasyApplyIndeed(SAMPLE_CONFIG)

    def test_construct_url_includes_iafilter_and_location(self):
        url = self.bot.construct_url(start=0)
        self.assertIn("ch.indeed.com/jobs?", url)
        self.assertIn("iafilter=1", url)
        self.assertIn("l=Zurich", url)
        self.assertIn("fromage=7", url)
        self.assertIn("remotejob=1", url)
        self.assertIn("TypeScript", url)

    def test_construct_url_pagination(self):
        url = self.bot.construct_url(start=20)
        self.assertIn("start=20", url)

    def test_answer_bucket(self):
        self.assertEqual(self.bot._current_answer_bucket(), "Indeed:Zurich")
        self.bot.current_location_index = 1
        self.assertEqual(self.bot._current_answer_bucket(), "Indeed:Zug")


class TestIndeedSelectorsJson(unittest.TestCase):
    def setUp(self):
        path = Path("indeed_selectors.json")
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def test_version_and_apply_with_indeed(self):
        self.assertGreaterEqual(self.data.get("version", 0), 2)
        texts = self.data["apply"]["applyButtonTexts"]
        self.assertIn("Apply with Indeed", texts)

    def test_continue_prefers_data_testid(self):
        cont = self.data["apply"]["continueButton"]
        self.assertEqual(cont[0], "button[data-testid='continue-button']")

    def test_apply_button_prefers_indeedApplyButton(self):
        btns = self.data["apply"]["applyButton"]
        self.assertEqual(btns[0], "#indeedApplyButton")

    def test_resume_selectors_present(self):
        resume = self.data["apply"]["resume"]
        self.assertIn("form[data-testid='resume-selection-form']", resume["form"])
        self.assertTrue(
            any("resume-selection-file-resume-radio-card-file-input" in s for s in resume["fileInput"])
        )

    def test_search_form_inputs(self):
        form = self.data["search"]["searchForm"]
        self.assertIn("#text-input-what", form["whatInput"])
        self.assertIn("#text-input-where", form["whereInput"])


class TestIndeedHelpers(unittest.TestCase):
    def setUp(self):
        with patch("base_easy_apply.webdriver.Firefox"):
            with patch("base_easy_apply.FirefoxService"):
                self.bot = EasyApplyIndeed(SAMPLE_CONFIG)
        self.bot.driver = MagicMock()

    def test_card_has_easily_apply_german(self):
        card = MagicMock()
        card.text = "Software Engineer\nFirma AG\nEinfach bewerben"
        self.assertTrue(self.bot._card_has_easily_apply(card))

    def test_card_has_easily_apply_english(self):
        card = MagicMock()
        card.text = "Software Engineer\nFirma AG\nEasily apply"
        self.assertTrue(self.bot._card_has_easily_apply(card))

    def test_card_missing_badge(self):
        card = MagicMock()
        card.text = "Software Engineer\nFirma AG\nAuf Unternehmenswebsite bewerben"
        self.assertFalse(self.bot._card_has_easily_apply(card))

    def test_is_indeed_apply_from_widget(self):
        widget = MagicMock()
        widget.is_displayed.return_value = True
        self.bot.driver.find_element.return_value = widget
        self.bot.driver.page_source = "<html></html>"
        self.bot.driver.current_url = "https://ch.indeed.com/viewjob?jk=abc"
        self.assertTrue(self.bot.is_indeed_apply())

    def test_is_indeed_apply_from_page_source(self):
        self.bot.driver.find_element.side_effect = Exception("missing")
        self.bot.driver.page_source = "<button id='indeedApplyButton'>Apply with Indeed</button>"
        self.bot.driver.current_url = "https://ch.indeed.com/viewjob?jk=abc"
        self.assertTrue(self.bot.is_indeed_apply())

    def test_is_indeed_apply_external_false(self):
        self.bot.driver.page_source = "<html>greenhouse apply</html>"
        self.bot.driver.current_url = "https://boards.greenhouse.io/foo"
        self.bot.driver.find_element.side_effect = Exception("missing")
        self.bot.driver.find_elements.return_value = []
        self.assertFalse(self.bot.is_indeed_apply())

    def test_find_button_by_texts(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Weiter"
        btn.get_attribute.side_effect = lambda k: "" if k != "aria-label" else ""
        self.bot.driver.find_elements.return_value = [btn]
        found = self.bot._find_button_by_texts(["Continue", "Weiter"])
        self.assertIs(found, btn)

    def test_close_application_switches_tab(self):
        self.bot.search_window = "search"
        self.bot.driver.window_handles = ["search", "apply"]
        self.bot.driver.current_window_handle = "apply"
        self.bot.driver.find_element.side_effect = Exception("no exit")
        self.bot.close_application()
        self.bot.driver.close.assert_called()
        self.bot.driver.switch_to.window.assert_called_with("search")

    def test_resume_selection_uses_existing_matching_pdf(self):
        form = MagicMock()
        label = MagicMock()
        label.text = "Resume_Gabriel_Clemente.pdf"
        radio = MagicMock()
        radio.is_selected.return_value = True

        def find_element(by, sel):
            if "resume-selection-form" in sel:
                return form
            if "radio-card-label" in sel:
                return label
            if "radio-card-input" in sel:
                return radio
            raise Exception(sel)

        self.bot.driver.find_element.side_effect = find_element
        with patch.object(
            self.bot,
            "_desired_resume_path",
            return_value="/tmp/Resume_Gabriel_Clemente.pdf",
        ):
            handled = self.bot._handle_resume_selection_step()
        self.assertTrue(handled)

    def test_resume_selection_uploads_when_wrong_language_on_profile(self):
        form = MagicMock()
        label = MagicMock()
        label.text = "Lebenslauf_Gabriel_Clemente.pdf"
        file_input = MagicMock()

        def find_element(by, sel):
            if "resume-selection-form" in sel:
                return form
            if "radio-card-label" in sel:
                return label
            raise Exception(sel)

        self.bot.driver.find_element.side_effect = find_element
        with patch.object(
            self.bot,
            "_desired_resume_path",
            return_value="/tmp/Resume_Gabriel_Clemente.pdf",
        ), patch.object(
            self.bot,
            "_configured_resume_names",
            return_value=[
                "Resume_Gabriel_Clemente.pdf",
                "Lebenslauf_Gabriel_Clemente.pdf",
            ],
        ), patch.object(
            self.bot,
            "_find_first_any",
            return_value=file_input,
        ):
            handled = self.bot._handle_resume_selection_step()
        self.assertTrue(handled)
        file_input.send_keys.assert_called_once_with("/tmp/Resume_Gabriel_Clemente.pdf")

    def test_card_job_key(self):
        card = MagicMock()
        card.get_attribute.return_value = "abc123"
        self.assertEqual(self.bot._card_job_key(card), "abc123")


if __name__ == "__main__":
    unittest.main()
