"""Local AI answer engine for LinkedIn Easy Apply form questions.

Pipeline: exact match -> semantic retrieval -> rules -> Ollama -> transformers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE_PATH = CACHE_DIR / "embeddings.pkl"

DEFAULT_AI_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "primary": "ollama",
    "ollama": {
        "baseUrl": "http://localhost:11434",
        "model": "qwen2.5:3b-instruct",
        "timeoutSeconds": 30,
    },
    "fallback": {
        "model": "Qwen/Qwen2.5-1.5B-Instruct",
        "device": "auto",
    },
    "retrieval": {
        "embeddingModel": "sentence-transformers/all-MiniLM-L6-v2",
        "similarityThreshold": 0.85,
    },
    "defaults": {
        "salaryExpectationUsd": "90000",
        "hourlyRateRange": "40-60",
        "requiresSponsorship": False,
        "willingToRelocate": True,
        "noticePeriodDays": 30,
        "relocateTarget": "Zug, Switzerland",
    },
    "style": {
        "maxWords": 40,
        "forbiddenPatterns": [
            "—",
            "Furthermore",
            "I am excited",
            "I am passionate",
        ],
    },
}


@dataclass
class Suggestion:
    answer: Any
    confidence: str  # "high" | "medium" | "low"
    source: str  # "exact" | "retrieval" | "rules" | "ollama" | "transformers" | "none"


def normalize_label(label: str) -> str:
    """Collapse LinkedIn duplicate labels and Required suffixes."""
    if not label:
        return ""
    text = label.replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    # Drop trailing "Required" markers
    parts = [p for p in parts if p.lower() != "required"]
    if not parts:
        return ""
    # Deduplicate consecutive identical lines (City\nCity)
    deduped: List[str] = []
    for part in parts:
        if not deduped or deduped[-1].lower() != part.lower():
            deduped.append(part)
    return " ".join(deduped).strip()


def sanitize_answer(
    answer: str,
    field_type: str = "text",
    options: Optional[Sequence[str]] = None,
    max_words: int = 40,
    forbidden_patterns: Optional[Sequence[str]] = None,
) -> str:
    """Strip AI tells and coerce to field constraints."""
    if answer is None:
        return ""
    text = str(answer).strip()

    # Remove common wrappers / quotes
    text = text.strip("`\"'")
    text = re.sub(r"^(answer|response)\s*:\s*", "", text, flags=re.IGNORECASE)

    # Em dashes and fancy punctuation
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"\s+--\s+", " - ", text)

    # Markdown leftovers
    text = re.sub(r"[#*_`]+", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.MULTILINE)

    forbidden = list(forbidden_patterns or [])
    for pattern in forbidden:
        if pattern and pattern.lower() not in ("—", "--"):
            text = re.sub(re.escape(pattern), "", text, flags=re.IGNORECASE)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Short fields: keep first sentence-ish chunk
    if field_type in ("text", "radio", "select", "checkbox") and "\n" in str(answer):
        first_line = str(answer).strip().splitlines()[0]
        text = re.sub(r"\s+", " ", first_line).strip()

    words = text.split()
    if max_words and len(words) > max_words and field_type in ("text", "textarea"):
        text = " ".join(words[:max_words]).rstrip(",.;:")

    if field_type == "checkbox":
        return _coerce_bool_string(text)

    if options and field_type in ("radio", "select"):
        matched = fuzzy_match_option(text, options)
        return matched if matched is not None else text

    return text


def _coerce_bool_string(text: str) -> str:
    lowered = text.strip().lower()
    if lowered in ("yes", "y", "true", "1", "check", "checked"):
        return "true"
    if lowered in ("no", "n", "false", "0", "uncheck", "unchecked"):
        return "false"
    return text


def coerce_checkbox_answer(answer: Any) -> bool:
    if isinstance(answer, bool):
        return answer
    text = str(answer).strip().lower()
    return text in ("yes", "y", "true", "1", "check", "checked")


def fuzzy_match_option(answer: str, options: Sequence[str]) -> Optional[str]:
    """Pick the closest option; prefer exact/substring matches."""
    if not options:
        return None
    cleaned = answer.strip().lower()
    # Exact (case-insensitive)
    for opt in options:
        if opt.strip().lower() == cleaned:
            return opt
    # Contained
    for opt in options:
        opt_l = opt.strip().lower()
        if cleaned in opt_l or opt_l in cleaned:
            return opt
    # Token overlap score
    answer_tokens = set(re.findall(r"[a-z0-9]+", cleaned))
    best_opt = None
    best_score = 0.0
    for opt in options:
        opt_tokens = set(re.findall(r"[a-z0-9]+", opt.lower()))
        if not opt_tokens:
            continue
        overlap = len(answer_tokens & opt_tokens) / len(opt_tokens)
        if overlap > best_score:
            best_score = overlap
            best_opt = opt
    if best_score >= 0.5:
        return best_opt
    return None


def flatten_user_inputs(user_inputs: Dict[str, Dict[str, Any]]) -> List[Tuple[str, Any]]:
    """Flatten location-scoped user_inputs into (normalized_question, answer) pairs."""
    pairs: List[Tuple[str, Any]] = []
    seen = set()
    for _location, answers in (user_inputs or {}).items():
        if not isinstance(answers, dict):
            continue
        for question, answer in answers.items():
            norm = normalize_label(question)
            if not norm or norm.lower() in seen:
                continue
            seen.add(norm.lower())
            pairs.append((norm, answer))
    return pairs


def _hash_pairs(pairs: Sequence[Tuple[str, Any]]) -> str:
    payload = json.dumps(
        [(q, str(a)) for q, a in pairs],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def detect_application_language(*texts: str) -> str:
    """Return 'de' or 'en'. Defaults to English when unsure."""
    combined = " ".join(t for t in texts if t).strip()
    if not combined:
        return "en"

    lowered = combined.lower()
    german_markers = [
        "ä", "ö", "ü", "ß",
        "lebenslauf", "anschreiben", "bewerbung", "kündigung", "kuendigung",
        "verfügbar", "verfuegbar", "jahre erfahrung", "wie viele jahre",
        "deutsch", "schweiz", "wohnort", "gehalt", "vorname", "nachname",
        "strasse", "plz", "ort", "haben sie", "ihre erfahrung", "notiz",
        "arbeitserlaubnis", "aufenthalts", "bewilligung",
    ]
    german_hits = sum(1 for m in german_markers if m in lowered)
    # Strong label cues
    if "lebenslauf" in lowered or "anschreiben" in lowered:
        return "de"
    if german_hits >= 2:
        return "de"

    try:
        from langdetect import detect

        lang = detect(combined)
        if lang == "de":
            return "de"
    except Exception:
        pass
    return "en"


def resolve_resume_path(context_data: Dict[str, Any], language: Optional[str] = None) -> Optional[str]:
    """Pick EN/DE resume path from config. Defaults to English."""
    resumes = context_data.get("resumes") or {}
    if not resumes:
        return None
    lang = (language or resumes.get("default") or "en").lower()
    if lang.startswith("de"):
        path = resumes.get("de") or resumes.get("en")
    else:
        path = resumes.get("en") or resumes.get("de")
    if path and Path(path).exists():
        return str(Path(path).resolve())
    # Try relative to cwd
    if path:
        candidate = Path(path)
        if candidate.exists():
            return str(candidate.resolve())
    return None


class AnswerEngine:
    def __init__(self, context_data: Dict[str, Any], ai_settings: Optional[Dict[str, Any]] = None):
        self.context_data = context_data
        self.ai_settings = self._merge_settings(ai_settings or context_data.get("aiSettings") or {})
        self.ai_context = context_data.get("aiContext") or {}
        self.user_inputs = context_data.get("user_inputs") or {}
        self.pairs = flatten_user_inputs(self.user_inputs)

        self._embedder = None
        self._embeddings = None  # numpy array or list
        self._pair_hash = _hash_pairs(self.pairs)
        self._transformers_pipeline = None
        self._index_built = False

        if self.ai_settings.get("enabled", True):
            try:
                self._ensure_embedding_index()
            except Exception as exc:
                logger.warning("Could not build embedding index at init: %s", exc)

    @staticmethod
    def _merge_settings(overrides: Dict[str, Any]) -> Dict[str, Any]:
        import copy

        merged = copy.deepcopy(DEFAULT_AI_SETTINGS)
        for key, value in (overrides or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        return merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def suggest(
        self,
        question: str,
        field_type: str = "text",
        options: Optional[Sequence[str]] = None,
        location: Optional[str] = None,
    ) -> Suggestion:
        """Return a suggested answer with confidence and source."""
        if field_type == "file":
            return Suggestion(answer=None, confidence="low", source="none")

        norm_q = normalize_label(question)
        opts = list(options) if options else None

        # Layer 1: exact match (location then global)
        exact = self._exact_match(question, location)
        if exact is not None:
            return Suggestion(answer=exact, confidence="high", source="exact")

        # Layer 2: semantic retrieval
        retrieved = self._semantic_retrieve(norm_q)
        if retrieved is not None:
            answer, score = retrieved
            answer = self._adapt_answer(answer, field_type, opts)
            confidence = "high" if score >= 0.92 else "medium"
            return Suggestion(answer=answer, confidence=confidence, source="retrieval")

        # Layer 3: rules
        rule_answer = self._rule_based_answer(norm_q, field_type, opts)
        if rule_answer is not None:
            answer = self._adapt_answer(rule_answer, field_type, opts)
            return Suggestion(answer=answer, confidence="high", source="rules")

        # Layer 4/5: LLM generation
        few_shot = self._top_similar_pairs(norm_q, k=5)
        prompt = self._build_prompt(norm_q, field_type, opts, few_shot)

        raw = None
        source = "none"
        if self.ai_settings.get("primary", "ollama") == "ollama":
            raw = self._generate_ollama(prompt)
            if raw is not None:
                source = "ollama"
        if raw is None:
            raw = self._generate_transformers(prompt)
            if raw is not None:
                source = "transformers"

        if raw is None:
            return Suggestion(answer=None, confidence="low", source="none")

        style = self.ai_settings.get("style") or {}
        cleaned = sanitize_answer(
            raw,
            field_type=field_type,
            options=opts,
            max_words=int(style.get("maxWords", 40)),
            forbidden_patterns=style.get("forbiddenPatterns"),
        )
        answer = self._adapt_answer(cleaned, field_type, opts)

        if field_type in ("radio", "select") and opts:
            if fuzzy_match_option(str(answer), opts) is None:
                return Suggestion(answer=answer, confidence="low", source=source)

        return Suggestion(answer=answer, confidence="medium", source=source)

    def rebuild_index(self) -> None:
        """Rebuild embedding index from current user_inputs (e.g. after save)."""
        self.user_inputs = self.context_data.get("user_inputs") or {}
        self.pairs = flatten_user_inputs(self.user_inputs)
        self._pair_hash = _hash_pairs(self.pairs)
        self._index_built = False
        self._embeddings = None
        self._ensure_embedding_index(force=True)

    # ------------------------------------------------------------------
    # Exact / retrieval
    # ------------------------------------------------------------------

    def _exact_match(self, question: str, location: Optional[str]) -> Any:
        norm = normalize_label(question)
        locations_to_check: List[str] = []
        if location:
            locations_to_check.append(location)
        locations_to_check.extend(self.user_inputs.keys())

        for loc in locations_to_check:
            answers = self.user_inputs.get(loc) or {}
            if question in answers:
                return answers[question]
            for key, value in answers.items():
                if normalize_label(key).lower() == norm.lower():
                    return value
        return None

    def _ensure_embedding_index(self, force: bool = False) -> None:
        if self._index_built and not force:
            return
        if not self.pairs:
            self._embeddings = None
            self._index_built = True
            return

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        model_name = (self.ai_settings.get("retrieval") or {}).get(
            "embeddingModel", "sentence-transformers/all-MiniLM-L6-v2"
        )

        if not force and EMBEDDINGS_CACHE_PATH.exists():
            try:
                with EMBEDDINGS_CACHE_PATH.open("rb") as f:
                    cached = pickle.load(f)
                if (
                    cached.get("pair_hash") == self._pair_hash
                    and cached.get("model") == model_name
                    and cached.get("questions") == [q for q, _ in self.pairs]
                ):
                    self._embeddings = cached["embeddings"]
                    self._index_built = True
                    logger.info("Loaded embedding index from cache (%d pairs)", len(self.pairs))
                    return
            except Exception as exc:
                logger.warning("Failed to load embedding cache: %s", exc)

        embedder = self._get_embedder(model_name)
        questions = [q for q, _ in self.pairs]
        embeddings = embedder.encode(questions, show_progress_bar=False, convert_to_numpy=True)
        self._embeddings = embeddings
        self._index_built = True

        try:
            with EMBEDDINGS_CACHE_PATH.open("wb") as f:
                pickle.dump(
                    {
                        "pair_hash": self._pair_hash,
                        "model": model_name,
                        "questions": questions,
                        "embeddings": embeddings,
                    },
                    f,
                )
            logger.info("Cached embedding index (%d pairs)", len(self.pairs))
        except Exception as exc:
            logger.warning("Failed to write embedding cache: %s", exc)

    def _get_embedder(self, model_name: str):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(model_name)
        return self._embedder

    def _cosine_scores(self, query_vec, matrix):
        import numpy as np

        q = np.asarray(query_vec, dtype=float)
        m = np.asarray(matrix, dtype=float)
        q_norm = q / (np.linalg.norm(q) + 1e-9)
        m_norm = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
        return m_norm @ q_norm

    def _semantic_retrieve(self, question: str) -> Optional[Tuple[Any, float]]:
        if not self.pairs:
            return None
        try:
            self._ensure_embedding_index()
        except Exception as exc:
            logger.warning("Embedding index unavailable: %s", exc)
            return None
        if self._embeddings is None:
            return None

        threshold = float(
            (self.ai_settings.get("retrieval") or {}).get("similarityThreshold", 0.85)
        )
        model_name = (self.ai_settings.get("retrieval") or {}).get(
            "embeddingModel", "sentence-transformers/all-MiniLM-L6-v2"
        )
        try:
            embedder = self._get_embedder(model_name)
            query_vec = embedder.encode([question], convert_to_numpy=True)[0]
            scores = self._cosine_scores(query_vec, self._embeddings)
            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])
            if best_score >= threshold:
                return self.pairs[best_idx][1], best_score
        except Exception as exc:
            logger.warning("Semantic retrieval failed: %s", exc)
        return None

    def _top_similar_pairs(self, question: str, k: int = 5) -> List[Tuple[str, Any]]:
        if not self.pairs:
            return []
        try:
            self._ensure_embedding_index()
            if self._embeddings is None:
                return self.pairs[:k]
            model_name = (self.ai_settings.get("retrieval") or {}).get(
                "embeddingModel", "sentence-transformers/all-MiniLM-L6-v2"
            )
            embedder = self._get_embedder(model_name)
            query_vec = embedder.encode([question], convert_to_numpy=True)[0]
            scores = self._cosine_scores(query_vec, self._embeddings)
            import numpy as np

            top_idx = np.argsort(scores)[::-1][:k]
            return [self.pairs[i] for i in top_idx]
        except Exception:
            return self.pairs[:k]

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def _rule_based_answer(
        self,
        question: str,
        field_type: str,
        options: Optional[Sequence[str]],
    ) -> Any:
        q = question.lower()
        defaults = self.ai_settings.get("defaults") or {}
        user_data = self.ai_context.get("user_data") or {}
        languages = self.ai_context.get("languagesSpokenByUser") or {}
        preferences = self.ai_context.get("preferences") or {}

        # Contact / profile fields
        if "country code" in q and "phone" in q:
            return user_data.get("phoneCountryCode") or "Switzerland (+41)"

        if re.search(r"\b(phone|mobile|telephone)\b", q) and "country code" not in q:
            if user_data.get("phoneNationalNumber") and (
                "mobile phone number" in q or "phone number" in q or q.strip() in ("phone", "mobile")
            ):
                return user_data["phoneNationalNumber"]
            phone = user_data.get("phone")
            if phone:
                return phone

        if "email" in q and "how did you" not in q:
            if user_data.get("email"):
                return user_data["email"]

        if re.search(r"\b(postal|zip)\b", q):
            return user_data.get("postalCode")

        if re.search(r"\bstreet\b", q) or "address line 1" in q:
            return user_data.get("street") or user_data.get("address")

        if re.search(r"\b(city|current location|where (are|do) you (live|reside)|residing|wohnort)\b", q):
            return user_data.get("currentLocation") or user_data.get("city") or user_data.get("address")

        if ("address" in q or "adresse" in q) and "email" not in q:
            return user_data.get("address")

        if "country" in q and "phone" not in q and "code" not in q:
            return user_data.get("country") or "Switzerland"

        if "linkedin" in q and ("url" in q or "profile" in q or "share" in q or "link" in q):
            return user_data.get("linkedin_url")

        if "github" in q:
            if user_data.get("github_url"):
                return user_data["github_url"]
            for past_q, past_a in self.pairs:
                if "github" in past_q.lower():
                    return past_a

        if "portfolio" in q or "website" in q or "personal site" in q:
            return user_data.get("portfolio_url")

        # Notice period (CV: 1 month)
        if "notice period" in q or "kündigungsfrist" in q or "kuendigungsfrist" in q:
            days = user_data.get("noticePeriodDays") or defaults.get("noticePeriodDays") or 30
            if "month" in q or "monat" in q:
                return "1"
            return str(days)

        # Work permit / authorization (Switzerland-aware)
        if re.search(r"authorized to work|legally authorized|work permit|work authorization|arbeitserlaubnis|aufenthalts", q):
            auth = self._work_auth_for_question(q)
            answer = "Yes" if auth.get("authorized") else "No"
            if options:
                return fuzzy_match_option(answer, options) or answer
            return answer

        # Language proficiency
        if re.search(
            r"(?:level of )?proficiency in \w+|(?:speak|language).*\b(english|spanish|dutch|portuguese|catalan|french|german|deutsch)\b",
            q,
            re.IGNORECASE,
        ) or ("language" in q and "proficiency" in q) or "sprachniveau" in q or "deutschkenntnisse" in q:
            for lang, level in languages.items():
                if lang.lower() in q or (lang.lower() == "german" and "deutsch" in q):
                    mapped = self._map_language_level(level, options)
                    return mapped if mapped is not None else level

        # Years of experience with a skill
        years_match = re.search(
            r"how many years.*?(?:with|using|in|of|working with|experience (?:with|in|using))\s+(.+?)(?:\?|$)",
            q,
            re.IGNORECASE,
        )
        if years_match or re.search(r"years of (?:work |professional )?experience", q):
            skill = None
            if years_match:
                skill = years_match.group(1).strip(" .?")
                skill = re.sub(r"\s*\(.*?\)\s*", " ", skill).strip()
            years = self._estimate_skill_years(skill) if skill else self._total_experience_years()
            if years is not None:
                if options:
                    return self._years_to_option(years, options)
                return str(years)

        # Visa / sponsorship
        if re.search(r"sponsor|sponsorship|visa|h-?1b|immigration|visum", q):
            auth = self._work_auth_for_question(q)
            requires = auth.get("requiresSponsorship", defaults.get("requiresSponsorship", True))
            if "require sponsorship" in q or "need visa" in q or "require.*visa" in q or "visum" in q:
                answer = "Yes" if requires else "No"
            elif "authorized to work" in q or "legally authorized" in q:
                answer = "Yes" if auth.get("authorized") else "No"
            else:
                answer = "Yes" if requires else "No"
            if options:
                matched = fuzzy_match_option(answer, options)
                return matched if matched is not None else answer
            return answer

        # Salary / rate
        if re.search(r"salary|compensation|ctc|expected (rate|pay)|hourly|gehalt", q):
            if "hour" in q or "hourly" in q or "rate" in q:
                return defaults.get("hourlyRateRange", "40-60")
            return defaults.get("salaryExpectationUsd", "90000")

        # Office / hybrid / commute — remote anywhere; onsite only Zurich/Zug
        if re.search(r"onsite|on-site|in.?office|commut|hybrid|office", q):
            office_ok = self._office_location_allowed(q)
            if "remote" in q and "only" not in q:
                answer = "Yes"
            elif office_ok is True:
                answer = "Yes"
            elif office_ok is False:
                answer = "No"
            else:
                # Ambiguous location — prefer remote yes; otherwise yes if willing to relocate to Zug
                if "remote" in q:
                    answer = "Yes"
                else:
                    answer = "Yes" if preferences.get("willingToRelocate") else "No"
            if options:
                return fuzzy_match_option(answer, options) or answer
            return answer

        # Relocate
        if "relocate" in q or "umzug" in q or "umziehen" in q:
            willing = preferences.get("willingToRelocate", defaults.get("willingToRelocate", True))
            target = preferences.get("relocateTarget") or defaults.get("relocateTarget")
            if field_type == "text" and target and ("where" in q or "which" in q):
                return target
            answer = "Yes" if willing else "No"
            if options:
                matched = fuzzy_match_option(answer, options)
                return matched if matched is not None else answer
            return answer

        # Yes/No radio with clear skill possession when skill is in experience
        if field_type in ("radio", "select") and options:
            yes_no = {o.strip().lower() for o in options}
            if yes_no <= {"yes", "no"} or yes_no == {"yes", "no"}:
                # "Do you have experience with X?"
                exp_match = re.search(
                    r"(?:experience (?:with|in|using)|familiar with|worked with|proficient in)\s+(.+?)(?:\?|$)",
                    q,
                )
                if exp_match:
                    skill = exp_match.group(1).strip()
                    years = self._estimate_skill_years(skill)
                    answer = "Yes" if years and years > 0 else "No"
                    return fuzzy_match_option(answer, options) or answer

        # Checkbox defaults for LinkedIn / agree terms
        if field_type == "checkbox":
            if "linkedin" in q:
                return True
            if "agree" in q and "terms" in q:
                return True

        return None

    def _work_auth_for_question(self, question_lower: str) -> Dict[str, Any]:
        auth_cfg = self.ai_context.get("workAuthorization") or {}
        defaults = self.ai_settings.get("defaults") or {}
        if re.search(r"switzerland|schweiz|swiss|zurich|zürich|zug", question_lower):
            return auth_cfg.get("switzerland") or {
                "authorized": True,
                "requiresSponsorship": False,
            }
        if re.search(
            r"\b(germany|deutschland|spain|france|netherlands|belgium|portugal|ireland|eu|eea|european)\b",
            question_lower,
        ):
            return auth_cfg.get("eu") or {"authorized": True, "requiresSponsorship": False}
        # Search location context
        try:
            # Prefer Switzerland defaults when searching CH
            return {
                "authorized": not defaults.get("requiresSponsorship", False),
                "requiresSponsorship": defaults.get("requiresSponsorship", False),
            }
        except Exception:
            return auth_cfg.get("default") or {
                "authorized": False,
                "requiresSponsorship": True,
            }

    def _office_location_allowed(self, question_lower: str) -> Optional[bool]:
        preferences = self.ai_context.get("preferences") or {}
        allowed = [x.lower() for x in (preferences.get("onsiteOnlyIn") or preferences.get("officeLocationsOnly") or [])]
        if not allowed:
            return None
        # If question mentions a city/region
        mentioned = None
        for city in allowed + ["geneva", "genf", "bern", "basel", "lausanne", "london", "remote"]:
            if city.lower() in question_lower:
                mentioned = city.lower()
                break
        if mentioned == "remote":
            return True
        if mentioned is None:
            return None
        return mentioned in [a.lower() for a in allowed]

    def _map_language_level(self, level: str, options: Optional[Sequence[str]]) -> Any:
        level_l = (level or "").lower()
        mapping = {
            "native": "Native or bilingual",
            "c2": "Native or bilingual",
            "c1": "Full professional",
            "full professional": "Full professional",
            "fluent": "Full professional",
            "professional": "Professional working",
            "intermediate": "Limited working",
            "basic": "Elementary",
            "beginner": "Elementary",
            "a1": "Elementary",
            "a2": "Elementary",
            "b1": "Limited working",
            "b2": "Professional working",
        }
        preferred = None
        for key, value in mapping.items():
            if key in level_l:
                preferred = value
                break
        preferred = preferred or level
        if options:
            matched = fuzzy_match_option(preferred, options)
            if matched:
                return matched
            matched = fuzzy_match_option(level, options)
            return matched if matched is not None else preferred
        return preferred

    def _total_experience_years(self) -> int:
        experience = self.ai_context.get("experience") or []
        # Rough: use longest contiguous span from earliest start to latest end/"Present"
        years = 0
        for job in experience:
            date = str(job.get("date") or "")
            y = self._parse_years_from_date_range(date)
            if y is not None:
                years = max(years, y)
        # Also sum unique roughly - prefer max of individual roles if overlapping
        if years == 0 and experience:
            years = 4  # sensible default from profile
        return years

    def _estimate_skill_years(self, skill: Optional[str]) -> Optional[int]:
        if not skill:
            return self._total_experience_years()
        skill_l = skill.lower().strip()
        # Normalize common aliases
        aliases = {
            "node": "node.js",
            "nodejs": "node.js",
            "react.js": "react",
            "reactjs": "react",
            "js": "javascript",
            "ts": "typescript",
            "postgres": "postgresql",
        }
        skill_l = aliases.get(skill_l, skill_l)

        # Prefer past user_inputs for this skill
        for past_q, past_a in self.pairs:
            pq = past_q.lower()
            if "years" in pq and skill_l in pq:
                try:
                    return int(re.search(r"\d+", str(past_a)).group())
                except Exception:
                    pass

        experience = self.ai_context.get("experience") or []
        skills_list = [s.lower() for s in (self.ai_context.get("skills") or [])]
        best = 0
        found = False
        for job in experience:
            job_skills = [s.lower() for s in (job.get("skills") or [])]
            if any(skill_l in s or s in skill_l for s in job_skills):
                found = True
                y = self._parse_years_from_date_range(str(job.get("date") or ""))
                if y:
                    best = max(best, y)
        if found:
            return best or 1
        if any(skill_l in s or s in skill_l for s in skills_list):
            return 1
        # Unknown skill -> 0 years is honest
        if re.search(r"[a-z]", skill_l):
            return 0
        return None

    @staticmethod
    def _parse_years_from_date_range(date_str: str) -> Optional[int]:
        # e.g. "Nov 2022 - Apr 2024" or "Jan 2021 - Present"
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        matches = re.findall(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})", date_str, re.I)
        if not matches:
            years = re.findall(r"(20\d{2})", date_str)
            if len(years) >= 1:
                start = int(years[0])
                end = 2026 if "present" in date_str.lower() else (int(years[-1]) if len(years) > 1 else start)
                return max(0, end - start)
            return None
        start_m, start_y = months[matches[0][0][:3].lower()], int(matches[0][1])
        if len(matches) >= 2:
            end_m, end_y = months[matches[1][0][:3].lower()], int(matches[1][1])
        elif "present" in date_str.lower():
            end_m, end_y = 8, 2026  # approximate "today"
        else:
            end_m, end_y = start_m, start_y
        total_months = (end_y - start_y) * 12 + (end_m - start_m)
        return max(0, round(total_months / 12))

    @staticmethod
    def _years_to_option(years: int, options: Sequence[str]) -> str:
        # Try numeric exact
        for opt in options:
            if re.fullmatch(r"\d+", opt.strip()) and int(opt.strip()) == years:
                return opt
        # Ranges like "2-5 years", "0-2 years", "3+"
        for opt in options:
            m = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", opt)
            if m:
                low, high = int(m.group(1)), int(m.group(2))
                if low <= years <= high:
                    return opt
            m = re.search(r"(\d+)\s*\+", opt)
            if m and years >= int(m.group(1)):
                return opt
            m = re.search(r"less than\s*(\d+)", opt, re.I)
            if m and years < int(m.group(1)):
                return opt
        return fuzzy_match_option(str(years), options) or str(years)

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def _build_context_summary(self) -> str:
        user_data = self.ai_context.get("user_data") or {}
        preferences = self.ai_context.get("preferences") or {}
        skills = self.ai_context.get("skills") or []
        languages = self.ai_context.get("languagesSpokenByUser") or {}
        experience = self.ai_context.get("experience") or []
        titles = [e.get("title") for e in experience[:3] if e.get("title")]
        defaults = self.ai_settings.get("defaults") or {}

        lines = [
            f"Location: {user_data.get('currentLocation', 'N/A')}",
            f"Address: {user_data.get('address', 'N/A')}",
            f"Email: {user_data.get('email', 'N/A')}",
            f"Phone: {user_data.get('phone', 'N/A')}",
            f"LinkedIn: {user_data.get('linkedin_url', 'N/A')}",
            f"GitHub: {user_data.get('github_url', 'N/A')}",
            f"Work permit: {user_data.get('workPermit', 'N/A')}",
            f"Notice period days: {user_data.get('noticePeriodDays', defaults.get('noticePeriodDays', 30))}",
            f"Top skills: {', '.join(skills[:12])}",
            f"Recent roles: {', '.join(titles)}",
            f"Languages: {', '.join(f'{k} ({v})' for k, v in languages.items())}",
            f"Preferred workplace: {preferences.get('workplaceType', 'Remote')}",
            f"Remote anywhere: {preferences.get('remoteAnywhere', True)}",
            f"Office only in: {', '.join(preferences.get('onsiteOnlyIn') or [])}",
            f"Relocate target: {preferences.get('relocateTarget', defaults.get('relocateTarget'))}",
            f"Preferred job type: {preferences.get('jobType', 'Contract')}",
            f"Willing to relocate: {preferences.get('willingToRelocate', defaults.get('willingToRelocate'))}",
            f"Requires sponsorship (default): {defaults.get('requiresSponsorship')}",
            f"Salary expectation USD: {defaults.get('salaryExpectationUsd')}",
            f"Hourly rate: {defaults.get('hourlyRateRange')}",
            f"Total experience years (approx): {self._total_experience_years()}",
        ]
        return "\n".join(lines)

    def _build_prompt(
        self,
        question: str,
        field_type: str,
        options: Optional[Sequence[str]],
        few_shot: Sequence[Tuple[str, Any]],
    ) -> str:
        examples = "\n".join(
            f"Q: {q}\nA: {a}" for q, a in few_shot if a is not None
        )
        option_block = ""
        if options:
            option_block = (
                "\nValid options (reply with ONLY one of these exactly):\n"
                + "\n".join(f"- {o}" for o in options)
            )
        elif field_type == "checkbox":
            option_block = "\nReply with ONLY true or false."

        instruction = (
            "You are filling a job application form as the candidate. "
            "Answer in 1-2 short plain sentences max. "
            "No em dashes, no bullet lists, no markdown, no phrases like "
            "'I am excited' or 'I am passionate'. Match the tone of the examples. "
            "Reply with ONLY the answer text."
        )
        if field_type in ("radio", "select") and options:
            instruction = (
                "You are filling a job application form as the candidate. "
                "Reply with ONLY the exact option text from the list. "
                "No explanation."
            )
        elif field_type == "checkbox":
            instruction = (
                "You are filling a job application form as the candidate. "
                "Reply with ONLY true or false."
            )

        return (
            f"{instruction}\n\n"
            f"Candidate profile:\n{self._build_context_summary()}\n\n"
            f"Examples of how this candidate answers:\n{examples}\n\n"
            f"Question: {question}"
            f"{option_block}\n\n"
            f"Answer:"
        )

    def _generate_ollama(self, prompt: str) -> Optional[str]:
        cfg = self.ai_settings.get("ollama") or {}
        base_url = cfg.get("baseUrl", "http://localhost:11434").rstrip("/")
        model = cfg.get("model", "qwen2.5:3b-instruct")
        timeout = int(cfg.get("timeoutSeconds", 30))
        try:
            import requests

            resp = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 120},
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                logger.warning("Ollama returned status %s", resp.status_code)
                return None
            data = resp.json()
            return (data.get("response") or "").strip() or None
        except Exception as exc:
            logger.info("Ollama unavailable, will try fallback: %s", exc)
            return None

    def _generate_transformers(self, prompt: str) -> Optional[str]:
        cfg = self.ai_settings.get("fallback") or {}
        model_name = cfg.get("model", "Qwen/Qwen2.5-1.5B-Instruct")
        device = cfg.get("device", "auto")
        try:
            pipe = self._get_transformers_pipeline(model_name, device)
            result = pipe(
                prompt,
                max_new_tokens=80,
                do_sample=False,
                return_full_text=False,
            )
            if isinstance(result, list) and result:
                text = result[0].get("generated_text", "")
                return text.strip() or None
            return None
        except Exception as exc:
            logger.warning("Transformers fallback failed: %s", exc)
            return None

    def _get_transformers_pipeline(self, model_name: str, device: str):
        if self._transformers_pipeline is None:
            from transformers import pipeline

            kwargs: Dict[str, Any] = {
                "task": "text-generation",
                "model": model_name,
            }
            if device != "auto":
                kwargs["device"] = device
            self._transformers_pipeline = pipeline(**kwargs)
        return self._transformers_pipeline

    def _adapt_answer(self, answer: Any, field_type: str, options: Optional[Sequence[str]]) -> Any:
        if field_type == "checkbox":
            return coerce_checkbox_answer(answer)
        if options and field_type in ("radio", "select"):
            matched = fuzzy_match_option(str(answer), options)
            return matched if matched is not None else answer
        return answer
