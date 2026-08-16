# EasyApply-Linkedin

With this tool, you can easily automate the process of applying for jobs on LinkedIn!

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

1. Install Selenium. Use `pip` to install the Selenium package:
    ```sh
    pip install selenium
    ```

2. Selenium requires a driver to interface with the chosen browser. Make sure the driver is in your path, you will need to add your `driver_path` to the `config.json` file.

    I used the Firefox driver, you can download it [here](https://github.com/mozilla/geckodriver/releases). You can also download drivers for [Chrome](https://sites.google.com/a/chromium.org/chromedriver/downloads), [Edge](https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/), or [Safari](https://webkit.org/blog/6900/webdriver-support-in-safari-10/), depending on your preferred browser.

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/Gabo-Tech/EasyApply-Linkedin.git
    cd EasyApply-Linkedin
    ```

2. Install the necessary packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Update the `config.json` file with your information:
    ```json
    {
        "email": "example@example.com",
        "password": "securePassword123!",
        "keywords": ["Web Developer", "JavaScript", "React"],
        "keywordsToAvoid": ["C++", ".NET"],
        "locations": ["New York", "Los Angeles", "San Francisco"],
        "driver_path": "/usr/local/bin/geckodriver",
        "sortBy": "R",
        "filters": {
            "easy_apply": true,
            "experience": ["Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"],
            "jobType": ["Full-time", "Part-time", "Contract", "Internship", "Temporary"],
            "timePostedRange": ["Any Time", "Last Month", "Past Week", "Past 24 hours"],
            "workplaceType": ["Remote", "Hybrid", "On-site"],
            "less_than_10_applicants": true
        }
    }
    ```

4. Update the location codes in the script:
    ```python
    LOCATION_MAPPING = {
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
        "United Kingdom": "101165590"
    }
    ```
    You can find the code in the `geoId` found in the LinkedIn URL after doing a job search. These are the correct ones if you don't want to search elsewhere, but there are many more.

### Usage

LinkedIn (default):
```sh
python main.py
# or
python main.py --platform linkedin
```

Indeed Switzerland (Easily apply / Indeed Apply):
```sh
python main.py --platform indeed
```

### Features

- **Automated Job Applications**: Automatically apply to jobs that match your keywords and location.
- **LinkedIn Easy Apply** and **Indeed Easily Apply** (ch.indeed.com).
- **Filter Options**: Customize filters for experience level, job type, time posted, workplace type, and more.
- **Logging**: Keep track of errors and the companies you've applied to.
- **Local AI answers**: When a new Easy Apply question appears, a local model suggests an answer from your `aiContext`, past `user_inputs`, and simple rules. You confirm before it is saved.

### Indeed Easily Apply (ch.indeed.com)

The Indeed bot reuses the same answer engine, resumes, and `user_inputs` cache (stored under buckets like `Indeed:Zurich`).

1. Configure the `indeed` block in `config.json` (see `configExample.json`):
```json
"indeed": {
    "enabled": true,
    "baseUrl": "https://ch.indeed.com",
    "locations": ["Zurich", "Zug", "Remote"],
    "filters": {
        "easyApplyOnly": true,
        "fromage": 7,
        "remotejob": true
    }
}
```
2. Optional: refresh live DOM anchors after Indeed UI changes:
```sh
python discover_indeed_selectors.py
```
   Log in when prompted, open an Easily apply flow, and the script updates `indeed_selectors.json` plus snapshots under `.cache/indeed/`.
3. Run:
```sh
python main.py --platform indeed
```

Jobs without the Easily apply / Einfach bewerben badge (external ATS redirects) are skipped. CAPTCHA/login challenges pause for manual resolution.

Selectors live in [`indeed_selectors.json`](indeed_selectors.json) (v2, from live CH DOM):

- Apply button: `#indeedApplyButton` / `data-testid="indeedApplyButton-test"` (label **Apply with Indeed**)
- Easily apply badge: text match `Easily apply` / `Einfach bewerben`
- Continue: `button[data-testid="continue-button"]`
- Resume step: `form[data-testid="resume-selection-form"]` + hidden file input `data-testid="resume-selection-file-resume-radio-card-file-input"`
- Search inputs: `#text-input-what`, `#text-input-where`

Hashed Emotion/mosaic class names are avoided; DE/EN text fallbacks remain.

### Local AI auto-answer

When the bot hits a question that is not already in `user_inputs`, it:

1. Tries an exact (and normalized) cache lookup
2. Tries semantic retrieval over your past answers (`sentence-transformers`)
3. Applies rule-based answers from `aiContext` (years of experience, contact info, visa, salary, etc.)
4. Asks **Ollama** (primary) to generate a short, plain answer
5. Falls back to a local **transformers** model if Ollama is unavailable
6. Shows the suggestion and asks you to **[Y]es / [e]dit / [m]anual** before saving

File uploads are never guessed by AI; those stay manual.

#### Ollama setup (recommended)

```sh
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b-instruct
```

Keep the Ollama server running (`ollama serve` if it is not already a service). The bot talks to `http://localhost:11434` by default.

#### `aiSettings` in `config.json`

Copy the `aiSettings` block from `configExample.json`, or use:

```json
"aiSettings": {
    "enabled": true,
    "primary": "ollama",
    "ollama": {
        "baseUrl": "http://localhost:11434",
        "model": "qwen2.5:3b-instruct",
        "timeoutSeconds": 30
    },
    "fallback": {
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "device": "auto"
    },
    "retrieval": {
        "embeddingModel": "sentence-transformers/all-MiniLM-L6-v2",
        "similarityThreshold": 0.85
    },
    "defaults": {
        "salaryExpectationUsd": "90000",
        "hourlyRateRange": "40-60",
        "requiresSponsorship": true,
        "willingToRelocate": true
    },
    "style": {
        "maxWords": 40,
        "forbiddenPatterns": ["—", "Furthermore", "I am excited", "I am passionate"]
    }
}
```

Also keep `aiContext` filled with your profile (experience, skills, languages, preferences). That data plus your growing `user_inputs` history is what makes answers sound like you.

#### Language-aware CVs

Put both resumes under `resumes/` and configure:

```json
"resumes": {
    "en": "resumes/Resume_Gabriel_Clemente.pdf",
    "de": "resumes/Lebenslauf_Gabriel_Clemente.pdf",
    "default": "en"
}
```

When an Easy Apply form asks for a resume/CV/Lebenslauf, the bot detects whether the application is German or English (from the form/job text) and attaches the matching file. If unsure, it uses English.

Set `"enabled": false` to fall back to the old fully manual prompts.

Embedding vectors are cached under `.cache/embeddings.pkl` so startup stays fast after the first run.

### Customization

You can customize the job search and application process by editing the `config.json` file:
- **email**: Your LinkedIn email address.
- **password**: Your LinkedIn password.
- **keywords**: Keywords for finding specific job titles (e.g., "Machine Learning Engineer", "Data Scientist").
- **keywordsToAvoid**: Keywords to exclude from your search.
- **locations**: Locations where you are currently looking for a position.
- **driver_path**: Path to your downloaded WebDriver.
- **sortBy**: Sort order for job listings.
- **filters**: Various filters to narrow down the job search (e.g., easy apply, experience level, job type, etc.).
- **aiContext**: Your CV-style profile used by the local answer engine.
- **aiSettings**: Local AI model, retrieval, and answer-style settings.
- **user_inputs**: Cached answers to application questions (filled manually or after you confirm an AI suggestion).
- **indeed**: Indeed CH base URL, locations, and Easily apply filters.
- **resumes**: Paths to English/German CV PDFs.

### Testing

#### Unit Tests

Unit tests mock the Selenium WebDriver to test methods in isolation without making actual web requests.

Run the unit tests:
```bash
python unit_tests.py
```

Answer-engine tests (retrieval, rules, sanitizer, mocked Ollama/transformers):
```bash
python test_answer_engine.py
```

Indeed helper tests (URL builder, Easily apply detection, tab switching):
```bash
python test_indeed_bot.py
```

#### E2E Tests

End-to-end tests using `pytest` and `selenium` require an actual web browser to run.

Run the E2E tests:
```bash
pytest e2e_tests.py
```

### Contributing

Please feel free to comment or give suggestions/issues. Fork and submit pull requests for any enhancements or bug fixes.

### License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Gabo-Tech/EasyApply-Linkedin/blob/master/LICENCE) file for details.