#!/usr/bin/env python
import json
import logging
import os
import time
from collections import OrderedDict, deque
from datetime import datetime
from os import path, makedirs
from random import randint

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class SearchJobs:

    def __init__(self, keywords, location, time_str, driver_path=None):
        """
        Initialize a SearchJobs instance
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

    @property
    def out_file(self):
        """ Output data file """
        if len(self.location.split(' ')) == 1:
            location = self.location.lower()
        else:
            location = ''.join([word[0].lower() for word in self.location.split(' ')])
        return path.join('data', self.time_str + f'_{location}_{self.job_type}.csv')

    @property
    def job_type(self):
        """ first letter of each keywords"""
        return ''.join([word[0].lower() for word in self.keywords.split(' ')])

    def init_webdriver(self):
        """
        Initialize a Chrome webdriver.
        """
        logging.info(f"Initialize a Chrome driver.")
        if self.driver_path:
            self.driver = webdriver.Chrome(self.driver_path)
        else:
            self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)  # seconds
        time.sleep(0.5)
        self.driver.maximize_window()
        time.sleep(0.5)

    def get_credentials(self):
        """ Load login account and password from a local file """
        logging.info(f"Load a configuration file for job search.")
        with open('data/config.json', 'r') as config_file:
            data = json.load(config_file)
        self.email = data['email']
        self.password = data['password']

    def login(self):
        pass

    def search_jobs(self):
        pass

    def filter(self):
        """ Filter jobs by post date/time """
        pass

    def find_page_jobs(self):
        """ Find all jobs on a single page """
        pass

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
            time.sleep(randint(1, 2) * 0.5)

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
            try:
                page_button = self.driver.find_element(By.XPATH, f'//button[@aria-label="Page {page_num}"]')
                page_button.click()
                time.sleep(randint(3, 6))
            except Exception:
                logging.info(f"Unable to locate element - Page {page_num}.")
                time.sleep(randint(1, 2))
                if page_num > 1:
                    # when there is only one page of jobs, there is not a page_button element
                    break

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

            page_num += 1
            if page_num > 40:
                logging.info(f"Exit as finished {page_num} job pages.")
                break

    def save_results(self, data):
        """
        Find interested jobs from job data and save it to a local csv file
        :return:
        """
        df = pd.DataFrame(data)
        if not path.exists(self.out_file):
            logging.info(f"Save all jobs on this page to {self.out_file}")
            df.to_csv(self.out_file, index=True)
        else:
            logging.info(f"Append all jobs on this page to {self.out_file}")
            df.to_csv(self.out_file, mode='a', index=True, header=False)

    def close_session(self):
        """This function closes the actual session"""
        logging.info('Close this session!')
        self.driver.close()
        time.sleep(1)

    def run(self):
        """ Search jobs and save results """
        pass


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
