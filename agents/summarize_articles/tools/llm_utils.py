"""
Module: llm_utils
Function: summarize_with_mistral

Description:
Tool function to interact with the Mistral API and generate a summary for a given article text.

Version: 0.1.0
Initial State: Receives article text and API key.
Final State: Returns the summary and estimated waterdrop consumption.

Exceptions handled:
- ValueError — if article is empty or invalid.
- Exception — general API or runtime failures.

Validation:
- Validated by: Olivier Hays
- Date: 2025-06-14

Estimated Water Cost:
- 2 waterdrops per call (default estimate)
"""

import requests

def summarize_with_mistral(article_text: str, api_key: str) -> tuple[str, int]:
    if not article_text or not isinstance(article_text, str):
        raise ValueError("Article text must be a non-empty string.")

    try:
        mistral_endpoint = "https://api.mistral.ai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistral-small",  # ou autre modèle selon ton abonnement
            "messages": [
                {"role": "system", "content": "You are a professional summarizer."},
                {"role": "user", "content": f"Summarize this article:\n{article_text}"}
            ],
            "temperature": 0.7
        }

        response = requests.post(mistral_endpoint, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        summary = result["choices"][0]["message"]["content"].strip()
        return summary, 2  # Waterdrop estimate

    except requests.exceptions.RequestException as e:
        raise Exception(f"Mistral API call failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error during summarization: {e}")