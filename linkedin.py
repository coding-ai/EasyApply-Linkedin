#!/usr/bin/env python
import json
import logging
import time
from collections import OrderedDict, deque
from random import randint

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from base_search import SearchJobs


class SearchLinkedin(SearchJobs):

    def __init__(self, keywords, location, time_str, driver_path=None):
        """
        Initialize a SearchLinkedin
        :param keywords: job title
        :param location: job location
        :param time_str: use a time string to name output files and log files
        :param driver_path: web driver path. No need to specify the driver_path if it is added to the system env.
        """
        self.keywords = keywords
        self.location = location
        self.time_str = time_str

        self.email = None
        self.password = None
        self.driver_path = driver_path
        self.driver = None

    def get_credentials(self):
        """ Load login account and password from a local file """
        logging.info(f"Load a configuration file for job search.")
        with open('data/config.json', 'r') as config_file:
            data = json.load(config_file)
        self.email = data['email']
        self.password = data['password']

    def login(self):
        """This function logs into your personal LinkedIn profile"""
        self.get_credentials()

        logging.info(f"Go to the LinkedIn login url: https://www.linkedin.com/login.")
        self.driver.get("https://www.linkedin.com/login")

        # introduce email and password and hit enter
        logging.info(f"Fill email and password and hit enter.")
        login_email = self.driver.find_element('name', 'session_key')
        login_email.clear()
        login_email.send_keys(self.email)
        login_pass = self.driver.find_element('name', 'session_password')
        login_pass.clear()
        login_pass.send_keys(self.password)
        login_pass.send_keys(Keys.RETURN)
        time.sleep(randint(2, 4))

    def search_jobs(self):
        """This function goes to the 'Jobs' section a looks for all the jobs that matches the keywords and location"""

        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                # search based on keywords and location and hit enter
                if tries > 1:
                    logging.info(f"Number of trials for searching jobs: {tries}. ")

                # go to Jobs
                logging.info("Search jobs by title and location.")
                jobs_link = self.driver.find_element(By.LINK_TEXT, 'Jobs')
                jobs_link.click()
                time.sleep(randint(3, 6))

                logging.info(f"Search {self.keywords} at {self.location}")
                search_keywords = self.driver.find_element(By.XPATH,
                                                           '//input[starts-with(@id, "jobs-search-box-keyword-id-ember")]')
                search_keywords.clear()
                search_keywords.click()
                time.sleep(randint(1, 2) * 0.5)
                search_keywords.send_keys(self.keywords)
                time.sleep(randint(3, 6))
                search_keywords.send_keys(Keys.RETURN)
                time.sleep(randint(3, 6))

                search_location = self.driver.find_element(By.XPATH,
                                                           '//input[starts-with(@id, "jobs-search-box-location-id-ember")]')
                search_location.clear()
                search_location.click()
                time.sleep(randint(1, 2) * 0.5)
                search_location.send_keys(self.location)
                time.sleep(randint(3, 6))
                search_location.send_keys(Keys.RETURN)
                time.sleep(randint(5, 8))
                logging.info("Job search is done!")
                break
            except Exception as e:
                logging.error(str(e))
                time.sleep(randint(3, 6))
            tries += 1

    def filter(self):
        """This function filters all the job results by 'Date Posted' = Past 24 hours """

        logging.info("Select jobs posted in the past 24 hours")
        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                date_posted_button = self.driver.find_element(By.XPATH,
                                                              '//button[starts-with(@aria-label, "Date posted filter.")][@type="button"]')
                date_posted_button.click()
                time.sleep(randint(2, 5))

                past24h_radiobutton = self.driver.find_element(By.XPATH, "//span[text()='Past 24 hours']")
                past24h_radiobutton.click()
                time.sleep(randint(2, 5))

                show_results_button = self.driver.find_element(By.XPATH,
                                                               "//span[contains(normalize-space(), 'Show') and contains(normalize-space(), 'results')]")
                show_results_button.click()
                time.sleep(randint(4, 8))
                logging.info("Job filtering is done!")
                break
            except Exception as e:
                logging.error(str(e))
                time.sleep(randint(3, 6))
            tries += 1

    def find_page_jobs(self):
        """
        Find all jobs on a single page by treating it as a graph - BFS (breadth-first-search) traversal problem.
        :return:
            result_jobs: all jobs on this page in a dict {"link": job_element, }
        """

        def is_job_link(link_element):
            # check if a link element is a job link or not
            if str(link_element.get_attribute('href')).startswith("https://www.linkedin.com/jobs/view"):
                return True
            return False

        def get_href_link(job_element):
            # return link of a job element.
            return job_element.get_attribute('href').split('?')[0]

        result_jobs = OrderedDict()  # all jobs: {link: element}
        link_elements = self.driver.find_elements(By.XPATH, "//div/a")
        q_elements = deque([a for a in link_elements if is_job_link(a)])
        q_links = deque([get_href_link(a) for a in q_elements])
        while len(q_elements):
            sz = len(q_elements)
            for i in range(sz):
                job_element = q_elements.popleft()
                job_link = q_links.popleft()
                if job_link in result_jobs:
                    continue
                # add the link to the results
                result_jobs[job_link] = job_element

                # scroll to this job element and find all link elements. Scroll one time for every 3 elements.
                if i % 3 != 2:
                    continue
                self.driver.execute_script("arguments[0].scrollIntoView();", job_element)
                # if the following time is too short, e.g. 0.1s, a lot of jobs can be missed.
                time.sleep(randint(1, 3))
                new_link_elements = self.driver.find_elements(By.XPATH, "//a")

                # add new jobs which are not in the queue or in the result to the queue
                for new_link_element in new_link_elements:
                    if not is_job_link(new_link_element):
                        continue
                    new_job_link = get_href_link(new_link_element)
                    if (new_job_link not in q_links) and (new_job_link not in result_jobs):
                        q_elements.append(new_link_element)
                        q_links.append(new_job_link)
        return result_jobs

    def extract_data(self, job_links):
        """
        Extract information from a job link
        :param job_links:
        :return:
        """
        # Extract relevant information from each job posting and store it in a list of dictionaries
        data = {'Link': [], 'Title': [], 'Company': [], 'Location': [], 'Description': []}
        for i, (link, job_element) in enumerate(job_links.items()):
            logging.info(f"Scrape link {i + 1} / {len(job_links)}: {link}")
            job_element.click()
            time.sleep(randint(1, 3))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            try:
                job_title = soup.find('span', {'class': 'job-details-jobs-unified-top-card__job-title-link'}).get_text(
                    strip=True).strip()
                details = soup.find('div', {
                    'class': 'job-details-jobs-unified-top-card__primary-description-without-tagline'}).get_text().strip()
                company_name, location = details.split('·')[:2]

                job_desc = soup.find('div', class_='jobs-description-content__text')
                if job_desc:
                    description = job_desc.get_text(strip=True)
                    n_chars = len("About the job")
                    if len(description) > n_chars and description[:n_chars] == "About the job":
                        description = description[n_chars:]
                else:
                    description = "Job description not found."

                data['Link'].append(link)
                data['Title'].append(job_title)
                data['Company'].append(company_name)
                data['Location'].append(location)
                data['Description'].append(description)
            except Exception as e:
                logging.error(str(e))
        return data

    def scrape_jobs(self):
        """ Scrape/Crawl all jobs and save the jobs to a table file"""
        # Collect all jobs for each page

        page_num = 1
        while True:
            logging.info(f"Processing page {page_num}")
            if page_num > 1:
                tries, max_tries = 1, 5
                while tries < max_tries:
                    try:
                        page_button = self.driver.find_element(By.XPATH, f'//button[@aria-label="Page {page_num}"]')
                        page_button.click()
                        time.sleep(randint(3, 6))
                        break
                    except Exception:
                        logging.info(f"Unable to locate element - Page {page_num}.")
                        time.sleep(randint(1, 2))
                    tries += 1

            # find_page_jobs may crash somehow, retry it for at most 5 times.
            tries, max_tries = 1, 5
            while tries < max_tries:
                try:
                    logging.info(f"Find all job links on Page {page_num}.")
                    job_links = self.find_page_jobs()
                    logging.info("Extract job title, company, location and description.")
                    data = self.extract_data(job_links)
                    self.save_results(data)
                    break
                except Exception as e:
                    logging.error(str(e))
                    time.sleep(randint(3, 6))
                tries += 1

            page_num += 1
            if page_num > 40:
                logging.info(f"Exit as finished {page_num} job pages.")
                break
