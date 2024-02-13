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
from base_search import SearchJobs, config_log


class SearchIndeed(SearchJobs):
    """
    """
    def __init__(self, keywords, location, time_str, driver_path=None):
        super(SearchIndeed, self).__init__(keywords, location, time_str, driver_path=driver_path)

    def login(self):
        """This function logs into your personal Indeed profile"""
        # Indeed doesn't require login for searching jobs.
        logging.info(f"Go to the Indeed search url: https://www.indeed.com/q-welcome-to-the-usa-jobs.html")
        self.driver.get("https://www.indeed.com/q-welcome-to-the-usa-jobs.html")
        time.sleep(randint(1, 4))

    def search_jobs(self):
        tries, max_tries = 1, 5
        while tries < max_tries:
            try:
                # search based on keywords and location and hit enter
                if tries > 1:
                    logging.info(f"Number of trials for searching jobs: {tries}. ")

                logging.info(f"Search {self.keywords} at {self.location}")
                search_keywords = self.driver.find_element(By.XPATH, '//input[@id="text-input-what"]')
                # TODO: clear() does not work!
                search_keywords.clear()
                search_keywords.click()
                time.sleep(randint(1, 2) * 0.5)
                search_keywords.send_keys(self.keywords)
                time.sleep(randint(3, 6))
                search_keywords.send_keys(Keys.RETURN)
                time.sleep(randint(3, 6))

                search_location = self.driver.find_element(By.XPATH, '//input[@id="text-input-where"]')
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
        """ Filter jobs by post date/time """
        pass

    def find_page_jobs(self):
        """ Find all jobs on a single page """
        pass

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

