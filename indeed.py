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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from base_search import SearchJobs, config_log


class SearchIndeed(SearchJobs):
    """
    """
    def __init__(self, keywords, location, time_str, driver_path=None):
        super(SearchIndeed, self).__init__(keywords, location, time_str, driver_path=driver_path)

    def login(self):
        """This function logs into your personal Indeed profile"""
        # Indeed doesn't require login for searching jobs.
        # logging.info(f"Go to the Indeed search url: https://www.indeed.com/q-software-engineer-jobs.html")
        # self.driver.get("https://www.indeed.com/q-software-engineer-jobs.html")
        # time.sleep(randint(1, 4))
        pass

    def search_jobs(self):
        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                # search based on keywords and location and hit enter
                if tries > 1:
                    logging.info(f"Number of trials for searching jobs: {tries}. ")

                logging.info(f"Search {self.keywords} at {self.location}")
                job_keywords = '-'.join(self.keywords.lower().strip().split(' '))
                self.driver.get(f"https://www.indeed.com/q-{job_keywords}-jobs.html")
                time.sleep(randint(1, 5))

                search_location = self.driver.find_element(By.XPATH, '//input[@id="text-input-where"]')
                search_location.clear()
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
        """ Filter jobs by post date/time """
        logging.info("Select jobs posted in the past 24 hours")
        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                # Find the 'Date posted' button
                date_posted_button = self.driver.find_element(By.XPATH,
                                                              '//button[@id="filter-dateposted"]')
                date_posted_button.click()
                time.sleep(randint(2, 5))
                # select jobs posted within 24 hours.
                past24h_radiobutton = self.driver.find_element(By.XPATH, "//a[text()='Last 24 hours']")
                past24h_radiobutton.click()
                time.sleep(randint(2, 5))

                # Find the 'Job type' button
                job_type_button = self.driver.find_element(By.XPATH, '//button[@id="filter-jobtype"]')
                job_type_button.click()
                time.sleep(randint(2, 5))
                # select full-time jobs only.
                full_time_button = self.driver.find_element(By.XPATH,
                                                            "//a[contains(normalize-space(), 'Full-time')]")
                full_time_button.click()
                time.sleep(randint(4, 8))
                logging.info("Job filtering is done!")
                break
            except Exception as e:
                logging.error(str(e))
                time.sleep(randint(3, 6))
            tries += 1

    def find_page_jobs(self):
        """ Find all jobs on a single page """
        """
         Find all jobs on a single page by treating it as a graph - BFS (breadth-first-search) traversal problem.
         :return:
             result_jobs: all jobs on this page in a dict {"link": job_element, }
         """
        def is_job_link(link_element):
            # check if a link element is a job link or not
            if str(link_element.get_attribute('href')).startswith("https://www.indeed.com/rc/"):
                return True
            return False

        def get_href_link(job_element):
            # return link of a job element.
            return job_element.get_attribute('href').split('&')[0]

        result_jobs = OrderedDict()  # all jobs: {link: element}
        link_elements = self.driver.find_elements(By.XPATH, "//a")
        q_elements = deque([a for a in link_elements if is_job_link(a)])
        q_links = deque([get_href_link(a) for a in q_elements])
        data = {'Link': [], 'Title': [], 'Company': [], 'Location': [], 'Description': []}
        while len(q_elements):
            sz = len(q_elements)
            for i in range(sz):
                job_element = q_elements.popleft()
                job_link = q_links.popleft()
                if job_link in result_jobs:
                    continue

                # collect data from the current job
                job_title, company_name, location, description = self.retrieve_data(job_element)
                data['Link'].append(job_link)
                data['Title'].append(job_title)
                data['Company'].append(company_name)
                data['Location'].append(location)
                data['Description'].append(description)

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

    def retrieve_data(self, job_element):
        job_element.click()
        time.sleep(randint(1, 3))
        title_element = self.driver.find_element(By.XPATH, "//span[contains(normalize-space(), ' - job post')]")
        job_title = title_element.text.strip().replace('\n- job post', '')

        company_element = self.driver.find_element(By.XPATH,
                                                   '//a[contains(@aria-label, "(opens in a new tab)")][starts-with(@href, "https://www.indeed.com/cmp")]')
        company_name = company_element.text.strip()

        jd_element = self.driver.find_element(By.XPATH, '//div[@id="jobDescriptionText"]')
        description = jd_element.text.strip()

        location_element = self.driver.find_element(By.XPATH, '//div[contains(@data-testid, "companyLocation")]')
        location = location_element.text.strip()
        return job_title, company_name, location, description


    # def extract_data(self, job_links):
    #     """
    #     Extract information from a job link
    #     :param job_links:
    #     :return:
    #     """
    #     # Extract relevant information from each job posting and store it in a list of dictionaries
    #     data = {'Link': [], 'Title': [], 'Company': [], 'Location': [], 'Description': []}
    #     for i, (link, job_element) in enumerate(job_links.items()):
    #         logging.info(f"Scrape link {i + 1} / {len(job_links)}: {link}")
    #         job_element.click()
    #         time.sleep(randint(1, 3))
    #         try:
    #             title_element = self.driver.find_element(By.XPATH, "//span[contains(normalize-space(), ' - job post')]")
    #             job_title = title_element.text.strip().replace('\n- job post', '')
    #
    #             company_element = self.driver.find_element(By.XPATH, '//a[contains(@aria-label, "(opens in a new tab)")][starts-with(@href, "https://www.indeed.com/cmp")]')
    #             company_name = company_element.text.strip()
    #
    #             jd_element = self.driver.find_element(By.XPATH, '//div[@id="jobDescriptionText"]')
    #             description = jd_element.text.strip()
    #
    #             location_element = self.driver.find_element(By.XPATH, '//div[contains(@data-testid, "companyLocation")]')
    #             location = location_element.text.strip()
    #
    #             data['Link'].append(link)
    #             data['Title'].append(job_title)
    #             data['Company'].append(company_name)
    #             data['Location'].append(location)
    #             data['Description'].append(description)
    #         except Exception as e:
    #             logging.error(str(e))
    #     return data

    def scrape_jobs(self):
        """ Scrape/Crawl all jobs and save the jobs to a table file"""
        # Collect all jobs for each page

        page_num = 1
        while True:
            logging.info(f"Processing page {page_num}")
            if page_num > 1:
                try:
                    page_button = self.driver.find_element(By.XPATH, f'//a[@data-testid="pagination-page-{page_num}"]')
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
                    data = self.find_page_jobs()
                    # logging.info("Extract job title, company, location and description.")
                    # data = self.extract_data(job_links)
                    self.save_results(data)
                    break
                except Exception as e:
                    logging.error(str(e))
                    time.sleep(randint(3, 6))

            page_num += 1
            if page_num > 40:
                logging.info(f"Exit as finished {page_num} job pages.")
                break

    def run(self):
        """ Search jobs and save results """
        logging.info("Start...")
        self.init_webdriver()
        self.login()
        self.search_jobs()
        self.filter()
        self.scrape_jobs()
        self.close_session()
        logging.info("All done!")


if __name__ == '__main__':
    time_str = datetime.now().strftime("%Y%m%dH%H")
    config_log(path.join('data/logs', time_str + '_indeed.log'))

    job_titles = ["Machine Learning Engineer", "Senior Data Scientist"]
    locations = ["Seattle, WA"]
    for location in locations:
        out_files = []
        for job_title in job_titles:
            bot = SearchIndeed(job_title, location, time_str)
            bot.run()
            out_files.append(bot.out_file)
        logging.info("Select interesting jobs form the search list.")

