import unittest
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import NoSuchElementException

from main import EasyApplyLinkedin


class TestEasyApplyLinkedin(unittest.TestCase):
    def setUp(self):
        self.data = {
            "email": "test@example.com",
            "password": "secret",
            "keywords": ["TypeScript", "Angular", "React"],
            "keywordsToAvoid": ["C++", ".NET"],
            "locations": ["Switzerland", "Belgium"],
            "driver_path": "/usr/local/bin/geckodriver",
            "sortBy": "R",
            "filters": {
                "easy_apply": True,
                "experience": [],
                "jobType": ["Full-time", "Contract"],
                "timePostedRange": [],
                "workplaceType": ["Remote", "Hybrid"],
                "less_than_10_applicants": False,
            },
            "aiSettings": {"enabled": False},
            "user_inputs": {},
        }
        with patch("base_easy_apply.webdriver.Firefox"):
            with patch("base_easy_apply.FirefoxService"):
                self.bot = EasyApplyLinkedin(self.data)
        self.bot.driver = MagicMock()

    def test_login_linkedin(self):
        self.bot.driver.find_element.return_value = MagicMock()
        with patch("main.WebDriverWait") as mock_wait:
            mock_wait.return_value.until.return_value = MagicMock()
            self.bot.login_linkedin()
        self.bot.driver.get.assert_called_with("https://www.linkedin.com/login")
        self.assertTrue(self.bot.driver.find_element.called)

    def test_construct_url(self):
        url = self.bot.construct_url()
        self.assertIn("TypeScript", url)
        self.assertIn("Angular", url)
        self.assertIn("React", url)
        self.assertIn("geoId=106693272", url)
        self.assertIn("f_AL=true", url)

    def test_apply_filters_and_search_no_results(self):
        with patch.object(self.bot, "check_no_results", return_value=True), patch(
            "main.time.sleep"
        ):
            self.bot.apply_filters_and_search()
        self.assertEqual(self.bot.current_location_index, 2)

    def test_log_error(self):
        self.bot.log_error("Test error")
        errors = self.bot.load_json(self.bot.ERROR_LOG_PATH)
        self.assertTrue(any("Test error" in v for v in errors.values()))


if __name__ == "__main__":
    unittest.main()
