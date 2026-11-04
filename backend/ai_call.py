"""AI_CALL: talks to model APIs (OpenAI / Meta responses API).
call(preset, system, user, effort, max_tokens, api_key, ...)
   OUT: dict(text, usage={prompt, completion, reasoning}, error)"""
import json, time, urllib.request, urllib.error
try:
    import requests
except ImportError:
    requests = None


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
    if not isinstance(data, dict): return ""
    # Responses API streaming emits text in delta events. Accept only visible
    # output-text deltas; never collect reasoning or reasoning-summary deltas.
    event_type = data.get("type", "")
    if event_type in ("response.output_text.delta", "output_text.delta"):
        delta = data.get("delta")
        return delta if isinstance(delta, str) else ""
    if "output_text" in data and isinstance(data["output_text"], str): return data["output_text"]
    if "output" in data:
        out = data["output"]
        if isinstance(out, str): return out
        if isinstance(out, list):
            texts = []
            for item in out:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, dict):
                    # Never expose reasoning items in place of the requested
                    # final body tree or factual interval description.
                    if str(item.get("type", "")).startswith("reasoning"):
                        continue
                    content = item.get("content")
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, str):
                                texts.append(c)
                            elif isinstance(c, dict):
                                if str(c.get("type", "")).startswith("reasoning"):
                                    continue
                                t = c.get("text") or c.get("content") or ""
                                if t: texts.append(t)
                    elif isinstance(content, str): texts.append(content)
                    elif "text" in item and isinstance(item["text"], str): texts.append(item["text"])
            if texts: return "".join(texts)
        if isinstance(out, dict): return out.get("text") or out.get("content") or ""
    if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
        c = data["choices"][0]
        if isinstance(c, dict):
            msg = c.get("message")
            if isinstance(msg, dict): return msg.get("content") or ""
            if isinstance(msg, str): return msg
            return c.get("text") or ""
    if "response" in data and isinstance(data["response"], str): return data["response"]
    if "response" in data and isinstance(data["response"], dict): return _extract_text(data["response"])
    return ""


def call(preset, system, user, effort, max_tokens, api_key, timeout=120, retries=2, post=_http_post, sleep=time.sleep, on_event=None):
    t0 = time.time()
    if on_event: on_event("ai_start", dict(model=preset["model"], max_tokens=max_tokens))
    
    is_meta = "meta.ai" in preset.get("base", "")
    err = "unknown"

    for attempt in range(retries + 1):
        try:
            if is_meta and requests:
                # Meta AI specific request (using requests library as requested)
                url = preset["base"] + "/responses"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream",
                }
                payload = {
                    "model": preset["model"],
                    "input": [{"role": preset["role"], "content": system}, {"role": "user", "content": user}],
                    "stream": True,
                    "temperature": 1,
                    # Respect the caller's per-purpose budget. The previous
                    # hard-coded 32k cap made even short digest calls unbounded.
                    "max_output_tokens": max(1, int(max_tokens)),
                    "top_p": 1,
                }
                if preset["effort"] and effort and effort != "none":
                    payload["reasoning"] = {"effort": effort}
                
                resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
                if resp.status_code != 200:
                    try: d = resp.json()
                    except: d = resp.text
                    err = f"Meta HTTP {resp.status_code}: {d}"
                    if resp.status_code in (429, 500, 502, 503, 504): raise Exception(err)
                    break # Fatal error

                output_text_deltas = []
                done_text_candidates = []
                completed_text_candidates = []
                usage = {"prompt": 0, "completion": 0, "reasoning": 0}
                try:
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        decoded = line.decode("utf-8")
                        if not decoded.startswith("data: "):
                            continue
                        try:
                            chunk = json.loads(decoded[6:])
                            event_type = chunk.get("type", "")
                            if event_type in ("response.output_text.delta", "output_text.delta"):
                                delta = chunk.get("delta")
                                if isinstance(delta, str):
                                    output_text_deltas.append(delta)
                            elif event_type in ("response.output_text.done", "output_text.done"):
                                done_text = chunk.get("text")
                                if isinstance(done_text, str):
                                    done_text_candidates.append(done_text)
                            else:
                                piece = _extract_text(chunk)
                                if piece:
                                    completed_text_candidates.append(piece)
                            usage_data = chunk.get("usage")
                            if not usage_data and isinstance(chunk.get("response"), dict):
                                usage_data = chunk["response"].get("usage")
                            if usage_data:
                                u = usage_data
                                usage["prompt"] = u.get("input_tokens") or u.get("prompt_tokens") or usage["prompt"]
                                usage["completion"] = u.get("output_tokens") or u.get("completion_tokens") or usage["completion"]
                                od = u.get("output_tokens_details") or u.get("completion_tokens_details") or {}
                                usage["reasoning"] = od.get("reasoning_tokens") or u.get("reasoning_tokens") or usage["reasoning"]
                        except (TypeError, ValueError, AttributeError):
                            continue
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass

                full_text = (
                    "".join(output_text_deltas)
                    if output_text_deltas
                    else "".join(done_text_candidates)
                    if done_text_candidates
                    else "".join(completed_text_candidates)
                )
                elapsed_ms = int((time.time() - t0) * 1000)
                res = dict(text=full_text, error=None, elapsed_ms=elapsed_ms, usage=usage)
                if on_event: on_event("ai_done", dict(model=preset["model"], elapsed_ms=elapsed_ms, usage=res["usage"]))
                return res

            else:
                # Generic provider (Baseten) using standard format and urllib
                ep = preset.get("endpoint", "/chat/completions")
                url, headers = preset["base"] + ep, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                body = {
                    "model": preset["model"],
                    "max_tokens": max_tokens,
                    "messages": [{"role": preset["role"], "content": system}, {"role": "user", "content": user}],
                }
                if preset["effort"] and effort and effort != "none":
                    body["reasoning_effort" if "/chat/completions" in ep else "reasoning"] = effort if "/chat/completions" in ep else {"effort": effort}
                
                status, data, hdr = post(url, headers, body, timeout)
                if status == 200:
                    msg = _extract_text(data)
                    u = data.get("usage") or {}
                    p_toks = u.get("prompt_tokens") or u.get("input_tokens") or 0
                    c_toks = u.get("completion_tokens") or u.get("output_tokens") or 0
                    od = u.get("output_tokens_details") or u.get("completion_tokens_details") or {}
                    r_toks = od.get("reasoning_tokens") or u.get("reasoning_tokens") or 0
                    elapsed_ms = int((time.time() - t0) * 1000)
                    res = dict(text=msg, error=None, elapsed_ms=elapsed_ms, usage=dict(prompt=p_toks, completion=c_toks, reasoning=r_toks))
                    if on_event: on_event("ai_done", dict(model=preset["model"], elapsed_ms=elapsed_ms, usage=res["usage"]))
                    return res
                
                err = f"{preset['model']} HTTP {status}: {data}"
                if status in (0, 429) or status >= 500: raise Exception(err)
                break

        except Exception as e:
            err = str(e)
            if on_event: on_event("ai_retry", dict(model=preset["model"], attempt=attempt + 1, error=err))
            sleep(min(2 ** attempt, 30))

    elapsed_ms = int((time.time() - t0) * 1000)
    if on_event: on_event("ai_error", dict(model=preset["model"], elapsed_ms=elapsed_ms, error=err))
    return dict(text="", usage=dict(prompt=0, completion=0, reasoning=0), elapsed_ms=elapsed_ms, error=err)
