# import of webdriver and Keys classes from Selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.common.action_chains import ActionChains


# create an instance of Chrome with the path of the driver
driver = webdriver.Chrome('C:/coding-ai/chromedriver')

# use the get method to load a website
driver.get("https://www.linkedin.com/login")

# access the textual title of the page
# print('You are (automatically) accessing the website: ', driver.title)

# search_bar = driver.find_element_by_name('q')
# search_bar.clear()
# search_bar.send_keys("getting started with python")
# search_bar.send_keys(Keys.RETURN)

# entering credentials and login in
email = driver.find_element_by_name('session_key')
email.clear()
email.send_keys('cuchacoifman@gmail.com')

password = driver.find_element_by_name('session_password')
password.clear()
password.send_keys('Caracas4763')

password.send_keys(Keys.RETURN)

# confirm the current URL
#print('Current URL: ', driver.current_url)

time.sleep(10)

jobs_link = driver.find_element_by_link_text('Jobs')
jobs_link.click()

search_job = driver.find_element_by_css_selector(".jobs-search-box__text-input[aria-label='Search jobs']")
search_job.clear()
search_job.send_keys('machine learning')

search_location = driver.find_element_by_css_selector(".jobs-search-box__text-input[aria-label='Search location']")
search_location.clear()
search_location.send_keys('United States')
search_location.send_keys(Keys.RETURN)

time.sleep(5)

# wait = WebDriverWait(driver,10)
# element = EC.element_to_be_clickable((By.XPATH,"//*[@data-control-name='all-filters']"))
# all_filters = driver.find_element_by_class_name('search-s-facet__values.search-s-facet__values--is-floating.search-s-facet__values--f_LF.container-with-shadow')
# all_filters = driver.find_element_by_link_text('Easy Apply')7


all_filters = driver.find_element_by_xpath("//button[@data-control-name='all_filters']")
# actions = ActionChains(driver)
# actions.move_to_element(all_filters).perform()
# driver.execute_script('arguments[0].click();',all_filters)
all_filters.click()

time.sleep(2)

easy_apply = driver.find_element_by_xpath("//label[@for='f_LF-f_AL']")
time.sleep(5)
easy_apply.click()

apply = driver.find_element_by_xpath("//button[@data-control-name='all_filters_apply']")
time.sleep(2)
apply.click()

find_pages = driver.find_elements_by_class_name("artdeco-pagination__indicator.artdeco-pagination__indicator--number")
# print(find_pages)
time.sleep(2)
# total_pages = find_pages[len(find_pages)-1].text
# scroller = driver.find_element_by_class_name('jobs-search-results__list.artdeco-list')
# driver.execute_script("arguments[0].scrollIntoView();",scroller)
# time.sleep(2)
# target = driver.find_element_by_link_text('LinkedIn Corporation © 2020')
# actions = ActionChains(driver)
# actions.move_to_element(target)
# actions.perform()
# driver.find_elements_by_class_name('jobs-search-results__list.artdeco-list').send_keys(Keys.END)
# driver.maximize_window()
# wait = WebDriverWait(driver,10)
# wait.until(EC.visibility_of_element_located((By.CLASS_NAME,"occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")))
# results = driver.find_elements_by_class_name("occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")
# wait.until(EC.visibility_of_element_located((By.
# CLASS_NAME,"job-card-search__title.artdeco-entity-lockup__title.ember-view")))
results = driver.find_elements_by_class_name("occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")
# last_result = driver.find_elements_by_class_name("//div[contains(@class,'job-card-search--two-pane.jobs-search-results__list--card-viewport-tracking-')]")
for result in results:
    hover = ActionChains(driver).move_to_element(result)
    hover.perform()
    titles = result.find_elements_by_class_name('job-card-search__title.artdeco-entity-lockup__title.ember-view')
    for title in titles:
        print('You are applying to the position of: ', title.text)
        title.click()
        time.sleep(2)
        in_apply = driver.find_element_by_xpath("//button[@data-control-name='jobdetails_topcard_inapply']")
        print(in_apply.text)
        # here comes the "click" to easy apply
        time.sleep(2)
    # # for title in titles:
    # #     print(title.text)
    # #     title.click()
    # #     i=i+1
    # print(titles.text)
# print(len(last_result))


# find_offers = driver.find_elements_by_class_name("occludable-update.artdeco-list__item--offset-4.artdeco-list__item.p0.ember-view")
# print(find_offers)
# for offer in find_offers:
#     titles = offer.find_elements_by_class_name('job-card-search__title.artdeco-entity-lockup__title.ember-view')
#     for title in titles:
#         print(title.text)
    # print(offer.text)
    # print(type(offer.text))
    # print('\n\n\n')
# print(find_pages[len(find_pages)-1].text)

# all_filters = driver.find_element_by_xpath(".//*[@id='f_LF-f_AL']")
# actions = ActionChains(driver)
# actions.move_to_element(all_filters).click().perform()

# all_filters.click()
# all_filters =WebDriverWait(driver,20).until(EC.element_to_be_clickable((By.ID,"f_LF-f_AL"))).click()
# driver.implicitly_wait(10)
# time.sleep(2)
# all_filters.click()
# actions = ActionChains(driver)
# actions.move_to_element(all_filters).click().perform()

# try:
#     element = WebDriverWait(driver, 10).until(
#         EC.presence_of_element_located((By.XPATH, "//button[@data-control-name='all-filters']"))
#     )
# finally:
#     driver.quit()

# close current session
# driver.close()
