# Automate job search - Linkedin

With this tool you can easily automate the process of searching for jobs on LinkedIn!

## Getting started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

1. Install selenium and beautifulsoup4. I used `anaconda` to install these packages.

`conda create -n <env_name> python=3.11`

`conda install conda-forge::selenium`

`conda install anaconda::beautifulsoup4`

2. Selenium requires a driver to interface with the chosen browser. You will need to setup your Web driver.

I used the Chrome driver, you can download it [here](https://chromedriver.chromium.org/downloads). You can also download [Edge](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/), [Firefox](https://github.com/mozilla/geckodriver/releases) or [Safari](https://webkit.org/blog/6900/webdriver-support-in-safari-10/). Depends on your preferred browser.

Click [here](https://selenium-python.readthedocs.io/locating-elements.html) to check out a very useful document for using Selenium.

Click [here](https://www.youtube.com/watch?v=dz59GsdvUF8) to check out a Youtube Video on how to configure Chrome Driver on a Windows machine.

### Usage

Fork and clone/download the repository and prepare a configuration file.

* Create a json file "data/config.json" and write your LinkedIn login information:
  {"email": "<linkedin_account>", "password": "<password>"}
* Modify the keywords and location in the main.py etc.

Run `python main.py`.

Please feel free to comment or give suggestions/issues.
