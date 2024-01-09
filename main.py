from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
import time
import re
import json

class EasyApplyLinkedin:

    def __init__(self, data):
        """Parameter initialization"""

        self.email = data['email']
        self.password = data['password']
        self.keywords = data['keywords']
        self.location = data['location']
        self.driver = webdriver.Chrome(data["driver_path"])

    def login_linkedin(self):
        """This function logs into your personal LinkedIn profile"""

        # go to the LinkedIn login url
        self.driver.get("https://www.linkedin.com/login")

        # introduce email and password and hit enter
        login_email = self.driver.find_element('name', 'session_key')
        login_email.clear()
        login_email.send_keys(self.email)
        login_pass = self.driver.find_element('name', 'session_password')
        login_pass.clear()
        login_pass.send_keys(self.password)
        login_pass.send_keys(Keys.RETURN)
    
    def job_search(self):
        """This function goes to the 'Jobs' section a looks for all the jobs that matches the keywords and location"""

        # go to Jobs
        print("Search jobs by title and location.")
        jobs_link = self.driver.find_element(By.LINK_TEXT, 'Jobs')
        jobs_link.click()

        # search based on keywords and location and hit enter
        search_keywords = self.driver.find_element(By.XPATH, '//input[starts-with(@id, "jobs-search-box-keyword-id-ember")]')
        search_keywords.clear()
        search_keywords.send_keys(self.keywords)
        search_keywords.send_keys(Keys.RETURN)

        search_location = self.driver.find_element(By.XPATH, '//input[starts-with(@id, "jobs-search-box-location-id-ember")]')
        search_location.clear()
        search_location.send_keys(self.location)
        search_location.send_keys(Keys.RETURN)
        time.sleep(5)

        print("Filter the result by select jobs posted in the past 24 hours")
        date_posted_button = self.driver.find_element(By.XPATH,
                                                 '//button[starts-with(@aria-label, "Date posted filter.")][@type="button"]')

        date_posted_button.click()
        time.sleep(1)

        past24h_radiobutton = self.driver.find_element(By.XPATH, "//span[text()='Past 24 hours']")
        past24h_radiobutton.click()
        time.sleep(1)

        show_results_button = self.driver.find_element(By.XPATH,
                                                  "//span[contains(normalize-space(), 'Show') and contains(normalize-space(), 'results')]")
        show_results_button.click()
        time.sleep(1)

        # collect all job urls on this page


    def filter(self):
        """This function filters all the job results by 'Date Posted' = Past 24 hours """

        print("Filter the result by select jobs posted in the past 24 hours")
        date_posted_button = self.driver.find_element(By.XPATH,
                                                 '//button[starts-with(@aria-label, "Date posted filter.")][@type="button"]')

        date_posted_button.click()
        time.sleep(1)

        past24h_radiobutton = self.driver.find_element(By.XPATH, "//span[text()='Past 24 hours']")
        past24h_radiobutton.click()
        time.sleep(1)

        show_results_button = self.driver.find_element(By.XPATH,
                                                  "//span[contains(normalize-space(), 'Show') and contains(normalize-space(), 'results')]")
        show_results_button.click()
        time.sleep(1)

    def find_offers(self):
        from collections import OrderedDict
        from bs4 import BeautifulSoup

        """This function finds all the offers through all the pages result of the search and filter"""

        # How to get all page buttons?
        page_buttons = self.driver.find_elements(By.XPATH, '//button[starts-with(@aria-label, "Page ")][@type="button"]')
        page_buttons[0].click()
        self.driver.get(self.driver.current_url)

        # Loop through each element
        for button in page_buttons:
            # Perform actions on each element
            print("Button text:", button.text)
            # button.click()  # or perform any other actions

        # how to get all job links in the current page?
        job_links = OrderedDict()  # {link: element}
        for i in range(10):
            all_links = self.driver.find_elements(By.XPATH, "//a")
            for a in all_links:
                if str(a.get_attribute('href')).startswith("https://www.linkedin.com/jobs/view"):
                    simple_link = a.get_attribute('href').split('?')[0]
                    if simple_link not in job_links:
                        job_links[simple_link] = a
            # scroll down for each job element
            self.driver.execute_script("arguments[0].scrollIntoView();", a)
            time.sleep(0.5)

        # How to get tile, location, and description from a href?
        job_element = job_links['https://www.linkedin.com/jobs/view/3800277563/']
        job_element.click()
        time.sleep(2)

        # Find the general information of the job offers
        self.driver.page_source
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')

        job_postings = soup.find_all('li', {'class': 'jobs-search-results__list-item'})

        # Extract relevant information from each job posting and store it in a list of dictionaries
        data = []
        for job_posting in job_postings[:3]:
            try:
                job_title = job_posting.find('a', class_='job-card-list__title').get_text().strip()
            except AttributeError:
                job_title = None

            try:
                company_name = job_posting.find('a', class_='job-card-container__link').get_text().strip()
            except AttributeError:
                company_name = None

            try:
                location = job_posting.find('li', class_='job-card-container__metadata-item').get_text().strip()
            except AttributeError:
                location = None

            job_description_element = job_posting.find('div', class_='jobs-description-content__text')

            # job_description_element = self.driver.find_element(By.XPATH, "//div[text()='About the job']")
            #
            # contains(normalize - space(), 'Show')
            "About the job"
            # Extract the text content of the job description element
            job_description = job_description_element.get_text(
                strip=True) if job_description_element else "Job description not found."
            print(job_description)

            time.sleep(0.5)

            data.append({
                'Job Title': job_title,
                'Company Name': company_name,
                'Location': location,
                'Description': job_description
            })

    def close_session(self):
        """This function closes the actual session"""
        
        print('End of the session, see you later!')
        self.driver.close()

    def apply(self):
        """Apply to job offers"""

        self.driver.maximize_window()
        self.login_linkedin()
        time.sleep(5)
        self.job_search()
        time.sleep(2)
        self.filter()
        time.sleep(2)
        self.find_offers()
        time.sleep(2)
        self.close_session()


if __name__ == '__main__':
    with open('data/config.json') as config_file:
        data = json.load(config_file)

    bot = EasyApplyLinkedin(data)
    bot.apply()
