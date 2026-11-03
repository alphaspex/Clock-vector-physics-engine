"""AI_CALL: the only file that talks to a model API (OpenAI-style chat completions, plain urllib).
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


def call(preset, system, user, effort, max_tokens, api_key, timeout=120, retries=3, post=_http_post, sleep=time.sleep, on_event=None):
    t0 = time.time()
    body = {"model": preset["model"], "max_tokens": max_tokens,
            "messages": [{"role": preset["role"], "content": system}, {"role": "user", "content": user}]}
    if preset["effort"] and effort:
        body["reasoning_effort"] = effort
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    err = "unknown"
    if on_event:
        on_event("ai_start", dict(model=preset["model"], max_tokens=max_tokens))
    for attempt in range(retries + 1):
        status, data, hdr = post(preset["base"] + "/chat/completions", headers, body, timeout)
        if status == 200:
            try:
                msg = data["choices"][0]["message"].get("content") or ""
                u = data.get("usage", {})
                elapsed_ms = int((time.time() - t0) * 1000)
                res = dict(text=msg, error=None, elapsed_ms=elapsed_ms, usage=dict(
                    prompt=u.get("prompt_tokens", 0), completion=u.get("completion_tokens", 0),
                    reasoning=(u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)))
                if on_event:
                    on_event("ai_done", dict(model=preset["model"], elapsed_ms=elapsed_ms, usage=res["usage"]))
                return res
            except (KeyError, IndexError, TypeError):
                err = f"{preset['model']}: unexpected response shape"; break
        err = f"{preset['model']} HTTP {status}: {(data.get('error') or {}).get('message', data) if isinstance(data, dict) else data}"
        if status in (0, 429) or status >= 500:
            if on_event:
                on_event("ai_retry", dict(model=preset["model"], attempt=attempt + 1, error=err))
            wait = float(hdr.get("Retry-After", 2 ** attempt)) if str(hdr.get("Retry-After", "")).replace(".", "").isdigit() else 2 ** attempt
            sleep(min(wait, 30)); continue
        break
    elapsed_ms = int((time.time() - t0) * 1000)
    if on_event:
        on_event("ai_error", dict(model=preset["model"], elapsed_ms=elapsed_ms, error=err))
    return dict(text="", usage=dict(prompt=0, completion=0, reasoning=0), elapsed_ms=elapsed_ms, error=err)

