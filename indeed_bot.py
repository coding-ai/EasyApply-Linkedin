"""Indeed Apply (Easily apply) automation for ch.indeed.com."""

from __future__ import annotations

import json
import random
import time
import urllib.parse
from pathlib import Path

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from answer_engine import detect_application_language, resolve_resume_path
from base_easy_apply import BaseEasyApply

SELECTORS_PATH = Path("indeed_selectors.json")


def _human_delay(a=1.2, b=2.8):
    time.sleep(random.uniform(a, b))


class EasyApplyIndeed(BaseEasyApply):
    def __init__(self, data):
        indeed_cfg = data.get("indeed") or {}
        # Prefer Indeed-specific locations/credentials when present
        merged = dict(data)
        if indeed_cfg.get("email"):
            merged["email"] = indeed_cfg["email"]
        if indeed_cfg.get("password"):
            merged["password"] = indeed_cfg["password"]

        super().__init__(merged, start_driver=True)

        self.indeed_cfg = indeed_cfg
        self.base_url = (indeed_cfg.get("baseUrl") or "https://ch.indeed.com").rstrip("/")
        self.locations = indeed_cfg.get("locations") or ["Zurich"]
        self.indeed_filters = indeed_cfg.get("filters") or {}
        self.current_location_index = 0
        self.search_window = None
        self.selectors = self._load_selectors()

        # Ensure Indeed answer bucket exists
        if "Indeed" not in self.context_data["user_inputs"]:
            self.context_data["user_inputs"]["Indeed"] = {}

    def _load_selectors(self):
        if SELECTORS_PATH.exists():
            try:
                return json.loads(SELECTORS_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                self.log_info(f"Could not load indeed_selectors.json: {e}")
        return {}

    def _current_answer_bucket(self):
        loc = self.locations[self.current_location_index] if self.locations else "Zurich"
        return f"Indeed:{loc}"

    # ------------------------------------------------------------------
    # Login / URL
    # ------------------------------------------------------------------

    def login_indeed(self):
        try:
            self.driver.get(f"{self.base_url}/")
            _human_delay(2, 3)
            # Try account login page
            try:
                self.driver.get(f"{self.base_url}/account/login")
                _human_delay(1, 2)
            except Exception:
                pass

            email_sels = (self.selectors.get("login") or {}).get("email") or [
                "input[type='email']",
                "input#login-email-input",
            ]
            password_sels = (self.selectors.get("login") or {}).get("password") or [
                "input[type='password']",
            ]

            email_el = self._find_first(email_sels, timeout=8)
            if email_el:
                email_el.clear()
                email_el.send_keys(self.email)
                _human_delay(0.5, 1)
                # Indeed sometimes has two-step email then password
                submit = self._find_first(
                    (self.selectors.get("login") or {}).get("submit") or ["button[type='submit']"],
                    timeout=3,
                )
                if submit:
                    try:
                        submit.click()
                        _human_delay(1, 2)
                    except Exception:
                        pass

            pass_el = self._find_first(password_sels, timeout=8)
            if pass_el:
                pass_el.clear()
                pass_el.send_keys(self.password)
                pass_el.send_keys(Keys.RETURN)
                _human_delay(2, 4)

            if self._looks_like_captcha():
                self.handle_captcha()

            self.log_info("Indeed login step finished (verify manually if prompted).")
            input("If login/CAPTCHA is complete, press Enter to continue job search...")
            self.search_window = self.driver.current_window_handle
        except Exception as e:
            self.log_error(f"Indeed login error: {e}")
            input("Resolve login manually in the browser, then press Enter...")
            self.search_window = self.driver.current_window_handle

    def construct_url(self, start=0):
        location = self.locations[self.current_location_index]
        # Indeed uses spaces / OR differently; join keywords with OR for boolean
        q_parts = list(self.keywords_list)
        if self.keywords_to_avoid_list:
            # Indeed supports -term exclusion
            q_parts += [f"-{k}" for k in self.keywords_to_avoid_list]
        query = " OR ".join(q_parts) if len(self.keywords_list) > 1 else (self.keywords_list[0] if self.keywords_list else "")

        params = {
            "q": query,
            "l": location,
        }
        if self.indeed_filters.get("easyApplyOnly", True):
            params["iafilter"] = "1"
        fromage = self.indeed_filters.get("fromage")
        if fromage:
            params["fromage"] = str(fromage)
        if self.indeed_filters.get("remotejob"):
            params["remotejob"] = "1"
        if start:
            params["start"] = str(start)

        return f"{self.base_url}/jobs?{urllib.parse.urlencode(params)}"

    # ------------------------------------------------------------------
    # Search / apply loop
    # ------------------------------------------------------------------

    def find_offers(self):
        self.apply_filtered_jobs()

    def apply_filtered_jobs(self):
        while self.current_location_index < len(self.locations):
            start = 0
            empty_pages = 0
            while empty_pages < 2:
                url = self.construct_url(start=start)
                self.log_info(f"Opening Indeed search: {url}")
                self._focus_search_window()
                self.driver.get(url)
                _human_delay(3, 5)

                if self._looks_like_captcha():
                    self.handle_captcha()

                if self.check_no_results():
                    self.log_info(
                        f"No matching Indeed jobs in {self.locations[self.current_location_index]}."
                    )
                    empty_pages += 1
                    break

                cards = self._get_job_cards()
                if not cards:
                    self.log_info("No job cards found on page.")
                    empty_pages += 1
                    start += 10
                    continue

                empty_pages = 0
                for index in range(len(cards)):
                    try:
                        self._focus_search_window()
                        cards = self._get_job_cards()
                        if index >= len(cards):
                            break
                        card = cards[index]
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
                        _human_delay(0.8, 1.5)

                        if not self._card_has_easily_apply(card):
                            self.log_info("Skipping job without Easily apply badge.")
                            continue

                        company = self.get_company_name(card)
                        job_key = self._card_job_key(card)
                        applied_id = company or (f"indeed:{job_key}" if job_key else None)
                        if applied_id and applied_id in self.applied_companies:
                            self.log_info(f"Already applied at {applied_id}, skipping...")
                            continue

                        try:
                            link = self._find_in(card, (self.selectors.get("search") or {}).get("jobLink") or [])
                            if link:
                                self.driver.execute_script("arguments[0].click();", link)
                            else:
                                self.driver.execute_script("arguments[0].click();", card)
                        except ElementClickInterceptedException:
                            continue
                        _human_delay(1.5, 2.5)

                        if not self.is_indeed_apply():
                            self.log_info("Not an Indeed Apply listing (external ATS), skipping...")
                            self.close_application(try_exit=False)
                            continue

                        try:
                            self.handle_indeed_apply()
                            self.log_applied_company(
                                applied_id or f"indeed-job-{self.current_location_index}-{start}-{index}"
                            )
                        except Exception as e:
                            self.log_info(f"Failed Indeed apply at {company}: {e}")
                            self.log_failed_application(applied_id or company or "unknown")
                            self.close_application()
                    except (StaleElementReferenceException, NoSuchElementException) as e:
                        self.log_info(f"Card interaction error: {e}")
                        continue
                    except Exception as e:
                        self.log_error(f"Indeed apply loop error: {e}")
                        self.close_application()
                        continue

                start += 10
                if not self._has_next_page():
                    break

            self.current_location_index += 1

    def check_no_results(self):
        for sel in (self.selectors.get("search") or {}).get("noResults") or []:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return True
            except NoSuchElementException:
                continue
        # Heuristic: zero job cards
        return len(self._get_job_cards()) == 0 and "jobs" in self.driver.current_url

    def _get_job_cards(self):
        for sel in (self.selectors.get("search") or {}).get("jobCard") or [
            "div.job_seen_beacon",
            "div[data-jk]",
        ]:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if cards:
                    return cards
            except Exception:
                continue
        return []

    def _card_has_easily_apply(self, card):
        texts = (self.selectors.get("search") or {}).get("easilyApplyBadgeTexts") or [
            "Easily apply",
            "Einfach bewerben",
        ]
        try:
            body = (card.text or "").lower()
            return any(t.lower() in body for t in texts)
        except Exception:
            return False

    def _card_job_key(self, card):
        attr = (self.selectors.get("search") or {}).get("jobKeyAttribute") or "data-jk"
        try:
            key = (card.get_attribute(attr) or "").strip()
            if key:
                return key
        except Exception:
            pass
        try:
            el = card.find_element(By.CSS_SELECTOR, f"[{attr}]")
            return (el.get_attribute(attr) or "").strip() or None
        except Exception:
            return None

    def get_company_name(self, job_item):
        for sel in (self.selectors.get("search") or {}).get("companyName") or [
            "[data-testid='company-name']",
            "span.companyName",
        ]:
            try:
                el = job_item.find_element(By.CSS_SELECTOR, sel)
                name = (el.text or "").strip()
                if name:
                    return name
            except NoSuchElementException:
                continue
        return None

    def is_indeed_apply(self):
        """Return True when Apply with Indeed widget/button is present (not external ATS)."""
        apply_cfg = self.selectors.get("apply") or {}
        for sel in apply_cfg.get("applyWidget") or [
            "span[data-testid='indeed-apply-widget']",
            "#indeedApplyButton",
            ".jobsearch-IndeedApplyButton",
        ]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed() or sel.startswith("span"):
                    return True
            except Exception:
                continue
        page = (self.driver.page_source or "")[:50000].lower()
        if "indeedapplybutton" in page or "indeed-apply-widget" in page or "ia-basepage" in page:
            return True
        if "indeed.com" in (self.driver.current_url or ""):
            btn = self._find_button_by_texts(
                apply_cfg.get("applyButtonTexts") or ["Apply with Indeed", "Apply", "Bewerben"]
            )
            return btn is not None
        return False

    # ------------------------------------------------------------------
    # Apply wizard
    # ------------------------------------------------------------------

    def handle_indeed_apply(self):
        original_handles = list(self.driver.window_handles)
        apply_cfg = self.selectors.get("apply") or {}
        # Prefer stable IDs from live CH DOM
        apply_btn = self._find_first(
            apply_cfg.get("applyButton") or [
                "#indeedApplyButton",
                "button[data-testid='indeedApplyButton-test']",
            ],
            timeout=5,
        )
        if apply_btn is None:
            apply_btn = self._find_button_by_texts(
                apply_cfg.get("applyButtonTexts") or [
                    "Apply with Indeed",
                    "Apply now",
                    "Apply",
                    "Bewerben",
                ]
            )
        if apply_btn is None:
            raise NoSuchElementException("Indeed Apply button not found")

        try:
            self.driver.execute_script("arguments[0].click();", apply_btn)
        except Exception:
            apply_btn.click()
        _human_delay(2, 3.5)

        # Switch to new tab if opened ("opens in a new tab")
        WebDriverWait(self.driver, 8).until(
            lambda d: len(d.window_handles) >= len(original_handles)
        )
        if len(self.driver.window_handles) > len(original_handles):
            self.driver.switch_to.window(self.driver.window_handles[-1])
            _human_delay(1, 2)

        if "indeed.com" not in (self.driver.current_url or ""):
            raise RuntimeError(f"Redirected off Indeed: {self.driver.current_url}")

        # Wait for apply wizard shell (resume step or continue) before filling
        wizard_ready = self._find_first_any(
            (apply_cfg.get("modalOrContainer") or [])
            + (apply_cfg.get("resume") or {}).get("form", [])
            + (apply_cfg.get("continueButton") or [])
            + [
                ".ia-BasePage",
                "form[data-testid='resume-selection-form']",
                "button[data-testid='continue-button']",
            ],
            require_displayed=False,
            timeout=12,
        )
        if wizard_ready is None:
            self.log_info("Apply wizard shell not detected quickly; continuing anyway.")

        steps = 0
        max_steps = 20
        while steps < max_steps:
            steps += 1
            _human_delay(1, 2)
            self.fill_indeed_form()

            if self._click_submit_if_present():
                self.log_info("Indeed application submitted.")
                _human_delay(1.5, 2.5)
                self.close_application(try_exit=False)
                return

            if not self._click_continue():
                if self._application_complete():
                    self.log_info("Indeed application appears complete.")
                    self.close_application(try_exit=False)
                    return
                raise RuntimeError("Could not find Continue/Submit on Indeed apply wizard")

        raise RuntimeError("Indeed apply wizard exceeded max steps")

    def fill_indeed_form(self):
        # Resume selection step (mosaic module) — handle before generic questions
        if self._handle_resume_selection_step():
            return

        question_sels = (self.selectors.get("apply") or {}).get("questionItem") or [
            ".ia-Questions-item",
            "[class*='ia-Questions-item']",
        ]
        questions = []
        for sel in question_sels:
            try:
                questions = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if questions:
                    break
            except Exception:
                continue

        if not questions:
            self._fill_loose_fields()
            return

        for item in questions:
            try:
                label_text = self._question_label(item)
                if not label_text:
                    continue

                file_inputs = item.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    path = self.get_file_response_for_label(label_text)
                    file_inputs[0].send_keys(path)
                    _human_delay(0.5, 1)
                    continue

                selects = item.find_elements(By.CSS_SELECTOR, "select")
                if selects:
                    options = [
                        o.text.strip()
                        for o in selects[0].find_elements(By.TAG_NAME, "option")
                        if o.text.strip() and o.get_attribute("value") not in ("", "-1", "Select")
                    ]
                    if options:
                        answer = self.get_radio_response_for_label(label_text, options)
                        Select(selects[0]).select_by_visible_text(answer)
                    continue

                radios = item.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if radios:
                    options = []
                    for radio in radios:
                        opt = self._radio_label(radio)
                        if opt:
                            options.append(opt)
                    if options:
                        answer = self.get_radio_response_for_label(label_text, options)
                        for radio in radios:
                            if self._radio_label(radio).lower() == str(answer).lower():
                                self.driver.execute_script("arguments[0].click();", radio)
                                break
                    continue

                checkboxes = item.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                if checkboxes:
                    for cb in checkboxes:
                        cb_label = self._radio_label(cb) or label_text
                        response = self.get_checkbox_response_for_label(cb_label)
                        if response and not cb.is_selected():
                            self.driver.execute_script("arguments[0].click();", cb)
                        elif not response and cb.is_selected():
                            self.driver.execute_script("arguments[0].click();", cb)
                    continue

                text_fields = item.find_elements(
                    By.CSS_SELECTOR, "textarea, input[type='text'], input:not([type])"
                )
                if text_fields:
                    field = text_fields[0]
                    if (field.get_attribute("value") or "").strip():
                        continue
                    answer = self.get_response_for_label(label_text)
                    field.clear()
                    field.send_keys(str(answer))
                    continue
            except StaleElementReferenceException:
                continue
            except Exception as e:
                self.log_info(f"Indeed form field error: {e}")
                continue

    def _desired_resume_path(self):
        app_text = self._gather_application_text("resume")
        lang = detect_application_language(app_text)
        return resolve_resume_path(self.context_data, lang)

    def _configured_resume_names(self):
        names = []
        resumes = self.context_data.get("resumes") or {}
        for key in ("en", "de"):
            path = resumes.get(key)
            if path:
                names.append(Path(path).name)
        return names

    def _handle_resume_selection_step(self):
        """Handle mosaic resume-selection form from live CH DOM. Returns True if handled."""
        resume_cfg = ((self.selectors.get("apply") or {}).get("resume") or {})
        form_sels = resume_cfg.get("form") or ["form[data-testid='resume-selection-form']"]
        form = None
        for sel in form_sels:
            try:
                form = self.driver.find_element(By.CSS_SELECTOR, sel)
                if form:
                    break
            except Exception:
                continue
        if form is None:
            return False

        desired = self._desired_resume_path()
        desired_name = Path(desired).name if desired else None
        configured_names = {n.lower() for n in self._configured_resume_names()}

        # Prefer already-uploaded resume only when filename matches the desired CV
        label_sels = resume_cfg.get("existingLabel") or [
            "label[data-testid='resume-selection-file-resume-radio-card-label']"
        ]
        radio_sels = resume_cfg.get("existingRadio") or [
            "input[data-testid='resume-selection-file-resume-radio-card-input']"
        ]
        matched_existing = False
        for sel in label_sels:
            try:
                label = self.driver.find_element(By.CSS_SELECTOR, sel)
                label_l = (label.text or "").strip().lower()
                if desired_name and desired_name.lower() in label_l:
                    matched_existing = True
                    break
                # Other profile CV (wrong language / stale file) → upload desired below
                if any(name in label_l for name in configured_names):
                    break
            except Exception:
                continue

        if matched_existing:
            for sel in radio_sels:
                try:
                    radio = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if not radio.is_selected():
                        self.driver.execute_script("arguments[0].click();", radio)
                    self.log_info(f"Using existing Indeed resume selection ({desired_name}).")
                    return True
                except Exception:
                    continue
            return True

        # Upload configured local CV via hidden file input
        if not desired:
            self.log_info("No configured resume path; leaving Indeed resume selection as-is.")
            return True

        file_sels = resume_cfg.get("fileInput") or [
            "input[data-testid='resume-selection-file-resume-radio-card-file-input']"
        ]
        file_input = self._find_first_any(file_sels, require_displayed=False, timeout=3)

        if file_input is None:
            # Open Resume options -> Upload a different file
            for sel in resume_cfg.get("optionsMenu") or ["button[data-testid='ResumeOptionsMenu']"]:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, sel).click()
                    _human_delay(0.4, 0.8)
                    break
                except Exception:
                    continue
            for sel in resume_cfg.get("uploadDifferent") or [
                "button[data-testid='ResumeOptionsMenu-upload']"
            ]:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, sel).click()
                    _human_delay(0.4, 0.8)
                    break
                except Exception:
                    continue
            file_input = self._find_first_any(file_sels, require_displayed=False, timeout=3)

        if file_input is None:
            # Last resort: any file input in form
            try:
                file_input = form.find_element(By.CSS_SELECTOR, "input[type='file']")
            except Exception:
                file_input = None

        if file_input is not None:
            self.log_info(f"Uploading resume to Indeed: {desired}")
            file_input.send_keys(desired)
            _human_delay(1, 2)
            return True

        self.log_info("Resume selection form found but no file input; continuing with profile default.")
        return True

    def _fill_loose_fields(self):
        """Fallback when question items are not found — fill empty inputs / file."""
        if self._handle_resume_selection_step():
            return
        try:
            for file_input in self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']"):
                path = self.get_file_response_for_label("Resume / Lebenslauf")
                file_input.send_keys(path)
                _human_delay(0.5, 1)
                break
        except Exception:
            pass

    def _question_label(self, item):
        for sel in ["label", "legend", "[class*='Question']", "span", "div"]:
            try:
                els = item.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    text = (el.text or "").strip()
                    if text and len(text) < 500:
                        return text.split("\n")[0].strip()
            except Exception:
                continue
        return (item.text or "").split("\n")[0].strip()

    def _radio_label(self, radio):
        try:
            rid = radio.get_attribute("id")
            if rid:
                lab = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                return (lab.text or "").strip()
        except Exception:
            pass
        try:
            return radio.find_element(By.XPATH, "./following-sibling::label").text.strip()
        except Exception:
            return (radio.get_attribute("value") or "").strip()

    def _click_continue(self):
        # Prefer stable data-testid; ignore duplicate hp-continue-button-* stubs
        btn = self._find_first(
            (self.selectors.get("apply") or {}).get("continueButton") or [
                "button[data-testid='continue-button']",
                "button.ia-continueButton",
            ],
            timeout=3,
        )
        if btn is None:
            texts = (self.selectors.get("apply") or {}).get("continueButtonTexts") or [
                "Continue",
                "Weiter",
            ]
            btn = self._find_button_by_texts(texts)
            # Avoid clicking hp-continue-button-* duplicates when possible
            if btn is not None:
                testid = (btn.get_attribute("data-testid") or "")
                if testid.startswith("hp-continue-button"):
                    prefer = self._find_first(
                        ["button[data-testid='continue-button']"], timeout=1
                    )
                    if prefer is not None:
                        btn = prefer
        if btn is None:
            return False
        try:
            self.driver.execute_script("arguments[0].click();", btn)
        except Exception:
            try:
                btn.click()
            except Exception:
                return False
        _human_delay(1.5, 2.5)
        return True

    def _click_submit_if_present(self):
        texts = (self.selectors.get("apply") or {}).get("submitButtonTexts") or [
            "Submit",
            "Submit your application",
            "Absenden",
            "Bewerbung absenden",
        ]
        btn = self._find_button_by_texts(texts)
        if btn is None:
            return False
        label = (
            (btn.text or "")
            + " "
            + (btn.get_attribute("aria-label") or "")
            + " "
            + (btn.get_attribute("value") or "")
        ).strip().lower()
        # Avoid treating generic "Continue" as submit unless text matches submit list
        submit_l = [t.lower() for t in texts]
        if not any(t in label for t in submit_l):
            return False
        # Never submit via continue stubs
        testid = (btn.get_attribute("data-testid") or "")
        if testid in ("continue-button",) or testid.startswith("hp-continue-button"):
            return False
        try:
            self.driver.execute_script("arguments[0].click();", btn)
        except Exception:
            btn.click()
        return True

    def _application_complete(self):
        body = (self.driver.page_source or "").lower()
        markers = [
            "application submitted",
            "bewerbung gesendet",
            "your application has been submitted",
            "danke für ihre bewerbung",
            "thank you for applying",
        ]
        return any(m in body for m in markers)

    def close_application(self, try_exit=True):
        try:
            # Prefer Save and close when discarding an in-progress wizard
            if try_exit:
                exit_sels = (self.selectors.get("apply") or {}).get("exitButton") or (
                    self.selectors.get("apply") or {}
                ).get("closeButton") or []
                for sel in exit_sels:
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if el.is_displayed():
                            self.driver.execute_script("arguments[0].click();", el)
                            _human_delay(0.8, 1.5)
                            break
                    except Exception:
                        continue

            if len(self.driver.window_handles) > 1:
                self.driver.close()
                remaining = self.driver.window_handles
                target = self.search_window if self.search_window in remaining else remaining[0]
                self.driver.switch_to.window(target)
        except Exception as e:
            self.log_info(f"close_application: {e}")
        finally:
            self._focus_search_window()

    def _focus_search_window(self):
        try:
            if self.search_window and self.search_window in self.driver.window_handles:
                self.driver.switch_to.window(self.search_window)
            elif self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[0])
                self.search_window = self.driver.current_window_handle
        except Exception:
            pass

    def _has_next_page(self):
        for sel in (self.selectors.get("search") or {}).get("paginationNext") or []:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed() and el.get_attribute("aria-disabled") != "true":
                    return True
            except NoSuchElementException:
                continue
        return False

    def _gather_application_text(self, label_text=""):
        chunks = [label_text or ""]
        try:
            chunks.append((self.driver.title or ""))
            chunks.append((self.driver.page_source or "")[:3000])
        except Exception:
            pass
        return "\n".join(chunks)

    # ------------------------------------------------------------------
    # Element helpers
    # ------------------------------------------------------------------

    def _find_first(self, selectors, timeout=5):
        return self._find_first_any(selectors, require_displayed=True, timeout=timeout)

    def _find_first_any(self, selectors, require_displayed=True, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            for sel in selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if not require_displayed or el.is_displayed():
                        return el
                except Exception:
                    continue
            time.sleep(0.3)
        return None

    def _find_in(self, root, selectors):
        for sel in selectors:
            try:
                return root.find_element(By.CSS_SELECTOR, sel)
            except Exception:
                continue
        return None

    def _find_button_by_texts(self, texts):
        lowered = [t.lower() for t in texts]
        try:
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button, a[role='button'], input[type='submit']")
        except Exception:
            return None
        for btn in buttons:
            try:
                if not btn.is_displayed():
                    continue
                label = ((btn.text or "") + " " + (btn.get_attribute("aria-label") or "")).strip().lower()
                value = (btn.get_attribute("value") or "").lower()
                combined = f"{label} {value}"
                if any(t in combined for t in lowered):
                    return btn
            except StaleElementReferenceException:
                continue
        return None

    def _looks_like_captcha(self):
        src = (self.driver.page_source or "").lower()
        return any(
            token in src
            for token in ("captcha", "cf-challenge", "challenge-platform", "verify you are human")
        )
