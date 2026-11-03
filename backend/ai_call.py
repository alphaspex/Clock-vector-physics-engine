"""AI_CALL: the only file that talks to a model API (OpenAI / Meta responses API, plain urllib).
call(preset, system, user, effort, max_tokens, api_key, ...)
   IN : a provider preset (config.PROVIDERS), prompt texts, reasoning effort, token cap, key
   OUT: dict(text, usage={prompt, completion, reasoning}, error)   error is None on success
`post` and `sleep` can be swapped, so tests need no network."""
import json, time, urllib.request, urllib.error


def _http_post(url, headers, body, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try: data = json.loads(e.read() or b"{}")
        except Exception: data = {}
        return e.code, data, dict(e.headers)
    except Exception as e:
        return 0, {"error": {"message": str(e)}}, {}


def _extract_text(data):
    if not isinstance(data, dict):
        return ""
    if "output_text" in data and isinstance(data["output_text"], str):
        return data["output_text"]
    if "output" in data:
        out = data["output"]
        if isinstance(out, str):
            return out
        if isinstance(out, list) and len(out) > 0:
            first = out[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("text") or first.get("content") or (first.get("message", {}).get("content") if isinstance(first.get("message"), dict) else "")
        if isinstance(out, dict):
            return out.get("text") or out.get("content") or ""
    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
        c = data["choices"][0]
        if isinstance(c, dict):
            msg = c.get("message")
            if isinstance(msg, dict):
                return msg.get("content") or ""
            if isinstance(msg, str):
                return msg
            return c.get("text") or ""
    if "response" in data and isinstance(data["response"], str):
        return data["response"]
    return ""


def call(preset, system, user, effort, max_tokens, api_key, timeout=120, retries=3, post=_http_post, sleep=time.sleep, on_event=None):
    t0 = time.time()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    primary_ep = preset.get("endpoint", "/responses" if "meta.ai" in preset.get("base", "") else "/chat/completions")
    fallback_ep = "/chat/completions" if primary_ep == "/responses" else "/responses"
    
    if on_event:
        on_event("ai_start", dict(model=preset["model"], max_tokens=max_tokens))

    err = "unknown"
    for attempt in range(retries + 1):
        # Try primary endpoint, then fallback endpoint if primary returns 404
        endpoints = [primary_ep, fallback_ep]
        for ep_idx, ep in enumerate(endpoints):
            url = preset["base"] + ep
            
            if ep == "/responses":
                body = {
                    "model": preset["model"],
                    "input": f"{system}\n\n{user}" if system else user,
                    "instructions": system,
                    "messages": [{"role": preset["role"], "content": system}, {"role": "user", "content": user}],
                    "max_tokens": max_tokens,
                    "max_output_tokens": max_tokens,
                }
                if preset["effort"] and effort:
                    body["reasoning_effort"] = effort
            else:
                body = {
                    "model": preset["model"],
                    "max_tokens": max_tokens,
                    "messages": [{"role": preset["role"], "content": system}, {"role": "user", "content": user}],
                }
                if preset["effort"] and effort:
                    body["reasoning_effort"] = effort

            status, data, hdr = post(url, headers, body, timeout)

            if status == 200:
                try:
                    msg = _extract_text(data)
                    u = data.get("usage") or {}
                    if not isinstance(u, dict): u = {}
                    elapsed_ms = int((time.time() - t0) * 1000)
                    res = dict(
                        text=msg,
                        error=None,
                        elapsed_ms=elapsed_ms,
                        usage=dict(
                            prompt=u.get("prompt_tokens") or u.get("input_tokens") or 0,
                            completion=u.get("completion_tokens") or u.get("output_tokens") or 0,
                            reasoning=(u.get("completion_tokens_details") or {}).get("reasoning_tokens") or u.get("reasoning_tokens") or 0,
                        ),
                    )
                    if on_event:
                        on_event("ai_done", dict(model=preset["model"], elapsed_ms=elapsed_ms, usage=res["usage"]))
                    return res
                except Exception as ex:
                    err = f"{preset['model']}: unexpected response shape: {repr(ex)}"
                    break

            err = f"{preset['model']} HTTP {status}: {(data.get('error') or {}).get('message', data) if isinstance(data, dict) else data}"

            # If 404 on primary endpoint, attempt fallback endpoint
            if status == 404 and ep_idx == 0:
                continue

            # If transient error (0, 429, 5xx), back off and retry
            if status in (0, 429) or status >= 500:
                if on_event:
                    on_event("ai_retry", dict(model=preset["model"], attempt=attempt + 1, error=err))
                wait = float(hdr.get("Retry-After", 2 ** attempt)) if str(hdr.get("Retry-After", "")).replace(".", "").isdigit() else 2 ** attempt
                sleep(min(wait, 30))
                break

            break

    elapsed_ms = int((time.time() - t0) * 1000)
    if on_event:
        on_event("ai_error", dict(model=preset["model"], elapsed_ms=elapsed_ms, error=err))
    return dict(text="", usage=dict(prompt=0, completion=0, reasoning=0), elapsed_ms=elapsed_ms, error=err)
