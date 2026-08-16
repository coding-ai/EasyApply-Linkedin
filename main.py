import argparse
import json
import time
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
    ElementClickInterceptedException,
)

from base_easy_apply import BaseEasyApply


class EasyApplyLinkedin(BaseEasyApply):
    BASE_URL = "https://www.linkedin.com/jobs/search/"
    COLLECTION_URLS = {
        "small_business": "https://www.linkedin.com/jobs/collections/small-business",
        "remote_jobs": "https://www.linkedin.com/jobs/collections/remote-jobs",
        "easy_apply": "https://www.linkedin.com/jobs/collections/easy-apply",
        "top_applicant": "https://www.linkedin.com/jobs/collections/top-applicant"
    }

    TIME_POSTED_MAPPING = {
        "Any Time": "",
        "Last Month": "r2592000",
        "Past Week": "r604800",
        "Past 24 hours": "r86400",
    }

    EXPERIENCE_MAPPING = {
        "Internship": "1",
        "Entry level": "2",
        "Associate": "3",
        "Mid-Senior level": "4",
        "Director": "5",
        "Executive": "6",
    }

    WORKPLACE_TYPE_MAPPING = {
        "Remote": "2",
        "Hybrid": "3",
        "On-site": "1",
    }

    JOB_TYPE_MAPPING = {
        "Full-time": "F",
        "Part-time": "P",
        "Contract": "C",
        "Internship": "I",
        "Temporary": "T",
    }

    TITLE_MAPPING = {
        "Engineer": "9",
        "Developer": "25201",
        "Manager": "25170",
        "Specialist": "1456",
        "Consultant": "3731",
    }

    COMMITMENTS_MAPPING = {
        "Full-time": "1",
        "Part-time": "2",
        "Contract": "3",
        "Temporary": "4",
        "Volunteer": "5",
    }

    LOCATION_MAPPING = {
        "Texas": "102748797",
        "Canada": "101174742",
        "Portugal": "100364837",
        "Switzerland": "106693272",
        "United States": "103644278",
        "Belgium": "100565514",
        "Netherlands": "102890719",
        "DACH": "91000006",
        "Benelux": "91000005",
        "European Union": "91000000",
        "European Economic Area": "91000002",
        "Germany": "101282230",
        "Spain": "105646813",
        "United Kingdom": "101165590",
    }

    def __init__(self, data):
        super().__init__(data, start_driver=True)
        self.collection = data.get("collection", "")
        self.sort_by = data["sortBy"]
        self.locations = data["locations"]
        self.filters = data["filters"]

    def _gather_application_text(self, label_text=""):
        chunks = [label_text or ""]
        try:
            modal = self.driver.find_element(
                By.CSS_SELECTOR, "div.artdeco-modal--layer-default.jobs-easy-apply-modal"
            )
            chunks.append(modal.text or "")
        except Exception:
            pass
        try:
            details = self.driver.find_element(By.CLASS_NAME, "jobs-search__job-details--wrapper")
            chunks.append((details.text or "")[:2000])
        except Exception:
            pass
        return "\n".join(chunks)

    def login_linkedin(self):
        try:
            self.driver.get("https://www.linkedin.com/login")
            self.driver.add_cookie({
                'name': 'li_theme',
                'value': 'dark',
                'domain': '.linkedin.com',
                'path': '/',
                'expires': int(time.time() + 365 * 24 * 60 * 60),
                'secure': True,
                'httpOnly': False
            })
            self.driver.refresh()
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "session_key"))
            )
            login_email = self.driver.find_element(By.NAME, "session_key")
            login_email.clear()
            login_email.send_keys(self.email)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "session_password"))
            )
            login_pass = self.driver.find_element(By.NAME, "session_password")
            login_pass.clear()
            login_pass.send_keys(self.password)
            login_pass.send_keys(Keys.RETURN)
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.LINK_TEXT, "Jobs"))
            )
        except Exception as e:
            self.log_error(f"Login error: {e}")

    def job_search(self):
        while self.current_location_index < len(self.locations):
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.LINK_TEXT, "Jobs"))
                )
                jobs_link = self.driver.find_element(By.LINK_TEXT, "Jobs")
                jobs_link.click()
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[aria-label='Search by title, skill, or company']")
                    )
                )
                search_keywords = self.driver.find_element(
                    By.CSS_SELECTOR, "input[aria-label='Search by title, skill, or company']")
                search_keywords.clear()
                search_keywords.send_keys(self.keywords)
                search_keywords.send_keys(" NOT ")
                search_keywords.send_keys(self.keywords_to_avoid)
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[aria-label='City, state, or zip code']")
                    )
                )
                search_location = self.driver.find_element(
                    By.CSS_SELECTOR, "input[aria-label='City, state, or zip code']")
                search_location.clear()
                search_location.send_keys(self.locations[self.current_location_index])
                search_keywords.click()
                search_keywords.send_keys(Keys.RETURN)

                time.sleep(5)
                if not self.check_no_results():
                    break
                else:
                    self.log_info(f"No matching jobs found in {self.locations[self.current_location_index]}.")
                    self.current_location_index += 1

            except TimeoutException:
                self.log_info("Timeout while trying to access the Jobs page or elements on it.")
                self.current_location_index += 1
            except Exception as e:
                self.log_error(f"Job search error: {e}")
                self.current_location_index += 1

    def construct_url(self):
        current_location = self.locations[self.current_location_index]
        combined_keywords = f'{self.keywords} NOT {self.keywords_to_avoid}'

        params = {
            "keywords": combined_keywords,
            "origin": "JOB_SEARCH_PAGE_JOB_FILTER",
            "refresh": "true",
            "sortBy": self.sort_by,
        }

        if self.filters.get("easy_apply"):
            params["f_AL"] = "true"

        if self.filters.get("experience"):
            params["f_E"] = ",".join(
                [self.EXPERIENCE_MAPPING[exp] for exp in self.filters["experience"]]
            )

        if self.filters.get("jobType"):
            params["f_JT"] = ",".join(
                [self.JOB_TYPE_MAPPING[jt] for jt in self.filters["jobType"]]
            )

        if self.filters.get("timePostedRange"):
            params["f_TPR"] = ",".join(
                [self.TIME_POSTED_MAPPING[time] for time in self.filters["timePostedRange"]]
            )

        if self.filters.get("workplaceType"):
            params["f_WT"] = ",".join(
                [self.WORKPLACE_TYPE_MAPPING[wt] for wt in self.filters["workplaceType"]]
            )

        if self.filters.get("less_than_10_applicants"):
            params["f_EA"] = "true"

        if current_location in self.LOCATION_MAPPING:
            params["geoId"] = self.LOCATION_MAPPING[current_location]

        query_string = urllib.parse.urlencode(params, safe=",")
        url = f"{self.BASE_URL}?{query_string}"
        return url

    def apply_filters_and_search(self):
        while self.current_location_index < len(self.locations):
            search_url = self.construct_url()
            self.driver.get(search_url)
            time.sleep(5)

            if self.check_no_results():
                self.log_info(f"No matching jobs found in {self.locations[self.current_location_index]}.")
                self.current_location_index += 1
            else:
                break

    def check_no_results(self):
        try:
            no_results_element = self.driver.find_element(
                By.CSS_SELECTOR, "div.jobs-search-no-results-banner"
            )
            return no_results_element.is_displayed()
        except NoSuchElementException:
            return False

    def find_offers(self):
        if self.collection:
            self.apply_collection()
        else:
            self.apply_filtered_jobs()

    def apply_filtered_jobs(self):
        while self.current_location_index < len(self.locations):
            self.apply_filters_and_search()

            current_page = 1

            while True:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "scaffold-layout__list-container"))
                    )

                    job_list_container = self.find_element_with_retry(By.CLASS_NAME, "scaffold-layout__list-container")
                    job_list_items = job_list_container.find_elements(By.TAG_NAME, "li")

                    for index in range(len(job_list_items)):
                        try:
                            job_list_container = self.find_element_with_retry(By.CLASS_NAME, "scaffold-layout__list-container")
                            job_list_items = job_list_container.find_elements(By.TAG_NAME, "li")

                            if index >= len(job_list_items):
                                break

                            job_item = job_list_items[index]
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", job_item)
                            time.sleep(1)

                            try:
                                self.driver.execute_script("arguments[0].click();", job_item)
                            except ElementClickInterceptedException:
                                self.log_info("Element click intercepted, skipping to next job...")
                                continue

                            time.sleep(2)

                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CLASS_NAME, "jobs-search__job-details--wrapper")
                                )
                            )

                            company_name = self.get_company_name(job_item)

                            if company_name in self.applied_companies:
                                self.log_info(f"Already applied to a job at {company_name}, skipping...")
                                self.close_application_modal()
                                continue

                            job_details_wrapper = self.find_element_with_retry(By.CLASS_NAME, "jobs-search__job-details--wrapper")

                            try:
                                apply_button = job_details_wrapper.find_element(
                                    By.CSS_SELECTOR, "button.jobs-apply-button.artdeco-button--primary"
                                )
                                apply_button.click()
                                time.sleep(2)

                                WebDriverWait(self.driver, 10).until(
                                    EC.presence_of_element_located(
                                        (By.CSS_SELECTOR, "div.jobs-easy-apply-modal")
                                    )
                                )

                                try:
                                    self.handle_easy_apply()
                                    self.log_applied_company(company_name)
                                except Exception as e:
                                    self.log_info(f"Failed to apply at {company_name}: {str(e)}")
                                    self.log_failed_application(company_name)

                            except NoSuchElementException:
                                self.log_info("No apply button found, continuing to next job...")
                                continue

                        except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException) as e:
                            self.log_info(f"Exception occurred: {e}, continuing to next job...")
                            self.log_error(f"Find offers error: {e}")
                            continue

                    try:
                        pagination_container = self.find_element_with_retry(By.CLASS_NAME, "artdeco-pagination__pages")
                        next_page_button = pagination_container.find_element(
                            By.XPATH,
                            f"//button[@aria-label='Page {current_page + 1}']",
                        )
                        self.driver.execute_script("arguments[0].click();", next_page_button)
                        time.sleep(2)
                        current_page += 1
                    except NoSuchElementException:
                        self.log_info("No more pages left.")
                        break
                except TimeoutException:
                    self.log_info("Timeout while waiting for job list container.")
                    self.log_error("Timeout while waiting for job list container.")
                    break

            self.current_location_index += 1

    def apply_collection(self):
        collection_url = self.COLLECTION_URLS.get(self.collection)
        if not collection_url:
            self.log_error(f"Invalid collection: {self.collection}")
            return

        self.driver.get(collection_url)
        time.sleep(5)

        current_page = 1

        while True:
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "scaffold-layout__list-container"))
                )

                job_list_container = self.find_element_with_retry(By.CLASS_NAME, "scaffold-layout__list-container")
                job_list_items = job_list_container.find_elements(By.TAG_NAME, "li")

                for index in range(len(job_list_items)):
                    try:
                        job_list_container = self.find_element_with_retry(By.CLASS_NAME, "scaffold-layout__list-container")
                        job_list_items = job_list_container.find_elements(By.TAG_NAME, "li")

                        if index >= len(job_list_items):
                            break

                        job_item = job_list_items[index]
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", job_item)
                        time.sleep(1)

                        try:
                            self.driver.execute_script("arguments[0].click();", job_item)
                        except ElementClickInterceptedException:
                            self.log_info("Element click intercepted, skipping to next job...")
                            continue

                        time.sleep(2)

                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CLASS_NAME, "jobs-search__job-details--wrapper")
                            )
                        )

                        company_name = self.get_company_name(job_item)

                        if company_name in self.applied_companies:
                            self.log_info(f"Already applied to a job at {company_name}, skipping...")
                            self.close_application_modal()
                            continue

                        job_details_wrapper = self.find_element_with_retry(By.CLASS_NAME, "jobs-search__job-details--wrapper")

                        try:
                            apply_button = job_details_wrapper.find_element(
                                By.CSS_SELECTOR, "button.jobs-apply-button.artdeco-button--primary"
                            )
                            apply_button.click()
                            time.sleep(2)

                            WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, "div.jobs-easy-apply-modal")
                                )
                            )

                            try:
                                self.handle_easy_apply()
                                self.log_applied_company(company_name)
                            except Exception as e:
                                self.log_info(f"Failed to apply at {company_name}: {str(e)}")
                                self.log_failed_application(company_name)

                        except NoSuchElementException:
                            self.log_info("No apply button found, continuing to next job...")
                            continue

                    except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException) as e:
                        self.log_info(f"Exception occurred: {e}, continuing to next job...")
                        self.log_error(f"Find offers error: {e}")
                        continue

                try:
                    pagination_container = self.find_element_with_retry(By.CLASS_NAME, "artdeco-pagination__pages")
                    next_page_button = pagination_container.find_element(
                        By.XPATH,
                        f"//button[@aria-label='Page {current_page + 1}']",
                    )
                    self.driver.execute_script("arguments[0].click();", next_page_button)
                    time.sleep(2)
                    current_page += 1
                except NoSuchElementException:
                    self.log_info("No more pages left.")
                    break
            except TimeoutException:
                self.log_info("Timeout while waiting for job list container.")
                self.log_error("Timeout while waiting for job list container.")
                break

    def get_company_name(self, job_item):
        try:
            company_element = job_item.find_element(
                By.CSS_SELECTOR,
                "div.artdeco-entity-lockup__subtitle span.job-card-container__primary-description",
            )
            return company_element.text.strip()
        except NoSuchElementException:
            return None

    def handle_easy_apply(self):
        while True:
            try:
                modal_dialog = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.artdeco-modal--layer-default.jobs-easy-apply-modal")
                    )
                )
                try:
                    next_button = modal_dialog.find_element(
                        By.CSS_SELECTOR, "button[data-easy-apply-next-button]"
                    )
                    self.driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(2)
                except NoSuchElementException:
                    try:
                        review_button = modal_dialog.find_element(
                            By.CSS_SELECTOR, "button[aria-label='Review your application']"
                        )
                        self.driver.execute_script("arguments[0].click();", review_button)
                        time.sleep(2)
                    except NoSuchElementException:
                        try:
                            submit_button = modal_dialog.find_element(
                                By.CSS_SELECTOR, "button[aria-label='Submit application']"
                            )
                            self.driver.execute_script("arguments[0].click();", submit_button)
                            time.sleep(2)
                            self.log_info("Application submitted.")
                            self.handle_done_button()
                            break
                        except NoSuchElementException:
                            self.log_info("Submit button not found, continuing to next job...")
                            self.close_application_modal()
                            break
                self.fill_form(modal_dialog)
            except TimeoutException:
                self.log_info("No more steps found, exiting...")
                break
            except Exception as e:
                self.log_info(f"Error during easy apply: {e}, skipping to next job...")
                self.log_error(f"Easy apply error: {e}")
                self.close_application_modal()
                break

    def fill_form(self, modal_dialog):
        form_elements = modal_dialog.find_elements(
            By.CSS_SELECTOR, "div[data-test-form-element], fieldset[data-test-form-builder-radio-button-form-component], fieldset[data-test-checkbox-form-component], div[data-test-text-entity-list-form-component]"
        )
        for element in form_elements:
            try:
                try:
                    label = element.find_element(By.CSS_SELECTOR, "label, legend, span[aria-hidden='true']")
                    label_text = label.text.strip()
                except NoSuchElementException:
                    self.log_info("No label found for a form element, skipping...")
                    continue

                if "notice period" in label_text.lower() or "kündigungsfrist" in label_text.lower():
                    input_field = element.find_element(By.CSS_SELECTOR, "input[type='text']")
                    if input_field.get_attribute("value") == "":
                        notice = (
                            (self.context_data.get("aiContext") or {})
                            .get("user_data", {})
                            .get("noticePeriodDays", 30)
                        )
                        self.log_info(f"Filling notice period with {notice} for field: {label_text}")
                        input_field.clear()
                        input_field.send_keys(str(notice))
                        time.sleep(1)
                        input_field.send_keys(Keys.RETURN)
                    continue

                if "data-test-checkbox-form-component" in element.get_attribute("outerHTML"):
                    self.handle_checkboxes(element)
                elif "data-test-text-entity-list-form-component" in element.get_attribute("outerHTML"):
                    select_element = element.find_element(By.CSS_SELECTOR, "select")
                    options = [option.text for option in select_element.find_elements(By.TAG_NAME, "option")]
                    response = self.get_radio_response_for_label(label_text, options[1:])
                    for option in select_element.find_elements(By.TAG_NAME, "option"):
                        if option.text == response:
                            option.click()
                            break
                else:
                    input_field = element.find_element(By.CSS_SELECTOR, "input, select, textarea")

                    if input_field.tag_name == "input" and input_field.get_attribute("type") == "text":
                        response = self.get_response_for_label(label_text)
                        if input_field.get_attribute("value") == "":
                            input_field.send_keys(response)
                            time.sleep(1)
                            input_field.send_keys(Keys.ARROW_DOWN)
                            input_field.send_keys(Keys.RETURN)

                    elif input_field.tag_name == "select":
                        response = self.get_response_for_label(label_text)
                        select_options = input_field.find_elements(By.TAG_NAME, "option")
                        for option in select_options:
                            if option.get_attribute("value") == response:
                                option.click()
                                break

                    elif input_field.tag_name == "textarea":
                        response = self.get_response_for_label(label_text)
                        if input_field.get_attribute("value") == "":
                            input_field.send_keys(response)

                    elif input_field.tag_name == "input" and input_field.get_attribute("type") == "radio":
                        radio_buttons = element.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                        for radio in radio_buttons:
                            radio_label = radio.find_element(By.XPATH, "./following-sibling::label").text.strip()
                            response = self.get_radio_response_for_label(label_text, [rb.find_element(By.XPATH, "./following-sibling::label").text.strip() for rb in radio_buttons])
                            if response.lower() == radio_label.lower():
                                try:
                                    radio.click()
                                except ElementClickInterceptedException:
                                    self.driver.execute_script("arguments[0].click();", radio)
                                break

                    elif input_field.tag_name == "input" and input_field.get_attribute("type") == "file":
                        response = self.get_file_response_for_label(label_text)
                        input_field.send_keys(response)
                        time.sleep(1)

            except NoSuchElementException as e:
                self.log_error(f"Element not found for a form field, error: {e}")
                continue
            except ElementNotInteractableException as e:
                self.log_error(f"Element not interactable for a form field, error: {e}")
                continue
            except Exception as e:
                self.log_error(f"Unexpected error while processing form field: {e}")
                continue

        try:
            next_button = modal_dialog.find_element(By.CSS_SELECTOR, "button[data-easy-apply-next-button]")
            next_button.click()
            time.sleep(2)
        except NoSuchElementException:
            self.log_info("Next button not found, form might be complete or there is an issue.")

    def handle_checkboxes(self, element):
        checkboxes = element.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for index in range(len(checkboxes)):
            checkbox_label = None
            try:
                checkbox = checkboxes[index]
                checkbox_label = checkbox.find_element(By.XPATH, "./following-sibling::label").text.strip()
                response = self.get_checkbox_response_for_label(checkbox_label)
                if response is not None:
                    self.set_checkbox_state(checkbox, checkbox_label, response)
            except (ElementClickInterceptedException, StaleElementReferenceException) as e:
                self.log_info(f"Checkbox interaction failed for {checkbox_label}, attempting to retry. Error: {e}")
                self.retry_checkbox_interaction(element, index)

    def retry_checkbox_interaction(self, element, index):
        retries = 3
        while retries > 0:
            retries -= 1
            try:
                checkboxes = element.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                checkbox = checkboxes[index]
                checkbox_label = checkbox.find_element(By.XPATH, "./following-sibling::label").text.strip()
                response = self.get_checkbox_response_for_label(checkbox_label)
                if response is not None:
                    self.set_checkbox_state(checkbox, checkbox_label, response)
                return
            except (NoSuchElementException, StaleElementReferenceException) as e:
                self.log_info(f"Retry failed for {checkbox_label}. Error: {e}")
                if retries == 0:
                    self.log_info(f"Skipping {checkbox_label} after multiple retries.")

    def set_checkbox_state(self, checkbox, checkbox_label, response):
        if response and not checkbox.is_selected():
            self.driver.execute_script("arguments[0].click();", checkbox)
        elif not response and checkbox.is_selected():
            self.driver.execute_script("arguments[0].click();", checkbox)

    def handle_done_button(self):
        try:
            done_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.artdeco-button.artdeco-button--primary"))
            )
            done_button.click()
            time.sleep(2)
        except TimeoutException:
            self.log_info("Done button not found, skipping to next job.")

    def close_application_modal(self):
        try:
            close_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "button.artdeco-button.artdeco-button--circle.artdeco-button--muted.artdeco-button--2.artdeco-button--tertiary.artdeco-modal__dismiss",
                    )
                )
            )
            close_button.click()
            time.sleep(2)
            self.handle_discard_dialog()
        except TimeoutException:
            self.log_info("Close button not found, skipping to next job.")

    def handle_discard_dialog(self):
        try:
            discard_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[data-control-name='discard_application_confirm_btn']")
                )
            )
            discard_button.click()
            time.sleep(2)
        except TimeoutException:
            self.log_info("Discard button not found, skipping to next job.")


def main():
    parser = argparse.ArgumentParser(description="Easy Apply automation for LinkedIn / Indeed")
    parser.add_argument(
        "--platform",
        choices=["linkedin", "indeed"],
        default="linkedin",
        help="Which job board to automate (default: linkedin)",
    )
    args = parser.parse_args()

    with open("config.json") as config_file:
        data = json.load(config_file)

    if args.platform == "indeed":
        from indeed_bot import EasyApplyIndeed

        bot = EasyApplyIndeed(data)
        bot.login_indeed()
        bot.find_offers()
        bot.close_session()
    else:
        bot = EasyApplyLinkedin(data)
        bot.login_linkedin()
        bot.job_search()
        bot.find_offers()
        bot.close_session()


if __name__ == "__main__":
    main()
