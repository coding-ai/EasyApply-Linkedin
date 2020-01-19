from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.common.action_chains import ActionChains
import re
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

class EasyApplyLinkedin:

    def __init__(self, email, password, keywords, location, driver_path):

        self.email = email
        self.password = password
        self.keywords = keywords
        self.location = location
        self.driver = webdriver.Chrome(driver_path)

    def login_linkedin(self):
        self.driver.get("https://www.linkedin.com/login")
        login_email = self.driver.find_element_by_name('session_key')
        login_email.clear()
        login_email.send_keys(self.email)
        login_pass = self.driver.find_element_by_name('session_password')
        login_pass.clear()
        login_pass.send_keys(self.password)
        login_pass.send_keys(Keys.RETURN)
    
    def job_search(self):
        jobs_link = self.driver.find_element_by_link_text('Jobs')
        jobs_link.click()
        search_keywords = self.driver.find_element_by_css_selector(".jobs-search-box__text-input[aria-label='Search jobs']")
        search_keywords.clear()
        search_keywords.send_keys(self.keywords)
        search_location = self.driver.find_element_by_css_selector(".jobs-search-box__text-input[aria-label='Search location']")
        search_location.clear()
        search_location.send_keys(self.location)
        search_location.send_keys(Keys.RETURN)

    def filter(self):
        all_filters_button = self.driver.find_element_by_xpath("//button[@data-control-name='all_filters']")
        all_filters_button.click()
        time.sleep(1)
        easy_apply_button = self.driver.find_element_by_xpath("//label[@for='f_LF-f_AL']")
        easy_apply_button.click()
        time.sleep(1)
        apply_filter_button = self.driver.find_element_by_xpath("//button[@data-control-name='all_filters_apply']")
        apply_filter_button.click()

    def find_offers(self):
        total_results = self.driver.find_element_by_class_name("display-flex.t-12.t-black--light.t-normal")
        total_results_int = int(total_results.text.split(' ',1)[0].replace(",",""))
        print(total_results_int)

        time.sleep(2)
        current_page = self.driver.current_url
        results = self.driver.find_elements_by_class_name("occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")
        for result in results:
            hover = ActionChains(self.driver).move_to_element(result)
            hover.perform()
            titles = result.find_elements_by_class_name('job-card-search__title.artdeco-entity-lockup__title.ember-view')
            for title in titles:
                self.submit_apply(title)
        if total_results_int > 24:
            time.sleep(2)
            find_pages = self.driver.find_elements_by_class_name("artdeco-pagination__indicator.artdeco-pagination__indicator--number")
            total_pages = find_pages[len(find_pages)-1].text
            total_pages_int = int(re.sub(r"[^\d.]", "", total_pages))
            get_last_page = self.driver.find_element_by_xpath("//button[@aria-label='Page "+str(total_pages_int)+"']")
            get_last_page.send_keys(Keys.RETURN)
            time.sleep(2)
            last_page = self.driver.current_url
            total_jobs = int(last_page.split('start=',1)[1])

            for page_number in range(25,total_jobs+25,25):
                self.driver.get(current_page+'&start='+str(page_number))
                time.sleep(2)
                results2 = self.driver.find_elements_by_class_name("occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")
                for result2 in results2:
                    hover2 = ActionChains(self.driver).move_to_element(result2)
                    hover2.perform()
                    titles2 = result2.find_elements_by_class_name('job-card-search__title.artdeco-entity-lockup__title.ember-view')
                    for title2 in titles2:
                        self.submit_apply(title2)
        else:
            self.close_session()

    def submit_apply(self,job_add):
        print('You are applying to the position of: ', job_add.text)
        job_add.click()
        time.sleep(2)
        in_apply = self.driver.find_element_by_xpath("//button[@data-control-name='jobdetails_topcard_inapply']")
        in_apply.click()
        time.sleep(1)
        try:
            submit = self.driver.find_element_by_xpath("//button[@data-control-name='submit_unify']")
            submit.send_keys(Keys.RETURN)
        except NoSuchElementException:
            print('Not direct application, going to next...')
            discard = self.driver.find_element_by_xpath("//button[@data-test-modal-close-btn]")
            discard.send_keys(Keys.RETURN)
            time.sleep(1)
            discard_confirm = self.driver.find_element_by_xpath("//button[@data-test-dialog-primary-btn]")
            discard_confirm.send_keys(Keys.RETURN)
            time.sleep(1)

        time.sleep(1)

    def close_session(self):
        print('End of the session, see you later!')
        self.driver.close()

    def apply(self):
        self.driver.maximize_window()
        self.login_linkedin()
        time.sleep(5)
        self.job_search()
        time.sleep(5)
        self.filter()
        time.sleep(2)
        self.find_offers()


if __name__ == '__main__':

    email = ''
    password = ''
    keywords = ''
    location = ''
    driver_path = ''

    bot = EasyApplyLinkedin(email,password,keywords,location,driver_path)
    bot.apply()