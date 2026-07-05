"""
RuralCare AI — Translation Service
IndicTrans2 (offline, Indic languages) with Google Translate fallback.
"""

import os
from app.utils.logger import get_logger

logger = get_logger(__name__)

INDIC_CODES = {"hi", "ta", "te", "bn", "kn", "ml", "mr", "pa", "gu", "or", "as"}


def detect_language(text: str) -> str:
    """Detect the language of the input text. Returns ISO 639-1 code."""
    try:
        from langdetect import detect
        return detect(text)
    except Exception as exc:
        logger.warning("Language detection failed: %s — defaulting to 'en'", exc)
        return "en"


def translate_text(text: str, src: str, dest: str = "en") -> str:
    """
    Translate text from src language to dest language.
    Tries IndicTrans2 first for Indic languages, falls back to Google Translate.
    """
    if src == dest or not text.strip():
        return text

    provider = os.getenv("TRANSLATE_PROVIDER", "google")

    if provider == "indicTrans2" and (src in INDIC_CODES or dest in INDIC_CODES):
        result = _try_indicTrans2(text, src, dest)
        if result:
            return result

    return _google_translate(text, src, dest)


def _try_indicTrans2(text: str, src: str, dest: str) -> str | None:
    try:
        from IndicTransToolkit import IndicProcessor
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch

        model_name = "ai4bharat/indictrans2-en-indic-1B"
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        model     = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
        ip = IndicProcessor(inference=True)

        src_lang = f"{src}_Latn" if src == "en" else f"{src}_Deva"
        tgt_lang = f"{dest}_Latn" if dest == "en" else f"{dest}_Deva"

        batch = ip.preprocess_batch([text], src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)

        with torch.no_grad():
            outputs = model.generate(**inputs, num_beams=4, max_length=512)

        decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)
        result = ip.postprocess_batch(decoded, lang=tgt_lang)[0]
        logger.info("IndicTrans2 translated %s → %s", src, dest)
        return result
    except Exception as exc:
        logger.warning("IndicTrans2 failed: %s — falling back to Google Translate", exc)
        return None


def _google_translate(text: str, src: str, dest: str) -> str:
    try:
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text, src=src, dest=dest)
        logger.info("Google Translate: %s → %s (%d chars)", src, dest, len(text))
        return result.text
    except Exception as exc:
        logger.error("Google Translate failed: %s", exc)
        return text  # return original text on failure
