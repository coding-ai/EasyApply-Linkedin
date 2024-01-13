#!/usr/bin/env python
import json
import logging
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


class SearchLinkedin:

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

    @property
    def out_file(self):
        """ Output data file """
        return path.join('data', self.time_str + f'_all_{self.job_type}.csv')

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

    def login_linkedin(self):
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

        # go to Jobs
        logging.info("Search jobs by title and location.")
        jobs_link = self.driver.find_element(By.LINK_TEXT, 'Jobs')
        jobs_link.click()
        time.sleep(randint(3, 6))

        tries, max_tries = 1, 5
        while tries < max_tries:
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
        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                date_posted_button = self.driver.find_element(By.XPATH, '//button[starts-with(@aria-label, "Date posted filter.")][@type="button"]')
                date_posted_button.click()
                time.sleep(randint(2, 5))

                past24h_radiobutton = self.driver.find_element(By.XPATH, "//span[text()='Past 24 hours']")
                past24h_radiobutton.click()
                time.sleep(randint(2, 5))

                show_results_button = self.driver.find_element(By.XPATH, "//span[contains(normalize-space(), 'Show') and contains(normalize-space(), 'results')]")
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
            time.sleep(randint(1, 3))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            time.sleep(randint(1, 2) * 0.5)

            try:
                job_title = soup.find('span', {'class': 'job-details-jobs-unified-top-card__job-title-link'}).get_text(strip=True).strip()
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

    def scrape_jobs(self):
        """ Scrape/Crawl all jobs and save the jobs to a table file"""
        # Collect all jobs for each page

        page_num = 1
        while True:
            logging.info(f"Processing page {page_num}")
            try:
                page_button = self.driver.find_element(By.XPATH, f'//button[@aria-label="Page {page_num}"]')
            except Exception as e:
                logging.info(f"Unable to locate element - Page {page_num}.")
                time.sleep(randint(1, 2))
                break
            page_button.click()
            time.sleep(randint(3, 6))

            logging.info(f"Find all job links on Page {page_num}.")
            job_links = self.find_page_jobs()

            logging.info("Extract job title, company, location and description.")
            data = self.extract_data(job_links)
            self.save_results(data)

            page_num += 1
            if page_num > 40:
                logging.info(f"Exit as finished {page_num} job pages. .")
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
        logging.info("Start...")
        self.init_webdriver()
        self.login_linkedin()
        self.search_jobs()
        self.filter()
        self.scrape_jobs()
        self.close_session()
        logging.info("All done!")


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


def is_intern_job(title):
    """ Is a job an intern job? """
    return True if 'intern' in title else False


def require_us_citizenship(description):
    """ Is US Citizenship required"""
    if 'u.s. citizen' in description or 'us citizen' in description:
        return True
    return False


def is_geo_job(description):
    """
    Is it a Geo job?
    :param description: lowercase string description
    :return:
    """
    geo_keywords = ['remote sensing', 'satellite', 'earth observation', 'climate change']
    for keywords in geo_keywords:
        if keywords in description:
            return True
    return False


def is_ai_job(description):
    """
    Is it an AI job?
    :param description: lowercase string description
    :return:
    """
    ai_keywords = ['deep learning', 'pytorch', 'tensorflow']
    for keywords in ai_keywords:
        if keywords in description:
            return True
    return False


def is_cv_job(description):
    """
    Is it a computer vision job?
    :param description: lowercase string description
    :return:
    """
    if 'computer vision' in description:
        return True
    return False


def select_jobs(file_list):
    """
    Select geo_ai and cv_ai jobs from the file list
    :param file_list: a list of output files.
    :return:
    """
    # There are usually overlaps between SDS and MLE jobs. Merge the two and remove redundancies.
    geoai_links = set()
    cvai_links = set()

    def select_geo_cv_jobs(in_file):
        """ Select geo_ai and cv_ai jobs """
        df = pd.read_csv(in_file)
        logging.info(f"{df.shape[0]} job entries in {in_file}.")
        geoai_inds = []
        cvai_inds = []
        for i in range(df.shape[0]):
            row = df.iloc[i]
            link, title, company, location = row['Link'], row['Title'], row['Company'], row['Location']
            logging.info(f"{i + 1}/{df.shape[0]}, {link}, {title}, {company}, {location}")
            description = row['Description'].lower()
            if is_intern_job(row['Title'].lower()) or require_us_citizenship(description):
                continue
            is_ai = is_ai_job(description)
            is_geo = is_geo_job(description)
            is_cv = is_cv_job(description)

            if is_ai and is_geo and (link not in geoai_links):
                geoai_inds.append(i)
                geoai_links.add(link)
            if is_ai and is_cv and (link not in cvai_links):
                cvai_inds.append(i)
                cvai_links.add(link)
        return df, geoai_inds, cvai_inds

    geoai_dfs, cvai_dfs = [], []
    for in_file in file_list:
        df, geoai_inds, cvai_inds = select_geo_cv_jobs(in_file)
        geoai_dfs.append(df.loc[geoai_inds])
        cvai_dfs.append(df.loc[cvai_inds])
    geoai_df = pd.concat(geoai_dfs)
    cvai_df = pd.concat(cvai_dfs)
    logging.info(f"The number GeoAI job entries: {geoai_df.shape[0]}.")
    logging.info(f"The number CV_AI job entries: {cvai_df.shape[0]}.")

    geoai_file = path.join(path.dirname(file_list[-1]), path.basename(file_list[-1]).split("_")[0] + '_all_geoai.csv')
    geoai_df.to_csv(geoai_file, index=True)
    cvai_file = path.join(path.dirname(file_list[-1]), path.basename(file_list[-1]).split("_")[0] + '_all_cvai.csv')
    cvai_df.to_csv(cvai_file, index=True)
    logging.info("Done!")


if __name__ == '__main__':

    # configure a log file
    time_str = datetime.now().strftime("%Y%m%dH%H")
    config_log(path.join('data/logs', time_str + '.log'))

    # search MLE jobs in the US. Default filter is "Past 24 hours".
    keywords = "Senior Data Scientist"
    location = "United States"
    bot_sds = SearchLinkedin(keywords, location, time_str)
    bot_sds.run()

    # search MLE jobs in the US. Default filter is "Past 24 hours".
    keywords = "Machine Learning Engineer"
    location = "United States"
    bot_mle = SearchLinkedin(keywords, location, time_str)
    bot_mle.run()

    logging.info("Select interesting jobs form the search list.")
    select_jobs([bot_sds.out_file, bot_mle.out_file])

