# utils/data_lookup.py
"""
챗봇이 사용할 데이터 조회 함수들
- SMPP 캐시에서 품명코드 검색
- API 검증 캐시에서 업종명/품명 검색
"""

import json
import os
from typing import Optional, Dict

def get_item_name_from_cache(item_code: str) -> Optional[str]:
    """
    API 검증 캐시에서 품명코드로 품명 조회
    
    Args:
        item_code: 세부품명번호 (10자리)
    
    Returns:
        품명 또는 None
    """
    try:
        # 프로젝트 루트 찾기
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_file = os.path.join(current_dir, "cache", "api_validation_cache.json")
        
        if not os.path.exists(cache_file):
            return None
        
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        items = cache_data.get("items", {})
        if item_code in items:
            return items[item_code].get("매칭_품명")
        
        return None
    except Exception as e:
        print(f"품명 조회 오류: {e}")
        return None


def get_industry_name_from_cache(industry_code: str) -> Optional[str]:
    """
    API 검증 캐시에서 업종코드로 업종명 조회
    
    Args:
        industry_code: 업종코드 (4자리)
    
    Returns:
        업종명 또는 None
    """
    try:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_file = os.path.join(current_dir, "cache", "api_validation_cache.json")
        
        if not os.path.exists(cache_file):
            return None
        
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        industries = cache_data.get("industries", {})
        if industry_code in industries:
            return industries[industry_code].get("매칭_업종명")
        
        return None
    except Exception as e:
        print(f"업종명 조회 오류: {e}")
        return None


def search_in_smpp_database(item_code: str) -> Dict[str, any]:
    """
    SMPP 데이터베이스에서 품명코드가 제한 대상인지 확인
    
    Args:
        item_code: 세부품명번호 (10자리)
    
    Returns:
        {
            "found": bool,
            "item_code": str,
            "is_restricted": bool,
            "notice_info": dict (고시 정보)
        }
    """
    try:
        from core.smpp_download import load_smpp_from_cache, smpp_database_num
        
        atchFileId = smpp_database_num["atchFileId"]
        cached_data = load_smpp_from_cache(atchFileId)
        
        if not cached_data:
            return {
                "found": False,
                "item_code": item_code,
                "error": "SMPP 캐시가 없습니다. 데이터를 새로고침해주세요."
            }
        
        item_codes = set(cached_data.get("item_codes", []))
        is_restricted = item_code in item_codes
        
        metadata = cached_data.get("metadata", {})
        notice_info = metadata.get("notice_info", {})
        
        return {
            "found": True,
            "item_code": item_code,
            "is_restricted": is_restricted,
            "notice_info": notice_info,
            "total_restricted_items": metadata.get("total_count", 0)
        }
    except Exception as e:
        return {
            "found": False,
            "item_code": item_code,
            "error": f"SMPP 조회 오류: {str(e)}"
        }


def lookup_item_code(item_code: str) -> Dict[str, any]:
    """
    품명코드에 대한 모든 정보 조회 (통합)
    
    Args:
        item_code: 세부품명번호 (10자리)
    
    Returns:
        {
            "item_code": str,
            "item_name": str or None,
            "is_restricted": bool,
            "notice_info": dict,
            "source": str (어디서 정보를 가져왔는지)
        }
    """
    # 1. API 검증 캐시에서 품명 조회
    item_name = get_item_name_from_cache(item_code)
    
    # 2. SMPP 데이터베이스에서 제한 여부 확인
    smpp_result = search_in_smpp_database(item_code)
    
    return {
        "item_code": item_code,
        "item_name": item_name,
        "is_restricted": smpp_result.get("is_restricted", False),
        "notice_info": smpp_result.get("notice_info", {}),
        "total_restricted_items": smpp_result.get("total_restricted_items", 0),
        "source": "api_cache + smpp_cache"
    }
