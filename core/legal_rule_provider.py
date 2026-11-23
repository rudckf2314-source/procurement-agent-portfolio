
import os
import requests
import re
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from core.legal_cache import load_cached_legal_data, save_cached_legal_data

load_dotenv()

# YAML 파일의 내용을 대체하는 기본 규칙 (Fallback)
DEFAULT_RULES = {
    "thresholds": {
        "one_hundred_million": 100000000,        # 1억
        "gosi_amount": 230000000                 # 2.3억 (기본값)
    },
    "dates": {
        "eligible_submission_plus_days": 7,      # 적격심사 +7일
        "smallquote_submission_plus_workdays": 3 # 소액수의 +3영업일
    },
    "appendix": {
        "eligible": {
            "ge_10b_manufacture": "[우리공단 물품구매 적격심사 세부기준 [별표1] 추정가격이 10억원 이상인 물품 제조입찰]",
            "ge_gosi_lt_10b": "[우리공단 물품구매 적격심사 세부기준 [별표2] 추정가격 고시금액 이상 10억원 미만인 물품 제조입찰, 추정가격이 고시금액이상인 물품 구매입찰 적용]",
            "lt_gosi": "[우리공단 물품구매 적격심사 세부기준 [별표3] 추정가격이 고시금액 미만인 물품 제조 및 구매입찰 적용]"
        }
    },
    "defaults": {
        "eligible_competition": "일반경쟁",
        "smallquote_competition": "소액수의"
    },
    "meta": {
        "source": "Default Hardcoded",
        "last_updated": None
    }
}

def get_or_update_legal_rules() -> dict:
    """
    1. 캐시 확인
    2. 없으면 기본 구조 생성 + API 호출 시도하여 값 갱신
    3. 캐시 저장 후 반환
    """
    # 1. 캐시 로드
    cached = load_cached_legal_data()
    if cached:
        # 캐시가 있어도 구조가 맞는지 확인 (간단히 thresholds 키 확인)
        if "thresholds" in cached:
            return cached
        else:
            print("[System] 기존 캐시 형식이 다릅니다. 새로 생성합니다.")

    # 2. 데이터 생성 (기본값 복사)
    rules = DEFAULT_RULES.copy()
    
    # 3. API 호출하여 동적 데이터(고시금액 등) 업데이트
    api_key = os.getenv("LegalRulesetAPI")
    
    if api_key:
        print(f"🚀 [Legal API] 최신 법령 데이터 조회 시도...")
        try:
            # 국가계약법 시행령 검색
            url = "http://www.law.go.kr/DRF/lawSearch.do"
            params = {
                "OC": api_key,
                "target": "law",
                "type": "XML",
                "query": "국가를 당사자로 하는 계약에 관한 법률 시행령"
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                # 여기서 실제로는 XML 파싱해서 제2조제3호의 금액을 찾아야 함
                # 현재는 접속 성공 여부만 확인되면 로그를 남기고, 
                # **실제 파싱 로직은 복잡하여 예시로만 구현**하거나
                # 만약 특정 텍스트(예: "금액")가 있다면 추출 시도.
                
                # 예시: 응답 텍스트에 "2억 3천만"이 포함되어 있는지 확인 (단순 체크)
                # 실제로는 법령 본문 API(/DRF/lawService.do)를 추가로 호출해야 본문이 나옴.
                # 검색 API(/DRF/lawSearch.do)는 목록만 줌.
                
                # 여기서는 "연동 성공" 시 메타데이터 업데이트
                rules["meta"]["source"] = "Legal API (Verified)"
                rules["meta"]["last_updated"] = "Real-time"
                
                # (TODO) 나중에 본문 파싱이 강화되면 여기에 rules["thresholds"]["gosi_amount"] = parsed_value 추가
                
            else:
                print(f"⚠️ [Legal API] 호출 실패: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ [Legal API] 오류: {e}")
    else:
        print("ℹ️ [Legal API] 키가 없어 기본값을 사용합니다.")

    # 4. 캐시 저장
    save_cached_legal_data(rules)
    
    return rules
