import pytest
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from main import EasyApplyLinkedin

@pytest.fixture
def setup_browser():
    service = FirefoxService(executable_path="/usr/local/bin/geckodriver")
    driver = webdriver.Firefox(service=service)
    yield driver
    driver.quit()

@pytest.fixture
def setup_bot(setup_browser):
    data = {
        "email": "sendmessage@gabo.email",
        "password": "***,****,****",
        "keywords": [
            "TypeScript",
            "Angular",
            "React",
            "React Native",
            "Node",
            "JavaScript",
            "Frontend Engineer",
            "Full-Stack Engineer",
            "Backend Engineer"
        ],
        "keywordsToAvoid": [
            "C++",
            ".NET",
            "Analyst",
            "PHP",
            "Python",
            "C",
            "Java",
            "Go",
            "Rust",
            "Kotlin",
            "Swift",
            "Objective-C",
            "Rust",
            "Kotlin",
            "Swift",
            "C#",
            ".Net",
            ".net",
            "Robotic",
            "Data",
            "Science",
            "Cloud",
            "Robotics",
            "AI",
            "ML",
            "DL",
            "NLP",
            "CV",
            "DevOps",
            "Solidity"
        ],
        "locations": [
            "Canada",
            "Portugal",
            "Switzerland",
            "Belgium",
            "Netherlands",
            "DACH",
            "Benelux",
            "European Union",
            "European Economic Area",
            "Germany",
            "Spain",
            "United States",
            "United Kingdom"
        ],
        "driver_path": "/usr/local/bin/geckodriver",
        "sortBy": "R",
        "filters": {
            "easy_apply": True,
            "experience": [],
            "jobType": [
                "Full-time",
                "Contract"
            ],
            "timePostedRange": [],
            "workplaceType": [
                "Remote",
                "Hybrid"
            ],
            "less_than_10_applicants": False
        }
    }
    bot = EasyApplyLinkedin(data)
    bot.driver = setup_browser
    return bot

def test_login_linkedin(setup_bot):
    setup_bot.login_linkedin()
    assert "feed" in setup_bot.driver.current_url

def test_job_search(setup_bot):
    setup_bot.login_linkedin()
    setup_bot.job_search()
    assert "jobs/search" in setup_bot.driver.current_url

def test_find_offers(setup_bot):
    setup_bot.login_linkedin()
    setup_bot.job_search()
    setup_bot.find_offers()
    assert len(setup_bot.applied_companies) > 0

if __name__ == "__main__":
    pytest.main()
