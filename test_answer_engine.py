"""Unit tests for answer_engine — no real LLM or network calls."""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from answer_engine import (
    AnswerEngine,
    coerce_checkbox_answer,
    flatten_user_inputs,
    fuzzy_match_option,
    normalize_label,
    sanitize_answer,
)


SAMPLE_CONTEXT = {
    "aiContext": {
        "user_data": {
            "linkedin_url": "https://www.linkedin.com/in/bugslayer",
            "phone": "+34 622480234",
            "email": "sendmessage@gabo.email",
            "address": "Albal, Valencia, Spain",
            "currentLocation": "Valencia, Spain",
        },
        "languagesSpokenByUser": {
            "English": "Native",
            "Spanish": "Native",
        },
        "preferences": {
            "workplaceType": "Remote",
            "jobType": "Contract",
            "willingToRelocate": True,
        },
        "experience": [
            {
                "title": "Full-Stack TypeScript Software Engineer",
                "description": "Built apps with Node and Angular",
                "date": "Nov 2022 - Apr 2024",
                "company": "Beyondbmi",
                "skills": ["TypeScript", "Node.js", "Angular", "React"],
            },
            {
                "title": "Full Stack Engineer",
                "description": "Various projects",
                "date": "Oct 2021 - Apr 2024",
                "company": "GABO",
                "skills": ["TypeScript", "Node.js", "React.js", "Express.js"],
            },
        ],
        "skills": ["TypeScript", "JavaScript", "Angular", "React", "Node.js", "Express.js"],
    },
    "user_inputs": {
        "United Kingdom": {
            "City\nCity": "Valencia, Valencian Community, Spain",
            "How many years of work experience do you have with Node.js?": "4",
            "How many years of work experience do you have with React?": "3",
            "What are your salary expectations?": "90000",
            "Will you now or in the future require sponsorship for employment visa status?\nWill you now or in the future require sponsorship for employment visa status?\nRequired": "Yes",
            "I Agree Terms & Conditions": True,
            "LinkedIn": True,
        },
        "United States": {
            "How many years of work experience do you have with Express.js?": "4",
            "Are you legally authorized to work in the United States?\nAre you legally authorized to work in the United States?\nRequired": "No",
        },
    },
    "aiSettings": {
        "enabled": True,
        "primary": "ollama",
        "retrieval": {"similarityThreshold": 0.85},
        "defaults": {
            "salaryExpectationUsd": "90000",
            "hourlyRateRange": "40-60",
            "requiresSponsorship": True,
            "willingToRelocate": True,
        },
        "style": {
            "maxWords": 40,
            "forbiddenPatterns": ["—", "Furthermore", "I am excited", "I am passionate"],
        },
    },
}


class TestNormalizeAndSanitize(unittest.TestCase):
    def test_normalize_duplicate_city_label(self):
        self.assertEqual(normalize_label("City\nCity"), "City")

    def test_normalize_strips_required(self):
        self.assertEqual(
            normalize_label("Are you authorized?\nAre you authorized?\nRequired"),
            "Are you authorized?",
        )

    def test_sanitize_strips_em_dash_and_markdown(self):
        raw = "I am excited — **furthermore** I built APIs"
        cleaned = sanitize_answer(
            raw,
            field_type="textarea",
            forbidden_patterns=["—", "Furthermore", "I am excited", "I am passionate"],
        )
        self.assertNotIn("—", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("I am excited", cleaned.lower())

    def test_sanitize_radio_fuzzy_match(self):
        cleaned = sanitize_answer(
            "yes please",
            field_type="radio",
            options=["Yes", "No"],
        )
        self.assertEqual(cleaned, "Yes")

    def test_fuzzy_match_option_exact(self):
        self.assertEqual(fuzzy_match_option("yes", ["Yes", "No"]), "Yes")

    def test_fuzzy_match_option_substring(self):
        self.assertEqual(
            fuzzy_match_option("Native", ["Native or bilingual", "Elementary"]),
            "Native or bilingual",
        )

    def test_coerce_checkbox(self):
        self.assertTrue(coerce_checkbox_answer("yes"))
        self.assertTrue(coerce_checkbox_answer(True))
        self.assertFalse(coerce_checkbox_answer("no"))


class TestFlatten(unittest.TestCase):
    def test_flatten_dedupes_normalized_labels(self):
        pairs = flatten_user_inputs(SAMPLE_CONTEXT["user_inputs"])
        questions = [q.lower() for q, _ in pairs]
        self.assertEqual(len(questions), len(set(questions)))
        self.assertTrue(any("node.js" in q for q in questions))


class TestRules(unittest.TestCase):
    def setUp(self):
        # Skip embedding model download in unit tests
        with patch.object(AnswerEngine, "_ensure_embedding_index", lambda self, force=False: None):
            self.engine = AnswerEngine(SAMPLE_CONTEXT, SAMPLE_CONTEXT["aiSettings"])
        self.engine._embeddings = None
        self.engine._index_built = True

    def test_rule_years_with_nodejs(self):
        suggestion = self.engine.suggest(
            "How many years of work experience do you have with Node.js?",
            field_type="text",
        )
        # Exact match from user_inputs should win first
        self.assertEqual(str(suggestion.answer), "4")
        self.assertEqual(suggestion.source, "exact")

    def test_rule_years_unknown_skill_via_rules(self):
        # Avoid exact/retrieval by using a novel phrasing and empty retrieval
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest(
                    "How many years of work experience do you have with COBOL?",
                    field_type="text",
                )
        self.assertEqual(suggestion.source, "rules")
        self.assertEqual(str(suggestion.answer), "0")

    def test_rule_email(self):
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest("Email address", field_type="text")
        self.assertEqual(suggestion.answer, "sendmessage@gabo.email")
        self.assertEqual(suggestion.source, "rules")

    def test_rule_notice_period(self):
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest("Notice period in number of days?", field_type="text")
        self.assertEqual(str(suggestion.answer), "30")
        self.assertEqual(suggestion.source, "rules")

    def test_detect_german_vs_english(self):
        from answer_engine import detect_application_language, resolve_resume_path

        self.assertEqual(detect_application_language("Upload your Lebenslauf bitte"), "de")
        self.assertEqual(detect_application_language("Please upload your resume"), "en")
        self.assertEqual(detect_application_language("asdf qwer"), "en")

    def test_resolve_resume_language(self):
        from answer_engine import resolve_resume_path
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            en = Path(tmp) / "en.pdf"
            de = Path(tmp) / "de.pdf"
            en.write_bytes(b"%PDF")
            de.write_bytes(b"%PDF")
            ctx = {"resumes": {"en": str(en), "de": str(de), "default": "en"}}
            self.assertTrue(resolve_resume_path(ctx, "de").endswith("de.pdf"))
            self.assertTrue(resolve_resume_path(ctx, "en").endswith("en.pdf"))
            self.assertTrue(resolve_resume_path(ctx, None).endswith("en.pdf"))

    def test_rule_salary(self):
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest("What is your salary expectation?", field_type="text")
        self.assertEqual(str(suggestion.answer), "90000")
        self.assertEqual(suggestion.source, "rules")

    def test_rule_sponsorship(self):
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest(
                    "Will you now or in the future require sponsorship for employment visa status?",
                    field_type="radio",
                    options=["Yes", "No"],
                )
        self.assertEqual(suggestion.answer, "Yes")
        self.assertEqual(suggestion.source, "rules")

    def test_rule_language_proficiency(self):
        with patch.object(self.engine, "_semantic_retrieve", return_value=None):
            with patch.object(self.engine, "_exact_match", return_value=None):
                suggestion = self.engine.suggest(
                    "What is your level of proficiency in English?",
                    field_type="select",
                    options=["Elementary", "Limited working", "Native or bilingual"],
                )
        self.assertEqual(suggestion.answer, "Native or bilingual")
        self.assertEqual(suggestion.source, "rules")


class TestRetrieval(unittest.TestCase):
    def test_semantic_retrieve_returns_known_answer(self):
        with patch.object(AnswerEngine, "_ensure_embedding_index", lambda self, force=False: None):
            engine = AnswerEngine(SAMPLE_CONTEXT, SAMPLE_CONTEXT["aiSettings"])

        # Fake embeddings: identity-ish vectors for each pair
        n = len(engine.pairs)
        engine._embeddings = np.eye(n, dtype=float)
        engine._index_built = True

        # Mock embedder to return the vector for the Node.js question index
        node_idx = next(i for i, (q, _) in enumerate(engine.pairs) if "node.js" in q.lower())
        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = np.array([engine._embeddings[node_idx]])

        with patch.object(engine, "_get_embedder", return_value=mock_embedder):
            with patch.object(engine, "_exact_match", return_value=None):
                suggestion = engine.suggest(
                    "Years of professional Node.js experience?",
                    field_type="text",
                )

        self.assertEqual(suggestion.source, "retrieval")
        self.assertEqual(str(suggestion.answer), "4")


class TestLLMFallback(unittest.TestCase):
    def setUp(self):
        with patch.object(AnswerEngine, "_ensure_embedding_index", lambda self, force=False: None):
            self.engine = AnswerEngine(SAMPLE_CONTEXT, SAMPLE_CONTEXT["aiSettings"])
        self.engine._embeddings = None
        self.engine._index_built = True

    def test_ollama_then_transformers_fallback(self):
        with patch.object(self.engine, "_exact_match", return_value=None):
            with patch.object(self.engine, "_semantic_retrieve", return_value=None):
                with patch.object(self.engine, "_rule_based_answer", return_value=None):
                    with patch.object(self.engine, "_generate_ollama", return_value=None) as ollama:
                        with patch.object(
                            self.engine,
                            "_generate_transformers",
                            return_value="I built several React apps.",
                        ) as transformers:
                            suggestion = self.engine.suggest(
                                "Describe a project you are proud of",
                                field_type="textarea",
                            )

        ollama.assert_called_once()
        transformers.assert_called_once()
        self.assertEqual(suggestion.source, "transformers")
        self.assertIsNotNone(suggestion.answer)
        self.assertNotIn("—", str(suggestion.answer))

    def test_ollama_success_skips_transformers(self):
        with patch.object(self.engine, "_exact_match", return_value=None):
            with patch.object(self.engine, "_semantic_retrieve", return_value=None):
                with patch.object(self.engine, "_rule_based_answer", return_value=None):
                    with patch.object(
                        self.engine, "_generate_ollama", return_value="4 years with React"
                    ):
                        with patch.object(self.engine, "_generate_transformers") as transformers:
                            suggestion = self.engine.suggest(
                                "Tell us about your React experience briefly",
                                field_type="textarea",
                            )

        transformers.assert_not_called()
        self.assertEqual(suggestion.source, "ollama")
        self.assertIn("React", str(suggestion.answer))

    def test_file_field_skipped(self):
        suggestion = self.engine.suggest("Upload resume", field_type="file")
        self.assertEqual(suggestion.source, "none")
        self.assertIsNone(suggestion.answer)

    def test_no_llm_returns_none_source(self):
        with patch.object(self.engine, "_exact_match", return_value=None):
            with patch.object(self.engine, "_semantic_retrieve", return_value=None):
                with patch.object(self.engine, "_rule_based_answer", return_value=None):
                    with patch.object(self.engine, "_generate_ollama", return_value=None):
                        with patch.object(self.engine, "_generate_transformers", return_value=None):
                            suggestion = self.engine.suggest(
                                "Invent a brand new obscure question xyzzy",
                                field_type="text",
                            )
        self.assertEqual(suggestion.source, "none")


class TestYearsParsing(unittest.TestCase):
    def test_parse_date_range(self):
        years = AnswerEngine._parse_years_from_date_range("Nov 2022 - Apr 2024")
        self.assertEqual(years, 1)

    def test_parse_present(self):
        years = AnswerEngine._parse_years_from_date_range("Oct 2021 - Present")
        self.assertGreaterEqual(years, 4)


if __name__ == "__main__":
    unittest.main()
