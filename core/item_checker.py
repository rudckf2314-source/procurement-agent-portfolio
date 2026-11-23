import os
import re
import json
import requests
from urllib.parse import unquote
from pathlib import Path
from typing import Dict, Any

# =========================
# 캐시 설정
# =========================
CACHE_DIR = Path(os.getcwd()) / "cache"
CACHE_FILE = CACHE_DIR / "api_validation_cache.json"

def load_cache() -> Dict[str, Any]:
    if not CACHE_FILE.exists():
        return {"items": {}, "industries": {}}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"items": {}, "industries": {}}

def save_cache(cache_data: Dict[str, Any]):
    if not CACHE_DIR.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

# =========================
# 1) 계획안 텍스트에서 후보 추출
# =========================
def extract_candidates_from_text(raw_text: str) -> dict:
    text = raw_text or ""

    # 공백/하이픈 제거한 버전(번호 추출 정확도↑)
    compact = re.sub(r"[\s\-]", "", text)

    # (A) 세부품명번호(10자리)
    item_codes_10 = sorted(set(re.findall(r"\b\d{10}\b", compact)))

    # (B) 업종번호(4자리) - "업종" 주변 우선
    industry_codes_4 = sorted(set(re.findall(r"(?:업종(?:코드|번호)?\s*[:：]?\s*)(\d{4})", text)))

    # (C) 품명(또는 세부품명/품목명) 1개
    item_name = ""
    m = re.search(r"(?:품명|품목명|세부품명)\s*[:：]\s*([^\n\r,]{2,60})", text)
    if m:
        item_name = m.group(1).strip()

    # (D) 업종명 1개 (업종: 0036 같은 “코드만”은 제외)
    industry_name = ""
    m2 = re.search(r"(?:업종명|업종)\s*[:：]\s*([^\n\r,]{2,60})", text)
    if m2:
        cand = m2.group(1).strip()
        if not re.fullmatch(r"\d{4}", cand):
            industry_name = cand

    return {
        "item_codes_10": item_codes_10,
        "item_name": item_name,
        "industry_codes_4": industry_codes_4,
        "industry_name": industry_name,
    }


# =========================
# 2) 물품목록정보서비스 검증 (Cached)
# env: G2BNoticeAPI 사용
# =========================
def verify_items_with_api(item_codes_10=None, item_name: str = "") -> list:
    item_codes_10 = item_codes_10 or []
    api_key = os.getenv("G2BNoticeAPI", "").strip()
    
    # 캐시 로드
    cache = load_cache()
    cached_items = cache.get("items", {})
    updated = False

    service_key = unquote(api_key) if api_key else ""
    base = "https://apis.data.go.kr/1230000/ao/ThngListInfoService"
    endpoint = f"{base}/getPrdctClsfcNoUnit10Info"

    def call(params: dict) -> dict:
        q = {
            "serviceKey": service_key,
            "pageNo": "1",
            "numOfRows": "10",
            "type": "json",
            **params,
        }
        r = requests.get(endpoint, params=q, timeout=5) # 타임아웃 5초
        r.raise_for_status()
        return r.json()

    def get_first_item_name(data: dict) -> str:
        try:
            body = data.get("response", {}).get("body", {})
            items = body.get("items", [])
            
            tgt = None
            if isinstance(items, list) and items:
                tgt = items[0]
            elif isinstance(items, dict):
                it = items.get("item", [])
                if isinstance(it, dict):
                    tgt = it
                elif isinstance(it, list) and it:
                    tgt = it[0]
            
            if not tgt:
                return ""
            
            return (
                str(tgt.get("dtilPrdctClsfcNoNm", "")).strip()
                or str(tgt.get("prdctClsfcNm", "")).strip()
                or ""
            )
        except Exception:
            return ""

    rows = []

    # Helper
    def check_and_cache(key: str, params: dict):
        nonlocal updated
        if key in cached_items:
            return cached_items[key]
        
        if not api_key:
            return {"status": "API_ERROR", "매칭_품명": "", "메시지": "No API Key"}
        
        try:
            data = call(params)
            count = int(data.get("response", {}).get("body", {}).get("totalCount", 0))
            ok = count > 0
            name = get_first_item_name(data) if ok else ""
            
            result = {
                "status": "OK" if ok else "NOT_FOUND",
                "매칭_품명": name
            }
            cached_items[key] = result
            updated = True
            return result
        except Exception as e:
            return {"status": "API_ERROR", "매칭_품명": "", "메시지": str(e)}

    # (A) 세부품명번호
    for code in item_codes_10:
        res = check_and_cache(code, {"dtilPrdctClsfcNoBgnNo": code, "dtilPrdctClsfcNoEndNo": code})
        row = {"구분": "세부품명번호", "입력값": code, **res}
        rows.append(row)

    # (B) 품명
    if (not item_codes_10) and item_name:
        res = check_and_cache(item_name, {"dtilPrdctClsfcNoNm": item_name})
        row = {"구분": "품명", "입력값": item_name, **res}
        rows.append(row)

    if updated:
        cache["items"] = cached_items
        save_cache(cache)

    return rows


# =========================
# 3) 업종 및 근거법규서비스 검증 (Cached)
# env: QualificationRuleAPI 사용
# =========================
def verify_industry_with_api(industry_codes_4=None, industry_name: str = "") -> list:
    industry_codes_4 = industry_codes_4 or []
    api_key = os.getenv("QualificationRuleAPI", "").strip()

    # 캐시 로드
    cache = load_cache()
    cached_inds = cache.get("industries", {})
    updated = False

    service_key = unquote(api_key) if api_key else ""
    base = "https://apis.data.go.kr/1230000/ao/IndstrytyBaseLawrgltInfoService"
    endpoint = f"{base}/getIndstrytyBaseLawrgltInfoList"

    def call(params: dict) -> dict:
        q = {
            "serviceKey": service_key,
            "pageNo": "1",
            "numOfRows": "10",
            "type": "json",
            **params,
        }
        r = requests.get(endpoint, params=q, timeout=5)
        r.raise_for_status()
        return r.json()

    def get_first_ind_name(data: dict) -> str:
        try:
            body = data.get("response", {}).get("body", {})
            items = body.get("items", [])
            
            tgt = None
            if isinstance(items, list) and items:
                tgt = items[0]
            elif isinstance(items, dict):
                it = items.get("item", [])
                if isinstance(it, dict):
                    tgt = it
                elif isinstance(it, list) and it:
                    tgt = it[0]
            
            if tgt:
                return str(tgt.get("indstrytyNm", "")).strip()
            return ""
        except Exception:
            return ""

    rows = []

    def check_and_cache(key: str, params: dict):
        nonlocal updated
        if key in cached_inds:
            return cached_inds[key]
        
        if not api_key:
             return {"status": "API_ERROR", "매칭_업종명": "", "메시지": "No API Key"}

        try:
            data = call(params)
            count = int(data.get("response", {}).get("body", {}).get("totalCount", 0))
            ok = count > 0
            name = get_first_ind_name(data) if ok else ""
            
            result = {
                "status": "OK" if ok else "NOT_FOUND",
                "매칭_업종명": name
            }
            cached_inds[key] = result
            updated = True
            return result
        except Exception as e:
             return {"status": "API_ERROR", "매칭_업종명": "", "메시지": str(e)}

    # (A) 업종코드
    for code in industry_codes_4:
        res = check_and_cache(code, {"indstrytyCd": code})
        row = {"구분": "업종코드", "입력값": code, **res}
        rows.append(row)

    # (B) 업종명
    if (not industry_codes_4) and industry_name:
        res = check_and_cache(industry_name, {"indstrytyNm": industry_name})
        row = {"구분": "업종명", "입력값": industry_name, **res}
        rows.append(row)

    if updated:
        cache["industries"] = cached_inds
        save_cache(cache)

    return rows
