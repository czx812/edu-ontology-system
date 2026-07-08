from fastapi import APIRouter

from services.llm_service import LLMResponseParseError, LLMService, LLMServiceError, extract_llm_content


router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/llm-config")
def llm_config() -> dict:
    service = LLMService()
    return service.config()


@router.get("/llm-test")
def llm_test() -> dict:
    service = LLMService()
    try:
        data = service.chat_completion(
            [{"role": "user", "content": "只回复OK"}],
            temperature=0.0,
            json_mode=False,
        )
        raw = data.get("raw_response", {})
        content = extract_llm_content(raw)
        return {
            "ok": True,
            "status_code": data.get("status_code", 200),
            "provider": service.provider,
            "base_url": service.base_url,
            "model": service.model,
            "api_key_suffix": service.api_key_suffix,
            "response_keys": list(raw.keys()),
            "content_extract_ok": True,
            "content_preview": str(content)[:200],
            "usage": data.get("usage", {}),
        }
    except LLMResponseParseError as exc:
        return {
            "ok": False,
            "status_code": exc.status_code,
            "provider": service.provider,
            "base_url": service.base_url,
            "model": service.model,
            "api_key_suffix": service.api_key_suffix,
            "response_keys": exc.response_keys,
            "content_extract_ok": False,
            "error_type": exc.error_type,
            "error": str(exc),
        }
    except LLMServiceError as exc:
        return {
            "ok": False,
            "status_code": exc.status_code,
            "provider": service.provider,
            "base_url": service.base_url,
            "model": service.model,
            "api_key_suffix": service.api_key_suffix,
            "response_keys": exc.response_keys,
            "content_extract_ok": False,
            "error_type": exc.error_type,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "provider": service.provider,
            "base_url": service.base_url,
            "model": service.model,
            "api_key_suffix": service.api_key_suffix,
            "response_keys": [],
            "content_extract_ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
