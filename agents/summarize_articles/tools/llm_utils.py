"""
Module: llm_utils
Component: Utility Function
Purpose: Article Summarization with Mistral API

Description:
Provides helper functions to interact with the Mistral LLM for summarizing text.
This module is used by ClearCoreAI agents to offload summarization tasks reliably.

Philosophy:
- Input text must be non-empty and explicitly validated.
- Only known models are used; no speculative logic or fallback chains.
- Waterdrop cost is fixed per call for predictable energy tracking.

Initial State:
- Article text is passed as a valid non-empty string
- A valid Mistral API key is provided as input

Final State:
- A clean, trimmed summary is returned along with its waterdrop cost

Version: 0.1.0
Validated by: Olivier Hays
Date: 2025-06-14

Estimated Water Cost:
- 2 waterdrops per call (default estimate)
"""

import requests

def summarize_with_mistral(article_text: str, api_key: str) -> tuple[str, int]:
    """
    Summarizes a single article using the Mistral API.

    Parameters:
        article_text (str): Full raw content of the article to be summarized.
        api_key (str): Valid API key for accessing the Mistral endpoint.

    Returns:
        tuple[str, int]: A tuple with the generated summary (str) and fixed waterdrop cost (int).

    Initial State:
        - article_text is a valid non-empty string
        - api_key is provided and has permission to access Mistral API

    Final State:
        - Mistral is called with the article text
        - A summary is returned (stripped and clean)
        - Water cost is fixed at 2 drops per summarization

    Raises:
        ValueError: If the input text is empty or not a string
        Exception: If the API call fails or the result cannot be parsed

    Water Cost:
        - 2 waterdrops per call (fixed estimate)
    """
    if not article_text or not isinstance(article_text, str):
        raise ValueError("Article text must be a non-empty string.")

    try:
        mistral_endpoint = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mistral-small",
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