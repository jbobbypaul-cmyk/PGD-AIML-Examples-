# Skill: Multilingual & Voice

## Skill Name
`multilingual-voice`

## Purpose
Enable RuralCare AI to accept patient input in multiple Indian languages (via text or voice), process it through the standard English-language pipeline, and return responses in the patient's language. This skill covers speech-to-text (Whisper), language detection (langdetect), and bidirectional translation (IndicTrans2 / Google Translate).

## When to Use
- Use when implementing `src/voice/whisper_transcriber.py`.
- Use when implementing `src/translation/translator.py`.
- Use when a patient inputs text in Hindi, Tamil, Bengali, Telugu, Kannada, or other languages.
- Use when a patient uploads a voice file (.wav, .mp3, .ogg).
- Use when debugging language detection or translation quality issues.
- Use when adding support for a new language.

## Inputs Expected

### Text Input
```json
{
  "raw_input": "मुझे तीन दिनों से बुखार है और सिर दर्द हो रहा है",
  "language_hint": "hi",
  "input_source": "text"
}
```

### Voice Input
```json
{
  "audio_file_path": "/tmp/patient_audio.wav",
  "language_hint": "auto",
  "input_source": "voice"
}
```

## Output Format

```json
{
  "raw_input": "मुझे तीन दिनों से बुखार है और सिर दर्द हो रहा है",
  "translated_input": "I have had fever for three days and have a headache",
  "detected_language": "hi",
  "language_name": "Hindi",
  "translation_provider": "indicTrans2",
  "transcription_confidence": null,
  "translation_confidence": "high"
}
```

## Decision Rules

### Voice Processing Pipeline
```
Audio file (.wav / .mp3 / .ogg / .m4a)
    │
    ▼
Whisper.transcribe(audio, task="transcribe")
    → raw_text: transcribed text
    → whisper_lang: Whisper's detected language code
    │
    ▼
langdetect.detect(raw_text)
    → confirmed_lang: language code
    │
    ▼
IF confirmed_lang == "en":
    → translated_input = raw_text (no translation needed)
ELSE:
    → translate(raw_text, src=confirmed_lang, dest="en")
    → translated_input = English translation
```

### Text Processing Pipeline
```
User text input
    │
    ▼
IF language_hint == "auto" or not provided:
    detected_lang = langdetect.detect(raw_input)
ELSE:
    detected_lang = language_hint
    │
    ▼
IF detected_lang == "en":
    translated_input = raw_input
ELSE:
    translated_input = translate(raw_input, src=detected_lang, dest="en")
```

### Translation Provider Selection
```
Primary: IndicTrans2 (AI4Bharat)
  - Use for: hi, ta, te, bn, kn, ml, mr, pa, gu, or, as
  - Advantages: Best Indic language quality, runs offline
  - Requirement: Model loaded at startup (~1GB)

Fallback: Google Translate API
  - Use for: non-Indic languages or if IndicTrans2 unavailable
  - Advantages: 100+ languages, reliable, simple
  - Cost: $20/million characters

Selection logic:
  IF TRANSLATE_PROVIDER=indicTrans2 AND language in INDIC_LANGUAGES:
      use IndicTrans2
  ELSE:
      use Google Translate
```

### Whisper Model Selection
```
WHISPER_MODEL=base    → Fast, lower accuracy (~39MB)
WHISPER_MODEL=small   → Better accuracy (~244MB)
WHISPER_MODEL=medium  → Best accuracy (~769MB)

Demo/Kaggle: base (CPU-friendly)
Production: small or medium
```

### Supported Languages (v1)

| Code | Language | Script |
|---|---|---|
| en | English | Latin |
| hi | Hindi | Devanagari |
| ta | Tamil | Tamil |
| bn | Bengali | Bengali |
| te | Telugu | Telugu |
| kn | Kannada | Kannada |
| ml | Malayalam | Malayalam |
| mr | Marathi | Devanagari |

### Response Translation Back to Patient Language
```python
def translate_response(english_response: str, target_lang: str) -> str:
    if target_lang == "en":
        return english_response
    return translator.translate(english_response, src="en", dest=target_lang)
```

Apply to: `health_guidance`, `followup_plan text`, `emergency_alert`
Do NOT translate: `rag_sources`, `triage_level` codes, `session_id`

### Language Detection Confidence
```python
from langdetect import detect_langs

detections = detect_langs(text)
top = detections[0]
if top.prob > 0.95:
    confidence = "high"
elif top.prob > 0.75:
    confidence = "medium"
else:
    confidence = "low"
    # If low: default to "en" and add UI note
```

## Safety Rules
- Audio files must be processed locally (Whisper) — no audio sent to external APIs.
- Language detection must complete before any LLM call — LLM always receives English.
- Translation of responses back to the patient language must NOT alter safety-critical content (emergency numbers, disclaimer, triage level).
- Emergency contact numbers (112, 108) must remain in English numerals in all translated responses.
- Disclaimer must be translated (patients must understand it in their language).
- If translation confidence is low: add note "Response shown in English as translation quality was low."

## Example Input (Voice)
```
Audio file: patient saying "मुझे तीन दिनों से बुखार है"
            (I have had fever for three days)
```

## Example Output (Voice)
```json
{
  "raw_input": "मुझे तीन दिनों से बुखार है",
  "translated_input": "I have had fever for three days",
  "detected_language": "hi",
  "language_name": "Hindi",
  "translation_provider": "indicTrans2",
  "transcription_confidence": "medium"
}
```

## Example Input (Text — Hindi)
```json
{
  "raw_input": "मुझे सांस लेने में तकलीफ हो रही है",
  "input_source": "text"
}
```

## Example Output (Text — Hindi)
```json
{
  "translated_input": "I am having difficulty breathing",
  "detected_language": "hi",
  "translation_provider": "indicTrans2"
}
```
Note: "difficulty breathing" triggers emergency flag before LLM call.

## Failure Handling
- **Whisper fails / audio corrupt:** Prompt user to type symptoms. Log failure. Do not crash pipeline.
- **Whisper model not loaded:** Fall back to text input only. Show message: "Voice processing unavailable. Please type your symptoms."
- **IndicTrans2 unavailable:** Switch to Google Translate. Log fallback event.
- **Google Translate API key missing:** Proceed in English. Add note: "Translation unavailable — response in English."
- **Language detection fails:** Default to "en". Do not block pipeline.
- **Audio too long (> 60 seconds):** Truncate to first 60 seconds. Inform user: "Only first 60 seconds of audio processed."
- **Unsupported audio format:** Inform user. List supported formats: .wav, .mp3, .ogg, .m4a.
