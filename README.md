# Automate job search - Linkedin

With this tool you can easily automate the process of searching for jobs on LinkedIn!

## Getting started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

1. Install selenium and beautifulsoup4. I used `anaconda` to install these packages.

`conda create -n <env_name> python=3.11`
`conda install conda-forge::selenium`
`conda install anaconda::beautifulsoup4`

2. Selenium requires a driver to interface with the chosen browser. Make sure the driver is in your path, you will need to add your `driver_path` to the `config.json` file.

I used the Chrome driver, you can download it [here](https://chromedriver.chromium.org/downloads). You can also download [Edge](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/), [Firefox](https://github.com/mozilla/geckodriver/releases) or [Safari](https://webkit.org/blog/6900/webdriver-support-in-safari-10/). Depends on your preferred browser.

Click [here](https://selenium-python.readthedocs.io/locating-elements.html) to check out a very useful document for using Selenium.

### Usage

Fork and clone/download the repository and change the configuration file with:

* Your email linked to LinkedIn.
* Your password.
* Keywords for finding specific job titles fx. Machine Learning Engineer, Data Scientist, etc.
* The location where you are currently looking for a position.
* The driver path to your downloaded webdriver.

Run `python main.py`.

Please feel free to comment or give suggestions/issues.
