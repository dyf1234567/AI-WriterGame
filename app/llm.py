"""模型调用封装：OpenAI 兼容接口 + 容错的 JSON 解析。"""
import json
import re
import time
import logging
from contextlib import contextmanager
from contextvars import ContextVar

from openai import OpenAI

from .config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

_client: OpenAI | None = None
_deadline = ContextVar("model_deadline", default=None)
logger = logging.getLogger(__name__)


class ModelServiceError(RuntimeError):
    pass


@contextmanager
def request_budget(seconds=65):
    token = _deadline.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)


def _timeout():
    deadline = _deadline.get()
    remaining = deadline - time.monotonic() if deadline else 25
    if remaining <= 0:
        raise ModelServiceError("本回合生成已超时，进度未提交，请稍后重试。")
    return min(25, remaining)


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, timeout=25, max_retries=0)
    return _client


def extract_json(text: str) -> dict:
    """从模型回复中尽力提取 JSON 对象（容忍代码围栏与前后杂文）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        data = json.loads(text[start:end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("模型未返回合法 JSON")


def chat_json(system: str, user: str, temperature: float = 0.8, max_tokens: int = 2400) -> dict:
    """单轮对话并要求 JSON 输出。调用方负责重试。"""
    client = get_client()
    kwargs = dict(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    started = time.monotonic()
    try:
        try:
            resp = client.chat.completions.create(response_format={"type": "json_object"},
                                                  timeout=_timeout(), **kwargs)
        except Exception as exc:
            # 只有明确拒绝 response_format 的参数错误才允许降级；鉴权/限流不重发。
            message = str(exc).lower()
            unsupported = (getattr(exc, "status_code", 0) in (400, 422)
                           and ("response_format" in message or "json_object" in message)
                           and any(s in message for s in ("not support", "unsupported", "invalid", "不支持")))
            if not unsupported:
                raise
            resp = client.chat.completions.create(timeout=_timeout(), **kwargs)
    except ModelServiceError:
        raise
    except Exception as exc:
        code = getattr(exc, "status_code", 0)
        detail = {401: "模型密钥无效，请检查配置。", 403: "模型服务拒绝访问，请检查权限。",
                  429: "模型服务限流或额度不足，请稍后重试。"}.get(code,
                    "模型服务连接失败或超时，进度未提交，请稍后重试。")
        logger.warning("model request failed type=%s status=%s seconds=%.2f",
                       type(exc).__name__, code, time.monotonic() - started)
        raise ModelServiceError(detail) from exc
    logger.info("model request seconds=%.2f tokens=%s", time.monotonic() - started,
                getattr(getattr(resp, "usage", None), "total_tokens", None))
    return extract_json(resp.choices[0].message.content or "")
