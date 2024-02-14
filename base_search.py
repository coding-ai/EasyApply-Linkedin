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
        self.keywords = keywords.strip()
        self.location = location.strip()
        self.time_str = time_str

        self.email = None
        self.password = None
        self.driver_path = driver_path
        self.driver = None

    @property
    def out_file(self):
        """ Output data file """
        if ',' in self.location:
            # use the first word
            location = self.location.lower().split(',')[0]  # use the first word
        elif ' ' in self.location:
            # use the first letter of each word
            location = ''.join([word[0].lower() for word in self.location.split(' ')])
        else:
            location = self.location.lower()
        platform = self.__class__.__name__.lower().replace('search', '')
        return path.join('data', self.time_str + f'_{platform}_{location}_{self.job_abbr}.csv')

    @property
    def job_abbr(self):
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
        pass

    def scrape_jobs(self):
        """ Scrape/Crawl all jobs and save the jobs to a table file"""
        pass

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
        self.login()
        self.search_jobs()
        self.filter()
        self.scrape_jobs()
        self.close_session()
        logging.info("Session closed!")


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
