"""
Thin wrapper around the Groq API (OpenAI-compatible client) that:
  - forces JSON-only output (via response_format json_object)
  - validates the response against a Pydantic model
  - on validation failure, feeds the error back to the model and retries (bounded)
  - on rate-limit (429) errors, waits and retries automatically (separate from
    validation retries) since free-tier quotas are easy to hit
This is the low-level mechanism the repair engine builds on top of.

External interface (call_structured, LLMCallResult, MODEL_FAST, MODEL_STRONG) is unchanged,
so no other pipeline file needs to change.
"""
import json
import os
import re
import time
from typing import Type, TypeVar
from groq import Groq
import groq
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Lighter model used for both stages by default to conserve free-tier daily token budget.
# llama-3.3-70b-versatile gives better reasoning but burns through the 100k/day free limit
# fast (a single complex prompt with repairs can use 10-20k tokens). Bump MODEL_STRONG back
# up once you have a paid tier or more headroom.
MODEL_FAST = "llama-3.1-8b-instant"
MODEL_STRONG = "llama-3.1-8b-instant"

MAX_RETRIES = 3
MAX_RATE_LIMIT_RETRIES = 3
DEFAULT_RATE_LIMIT_WAIT_SECONDS = 15


class LLMCallResult:
    def __init__(self, data: dict, latency_ms: float, retries: int, raw_text: str):
        self.data = data
        self.latency_ms = latency_ms
        self.retries = retries
        self.raw_text = raw_text


def _extract_wait_seconds(error_message: str) -> float:
    """Parse Groq's 'Please try again in 3m57.6s' style message for an exact wait time."""
    match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", error_message)
    if not match:
        return DEFAULT_RATE_LIMIT_WAIT_SECONDS
    minutes = float(match.group(1)) if match.group(1) else 0
    seconds = float(match.group(2))
    return minutes * 60 + seconds + 1  # +1 second buffer


def _call_with_rate_limit_retry(model, messages):
    for rl_attempt in range(MAX_RATE_LIMIT_RETRIES):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=4000,
            )
        except groq.RateLimitError as e:
            wait_s = _extract_wait_seconds(str(e))
            if rl_attempt == MAX_RATE_LIMIT_RETRIES - 1:
                raise
            print(f"[rate limit] waiting {wait_s:.0f}s before retry ({rl_attempt+1}/{MAX_RATE_LIMIT_RETRIES})...")
            time.sleep(wait_s)
    raise RuntimeError("Unreachable")


def call_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    model: str = MODEL_STRONG,
    max_retries: int = MAX_RETRIES,
) -> LLMCallResult:
    """
    Calls Groq, demands raw JSON only, validates against `schema`.
    On parse/validation failure, re-prompts with the specific error so the model can
    self-correct -- this is targeted repair, not blind retry.
    On rate-limit errors, waits the suggested time and retries automatically.
    """
    start = time.time()
    last_error = None
    current_user_prompt = user_prompt
    attempts = 0

    full_system = (
        system_prompt
        + "\n\nCRITICAL: Respond with ONLY raw JSON. No markdown fences, "
        + "no preamble, no explanation. Follow the exact structure shown in the example above."
    )

    for attempt in range(max_retries):
        attempts += 1
        response = _call_with_rate_limit_retry(
            model=model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": current_user_prompt},
            ],
        )
        raw_text = response.choices[0].message.content

        try:
            parsed = json.loads(raw_text)
            validated = schema.model_validate(parsed)
            latency_ms = (time.time() - start) * 1000
            return LLMCallResult(
                data=validated.model_dump(), latency_ms=latency_ms, retries=attempt, raw_text=raw_text
            )
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
        except ValidationError as e:
            last_error = f"Schema validation failed: {e}"

        # Targeted re-prompt: tell the model exactly what was wrong.
        current_user_prompt = (
            f"{user_prompt}\n\n"
            f"Your previous response failed validation with this error:\n{last_error}\n"
            f"Your previous response was:\n{raw_text[:1500]}\n\n"
            f"Fix the issue and return ONLY corrected raw JSON matching the required schema."
        )

    raise ValueError(f"Failed to get valid structured output after {attempts} attempts. Last error: {last_error}")