#!/usr/bin/env python
import logging
import os
from datetime import datetime
from os import path, makedirs
import pandas as pd
from indeed import SearchIndeed
from linkedin import SearchLinkedin


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
    """ Is US Citizenship required """
    # description is all lowercase.
    citizen_keywords = ['u.s. citizen', 'us citizen', 'united states citizen']
    for keywords in citizen_keywords:
        if keywords in description:
            return True
    return False


def is_geo_job(description):
    """
    Is it a Geo job?
    :param description: lowercase string description
    :return:
    """
    # a geo job should contain any of the following keywords
    geo_keywords = ['remote sensing', 'earth observation']
    for keywords in geo_keywords:
        if keywords in description:
            return True
    # a job description contains 2+ of the following keywords, it's a geo job
    cnt = 0
    for keyword in ['satellite', 'geospatial', 'image', 'climate change']:
        if keyword in description:
            cnt += 1
    return cnt >= 2


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


def is_rs_job(description):
    """
    Is it a recommender system job?
    :param description: lowercase string description
    :return:
    """
    rs_keywords = ['recommender system', 'recommendation system']
    for keywords in rs_keywords:
        if keywords in description:
            return True
    return False


def is_auto_job(description):
    """
    Is it an autonomous driving job
    :param description: 
    :return: 
    """
    cnt = 0
    for keyword in ['autonomous driving', 'self-driving', 'perception', 'lidar', 'radar', 'calibration', 'mapping']:
        if keyword in description:
            cnt += 1
    # if the description contains 2+ of the keywords, it's considered as an autonomous driving job
    return cnt >= 2


def select_jobs(file_list):
    """
    Select geo_ai and cv_ai jobs from the file list
    :param file_list: a list of output files.
    :return:
    """
    # There are usually overlaps between SDS and MLE jobs. Merge the two and remove redundancies.
    geoai_links = set()
    cvai_links = set()
    rsai_links = set()
    auto_links = set()

    def select_geo_cv_jobs(in_file):
        """ Select geo_ai and cv_ai jobs """
        df = pd.read_csv(in_file)
        logging.info(f"{df.shape[0]} job entries in {in_file}.")
        geoai_inds = []
        cvai_inds = []
        rsai_inds = []
        auto_inds = []
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
            is_rs = is_rs_job(description)
            is_auto = is_auto_job(description)

            if is_ai and is_geo and (link not in geoai_links):
                geoai_inds.append(i)
                geoai_links.add(link)
            if is_ai and is_cv and (link not in cvai_links):
                cvai_inds.append(i)
                cvai_links.add(link)
            if is_ai and is_rs and (link not in rsai_links):
                rsai_inds.append(i)
                rsai_links.add(link)
            if is_ai and is_auto and (link not in auto_links):
                auto_inds.append(i)
                auto_links.add(link)
        return df, geoai_inds, cvai_inds, rsai_inds, auto_inds

    geoai_dfs, cvai_dfs, rsai_dfs, auto_dfs = [], [], [], []
    for in_file in file_list:
        df, geoai_inds, cvai_inds, rsai_inds, auto_inds = select_geo_cv_jobs(in_file)
        geoai_dfs.append(df.loc[geoai_inds])
        cvai_dfs.append(df.loc[cvai_inds])
        rsai_dfs.append(df.loc[rsai_inds])
        auto_dfs.append(df.loc[auto_inds])

    geoai_df = pd.concat(geoai_dfs)
    cvai_df = pd.concat(cvai_dfs)
    rsai_df = pd.concat(rsai_dfs)
    auto_df = pd.concat(auto_dfs)
    logging.info(f"The number GeoAI job entries: {geoai_df.shape[0]}.")
    logging.info(f"The number CV_AI job entries: {cvai_df.shape[0]}.")
    logging.info(f"The number RS_AI job entries: {rsai_df.shape[0]}.")
    logging.info(f"The number AutoAI job entries: {auto_df.shape[0]}.")

    base_name = '_'.join(path.basename(file_list[-1]).split("_")[0:2])
    if geoai_df.shape[0] > 0:
        geoai_file = path.join(path.dirname(file_list[-1]), base_name + '_geoai.csv')
        geoai_df.to_csv(geoai_file, index=True)
    if cvai_df.shape[0] > 0:
        cvai_file = path.join(path.dirname(file_list[-1]), base_name + '_cvai.csv')
        cvai_df.to_csv(cvai_file, index=True)
    if rsai_df.shape[0] > 0:
        rsai_file = path.join(path.dirname(file_list[-1]), base_name + '_rsai.csv')
        rsai_df.to_csv(rsai_file, index=True)
    if auto_df.shape[0] > 0:
        auto_file = path.join(path.dirname(file_list[-1]), base_name + '_autoai.csv')
        auto_df.to_csv(auto_file, index=True)

    # delete the files
    for in_file in file_list:
        os.remove(in_file)
    logging.info("Done!")


if __name__ == '__main__':
    # configure a log file
    time_str = datetime.now().strftime("%Y%m%dH%H")
    config_log(path.join('data/logs', time_str + '.log'))

    job_titles = ["Machine Learning Engineer", "Senior Data Scientist"]  # , "Research Scientist"]
    locations = ["United States"]  # , "Canada"]

    # Search jobs on LinkedIn
    logging.info("Search jobs on LinkedIn.")
    for location in locations:
        out_files = []
        for job_title in job_titles:
            bot = SearchLinkedin(job_title, location, time_str)
            bot.run()
            out_files.append(bot.out_file)
        logging.info("Select interesting jobs form the search list.")
        select_jobs(out_files)

    # Search jobs on Indeed
    job_titles = ["Machine Learning Engineer", "Senior Data Scientist"]
    locations = ["Seattle, WA", "San Jose, CA", "New York, NY", "Boston, MA"]
    logging.info("Search jobs on Indeed.")
    for location in locations:
        out_files = []
        for job_title in job_titles:
            bot = SearchIndeed(job_title, location, time_str)
            bot.run()
            out_files.append(bot.out_file)
        logging.info("Select interesting jobs form the search list.")
        select_jobs(out_files)

