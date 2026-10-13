import os
from threading import Semaphore
import httpx

_llm_slot = Semaphore(1)
PROVIDERS = {"openai": "OPENAI", "gemini": "GEMINI", "claude": "ANTHROPIC"}


def provider_config(provider):
    if provider not in PROVIDERS:
        raise ValueError("Nhà cung cấp LLM không hợp lệ.")
    prefix = PROVIDERS[provider]
    key = os.getenv(f"{prefix}_API_KEY", "")
    model = os.getenv(f"{prefix}_MODEL", "")
    if not model and os.getenv("LLM_PROVIDER") == provider:
        model = os.getenv("LLM_MODEL", "")
    return key, model


def available_providers():
    return [{"id": p, "configured": bool(provider_config(p)[0] and provider_config(p)[1]),
             "model": provider_config(p)[1]} for p in PROVIDERS]


def generate_shorts_text(prompt, provider):
    return call_llm(prompt, provider)


def call_llm(prompt, provider, max_tokens=6000, json_mode=True, timeout=120):
    key, model = provider_config(provider)
    if not key or not model:
        raise ValueError("Chưa cấu hình API key/model. Bạn vẫn có thể dùng Copy Prompt và dán kết quả.")
    if len(prompt) > 300000:
        raise ValueError("Transcript quá dài cho chế độ API. Hãy dùng Copy Prompt hoặc chia video.")
    if provider == "openai":
        url = "https://api.openai.com/v1/responses"
        headers, body = {"Authorization": f"Bearer {key}"}, {"model": model, "input": prompt, "store": False, "max_output_tokens": max_tokens}
    elif provider == "gemini":
        from urllib.parse import quote
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent"
        headers = {"x-goog-api-key": key}
        config = {"maxOutputTokens": max_tokens, **({"responseMimeType": "application/json"} if json_mode else {})}
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": config}
    else:
        url = "https://api.anthropic.com/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    with _llm_slot:
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=timeout, follow_redirects=False)
            if response.status_code >= 300:
                raise RuntimeError(f"API LLM trả lỗi HTTP {response.status_code}. Kiểm tra key/model hoặc dùng Copy Prompt.")
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise RuntimeError("Không kết nối được API LLM. Bạn có thể dùng Copy Prompt.") from None
    try:
        if provider == "openai":
            text = "\n".join(c["text"] for item in data.get("output", []) for c in item.get("content", []) if c.get("type") == "output_text")
        elif provider == "gemini":
            text = "\n".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"] if not p.get("thought"))
        else:
            text = "\n".join(c["text"] for c in data["content"] if c.get("type") == "text")
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("API LLM trả dữ liệu không hợp lệ. Hãy dùng Copy Prompt.") from None
    if not text.strip():
        raise RuntimeError("LLM chưa trả clip (có thể bị từ chối hoặc hết token). Hãy dùng Copy Prompt.")
    return text
