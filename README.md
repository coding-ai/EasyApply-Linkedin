# EasyApply-Linkedin

With this tool you can easily automate the process of applying for jobs on LinkedIn!

## Getting started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

1. Install selenium. I used `pip` to install the selenium package.

`pip install selenium`

2. Selenium requires a driver to interface with the chosen browser. Make sure the driver is in your path, you will need to add your `driver_path` to the `config.json` file.

I used the Chrome driver, you can download it [here](https://sites.google.com/a/chromium.org/chromedriver/downloads). You can also download [Edge](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/), [Firefox](https://github.com/mozilla/geckodriver/releases) or [Safari](https://webkit.org/blog/6900/webdriver-support-in-safari-10/). Depends on your preferred browser.

### Usage

Fork and clone/download the repository and change the configuration file with:

* Your email linked to LinkedIn.
* Your password.
* Keywords for finding specific job titles fx. Machine Learning Engineer, Data Scientist, etc.
* The location where you are currently looking for a position.
* The driver path to your downloaded webdriver.

Run `python main.py`.

Please feel free to comment or give suggestions/issues.
