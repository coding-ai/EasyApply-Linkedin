#!/usr/bin/env python
import json
import time
from collections import OrderedDict, deque
from datetime import datetime
from os import path, makedirs
from random import randint
import logging

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class SearchLinkedin:

    def __init__(self, config):
        """Parameter initialization"""
        self.email = config['email']
        self.password = config['password']
        self.keywords = config['keywords']
        self.location = config['location']
        self.driver_path = config["driver_path"]

        self.driver = None
        self.job_data = {'Link': [], 'Title': [], 'Company': [], 'Location': [], 'Description': []}

    def init_webdriver(self):
        """
        Initialize a Chrome webdriver.
        """
        logging.info(f"Initialize a Chrome driver.")
        self.driver = webdriver.Chrome(self.driver_path)
        self.driver.implicitly_wait(10)  # seconds
        time.sleep(0.5)
        self.driver.maximize_window()
        time.sleep(0.5)

    def login_linkedin(self):
        """This function logs into your personal LinkedIn profile"""

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
    
    def job_search(self):
        """This function goes to the 'Jobs' section a looks for all the jobs that matches the keywords and location"""

        # go to Jobs
        logging.info("Search jobs by title and location.")
        jobs_link = self.driver.find_element(By.LINK_TEXT, 'Jobs')
        jobs_link.click()
        time.sleep(randint(3, 6))

        tries = 1
        while tries < 10:
            try:
                # search based on keywords and location and hit enter
                if tries > 1:
                    logging.info(f"Number of trials for searching jobs: {tries}. ")
                logging.info(f"Search {self.keywords} at {self.location}")
                search_keywords = self.driver.find_element(By.XPATH, '//input[starts-with(@id, "jobs-search-box-keyword-id-ember")]')
                search_keywords.clear()
                search_keywords.click()
                time.sleep(randint(1, 2) * 0.5)
                search_keywords.send_keys(self.keywords)
                time.sleep(randint(3, 6))
                search_keywords.send_keys(Keys.RETURN)
                time.sleep(randint(3, 6))

                search_location = self.driver.find_element(By.XPATH, '//input[starts-with(@id, "jobs-search-box-location-id-ember")]')
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
        tries = 1
        while tries < 10:
            try:
                date_posted_button = self.driver.find_element(By.XPATH,'//button[starts-with(@aria-label, "Date posted filter.")][@type="button"]')
                date_posted_button.click()
                time.sleep(randint(2, 5))

                past24h_radiobutton = self.driver.find_element(By.XPATH, "//span[text()='Past 24 hours']")
                past24h_radiobutton.click()
                time.sleep(randint(2, 5))

                show_results_button = self.driver.find_element(By.XPATH,"//span[contains(normalize-space(), 'Show') and contains(normalize-space(), 'results')]")
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
        link_elements = self.driver.find_elements(By.XPATH, "//a")
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

                # scroll to this job element and find all link elements
                self.driver.execute_script("arguments[0].scrollIntoView();", job_element)
                time.sleep(1)
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
            logging.info(f"Scrape link {i+1} / {len(job_links)}: {link}")
            job_element.click()
            time.sleep(randint(2, 5))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            time.sleep(randint(2, 5))

            try:
                job_title = soup.find('span',{'class': 'job-details-jobs-unified-top-card__job-title-link'}).get_text(strip=True).strip()
                details = soup.find('div',{'class': 'job-details-jobs-unified-top-card__primary-description-without-tagline'}).get_text().strip()
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

    def find_jobs(self):
        """This function finds all the jobs through all the pages result of the search and filter"""
        # Collect all jobs for each page
        page_num = 1
        while True:
            logging.info(f"Processing page {page_num}")
            try:
                page_button = self.driver.find_element(By.XPATH, f'//button[@aria-label="Page {page_num}"]')
            except Exception as e:
                logging.error(str(e))
                time.sleep(randint(3, 6))
                break
            page_button.click()
            time.sleep(randint(3, 6))

            # logging.info("Find all job links on the current page.")
            # job_links = self.find_page_jobs()
            #
            # logging.info("Extract job title, company, location and description.")
            # data = self.extract_data(job_links)
            # self.job_data['Link'].extend(data['Link'])
            # self.job_data['Title'].extend(data['Title'])
            # self.job_data['Company'].extend(data['Company'])
            # self.job_data['Location'].extend(data['Location'])
            # self.job_data['Description'].extend(data['Description'])

            page_num += 1
            if page_num > 2:
                logging.info(f"Finished {page_num} job pages. Exit.")
                break

    def save_results(self):
        """
        Find interested jobs from job data and save it to a local csv file
        :return:
        """
        job_df = pd.DataFrame(self.job_data)
        out_file = path.join('data', datetime.today().date().strftime('%Y-%m-%d') + '_all.csv')
        logging.info(f"Save all jobs to {out_file}")
        job_df.to_csv(out_file, index=True)

    def close_session(self):
        """This function closes the actual session"""
        logging.info('End of the session, see you later!')
        self.driver.close()

    def run(self):
        """Apply to job offers"""
        self.init_webdriver()
        self.login_linkedin()
        self.job_search()
        self.filter()
        self.find_jobs()
        self.save_results()
        self.close_session()


def config_log(log_file, level=logging.INFO) -> None:
    """
    Configure a log file.
    @param log_file: path to a log file
    @param level: choices can be logging.DEBUG, logging.INFO, ...
    """
    log_dir = path.dirname(log_file)
    if not path.exists(log_dir):
        makedirs(log_dir)

    # Remove all handlers from the root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        logging.root.removeHandler(handler)

    # Create a new log file
    str_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(filename=log_file, level=level, format=str_format)

    # Define a Handler which writes messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(str_format, "%Y-%m-%d %H:%M:%S"))
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


def is_geoai_job(description):
    """
    Check if a job is a Geo AI job
    The description contains
    (1) any of ['remote sensing', 'satellite', 'earth', 'climate']
    (2) any of ['deep learning', 'pytorch', 'tensorflow']
    :param description:
    :return:
    """
    return True


if __name__ == '__main__':

    # configure a log file
    config_log(path.join('data', 'logs', datetime.today().date().strftime('%Y-%m-%d') + '.log'))

    logging.info(f"Load a configuration file for job search.")
    with open('data/config.json') as config_file:
        config = json.load(config_file)

    bot = SearchLinkedin(config)
    bot.run()
    logging.info("All done!")
