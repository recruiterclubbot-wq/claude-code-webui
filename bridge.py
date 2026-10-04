#!/usr/bin/env python3
"""
Anthropic API to Google Gemini Bridge Server
Zero-dependency, uses standard library only (http.server, urllib, json, ssl).
Converts Anthropic Claude Code requests to Google Gemini 3.5 / 3.8 / Pro API,
supporting streaming SSE, non-streaming, function calling (tools), and system prompts.
"""

import os
import sys
import json
import time
import uuid
import ssl
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Bridge] %(message)s"
)
logger = logging.getLogger("ClaudeGeminiBridge")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CASCADE_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash"
]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def convert_anthropic_to_gemini(req_data):
    messages = req_data.get("messages", [])
    system = req_data.get("system")
    tools = req_data.get("tools")

    raw_contents = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        g_role = "user" if role == "user" else "model"

        parts = []
        if isinstance(content, str):
            if content.strip():
                parts.append({"text": content})
        elif isinstance(content, list):
            for block in content:
                b_type = block.get("type")
                if b_type == "text":
                    txt = block.get("text", "")
                    if txt:
                        parts.append({"text": txt})
                elif b_type == "tool_use":
                    parts.append({
                        "functionCall": {
                            "name": block.get("name"),
                            "args": block.get("input") or {}
                        }
                    })
                elif b_type == "tool_result":
                    res_content = block.get("content", "")
                    if isinstance(res_content, list):
                        res_content = " ".join([c.get("text", "") for c in res_content if isinstance(c, dict) and c.get("type") == "text"])
                    parts.append({
                        "functionResponse": {
                            "name": block.get("name") or "tool_result",
                            "response": {"output": str(res_content)}
                        }
                    })

        if parts:
            raw_contents.append({"role": g_role, "parts": parts})

    sanitized_contents = []
    last_role = None
    for c in raw_contents:
        if c["role"] == last_role and sanitized_contents:
            sanitized_contents[-1]["parts"].extend(c["parts"])
        else:
            sanitized_contents.append(c)
            last_role = c["role"]

    if not sanitized_contents:
        sanitized_contents = [{"role": "user", "parts": [{"text": "Hello"}]}]

    payload = {"contents": sanitized_contents}

    if system:
        sys_text = ""
        if isinstance(system, list):
            sys_text = "\n".join([b.get("text", "") for b in system if isinstance(b, dict) and b.get("text")])
        elif isinstance(system, str):
            sys_text = system
        if sys_text.strip():
            payload["systemInstruction"] = {"parts": [{"text": sys_text.strip()}]}

    if tools:
        declarations = []
        for t in tools:
            name = t.get("name")
            desc = t.get("description", "")
            schema = t.get("input_schema", {})
            if name:
                declarations.append({
                    "name": name,
                    "description": desc,
                    "parameters": schema
                })
        if declarations:
            payload["tools"] = [{"functionDeclarations": declarations}]

    return payload


def call_gemini(gemini_payload):
    last_error = None
    for model_name in CASCADE_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        data_bytes = json.dumps(gemini_payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, context=SSL_CTX, timeout=30) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                return resp_json, model_name
        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode("utf-8")
            except Exception:
                pass
            logger.warning(f"Gemini {model_name} HTTP {he.code}: {err_body[:200]}")
            last_error = he
            if he.code in (404, 429, 503):
                continue
            raise
        except Exception as e:
            logger.warning(f"Gemini {model_name} error: {e}")
            last_error = e
            continue

    if last_error:
        raise last_error
    raise RuntimeError("All Gemini models failed")


class BridgeHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/health", "/ping"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            resp = {
                "status": "healthy",
                "service": "Claude Code Google Gemini Bridge",
                "models": CASCADE_MODELS,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/v1/messages"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)
        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception as e:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
            return

        stream = bool(req_data.get("stream", False))
        requested_model = req_data.get("model", "claude-3-7-sonnet-20250219")
        msg_id = f"msg_{uuid.uuid4().hex[:24]}"

        try:
            gemini_payload = convert_anthropic_to_gemini(req_data)
            gemini_res, used_model = call_gemini(gemini_payload)

            candidates = gemini_res.get("candidates", [])
            parts = []
            finish_reason = "stop"
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                finish_reason = candidates[0].get("finishReason", "STOP").lower()

            anthropic_content = []
            has_tool_call = False
            for part in parts:
                if "text" in part and part["text"]:
                    anthropic_content.append({
                        "type": "text",
                        "text": part["text"]
                    })
                elif "functionCall" in part:
                    has_tool_call = True
                    fc = part["functionCall"]
                    tool_id = fc.get("id") or f"toolu_{uuid.uuid4().hex[:20]}"
                    anthropic_content.append({
                        "type": "tool_use",
                        "id": tool_id,
                        "name": fc.get("name"),
                        "input": fc.get("args") or {}
                    })

            if not anthropic_content:
                anthropic_content.append({"type": "text", "text": "OK"})

            stop_reason = "tool_use" if has_tool_call else "end_turn"

            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                def send_sse(event_name, data_obj):
                    line = f"event: {event_name}\ndata: {json.dumps(data_obj)}\n\n"
                    self.wfile.write(line.encode("utf-8"))
                    self.wfile.flush()

                send_sse("message_start", {
                    "type": "message_start",
                    "message": {
                        "id": msg_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [],
                        "model": requested_model,
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 50, "output_tokens": 1}
                    }
                })

                for idx, block in enumerate(anthropic_content):
                    b_type = block["type"]
                    if b_type == "text":
                        send_sse("content_block_start", {
                            "type": "content_block_start",
                            "index": idx,
                            "content_block": {"type": "text", "text": ""}
                        })
                        send_sse("content_block_delta", {
                            "type": "content_block_delta",
                            "index": idx,
                            "delta": {"type": "text_delta", "text": block["text"]}
                        })
                        send_sse("content_block_stop", {
                            "type": "content_block_stop",
                            "index": idx
                        })
                    elif b_type == "tool_use":
                        send_sse("content_block_start", {
                            "type": "content_block_start",
                            "index": idx,
                            "content_block": {
                                "type": "tool_use",
                                "id": block["id"],
                                "name": block["name"],
                                "input": {}
                            }
                        })
                        send_sse("content_block_delta", {
                            "type": "content_block_delta",
                            "index": idx,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": json.dumps(block["input"])
                            }
                        })
                        send_sse("content_block_stop", {
                            "type": "content_block_stop",
                            "index": idx
                        })

                send_sse("message_delta", {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": stop_reason,
                        "stop_sequence": None
                    },
                    "usage": {"output_tokens": 25}
                })

                send_sse("message_stop", {"type": "message_stop"})

            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                resp_obj = {
                    "id": msg_id,
                    "type": "message",
                    "role": "assistant",
                    "content": anthropic_content,
                    "model": requested_model,
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": 50,
                        "output_tokens": 25
                    }
                }
                self.wfile.write(json.dumps(resp_obj).encode("utf-8"))

        except Exception as err:
            logger.error(f"Error handling /v1/messages: {err}", exc_info=True)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            err_resp = {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": str(err)
                }
            }
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))


def run(port=8082):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, BridgeHTTPHandler)
    logger.info(f"Claude-to-Gemini Bridge listening on port {port} (Cascading models: {CASCADE_MODELS})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()


if __name__ == "__main__":
    p = int(os.getenv("BRIDGE_PORT", "8082"))
    run(p)
