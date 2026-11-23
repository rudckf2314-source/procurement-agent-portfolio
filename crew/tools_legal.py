try:
    from crewai_tools import tool
except ImportError:
    try:
        from crewai.tools import tool
    except ImportError:
        from crewai import tool

import json
from datetime import datetime
from core.legal_cache import load_cached_legal_data, save_cached_legal_data

@tool("Legal Search Tool")
def legal_tool(query: str):
    """
    기획재정부 고시 금액, 중소기업 범위, 적격심사 기준 등 최신 조달 관련 법령 정보를 조회합니다. 
    입력으로 검색 키워드를 받습니다.
    (데이터는 6개월 주기로 갱신되며, 캐시를 우선 확인합니다.)
    """
    return _legal_search_logic(query)


from core.legal_rule_provider import get_or_update_legal_rules

def _legal_search_logic(query: str) -> str:
    """
    법령 정보 조회 로직
    - core.legal_rule_provider를 통해 중앙화된 법령/규칙 데이터를 반환합니다.
    """
    # 중앙 Provider를 통해 최신 규칙(API 연동 포함) 가져오기
    rules_data = get_or_update_legal_rules()
    
    return json.dumps(rules_data, ensure_ascii=False, indent=2)
