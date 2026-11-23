from __future__ import annotations
from typing import List, Dict, Optional
from core.schemas import PlanSchema
import re


def merge_by_role(classified_paragraphs: List[dict]) -> Dict[str, List[dict]]:
    """
    역할별로 문단 그룹화
    
    Returns:
        {"공고명": [para1, para2], "예산액_vat포함": [para3], ...}
    """
    grouped = {}
    
    for item in classified_paragraphs:
        role = item["role"]
        if role not in grouped:
            grouped[role] = []
        grouped[role].append(item)
    
    return grouped


def extract_number_from_text(text: str) -> Optional[int]:
    """
    텍스트에서 숫자 추출 (쉼표 제거)
    
    예: "39,996,000원" → 39996000
    """
    # 쉼표 제거
    text = text.replace(',', '').replace('，', '')
    
    # 숫자 패턴 찾기
    match = re.search(r'\d+', text)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def extract_item_codes(paragraphs: List[dict]) -> Optional[List[str]]:
    """
    세부품명번호 추출 (10자리 숫자만)
    """
    codes = []
    
    for para in paragraphs:
        text = para["paragraph"]
        # 10자리 연속 숫자 패턴
        matches = re.findall(r'\b\d{10}\b', text)
        codes.extend(matches)
        
        # key_values에서도 확인
        if para.get("key_values"):
            for val in para["key_values"]:
                if isinstance(val, str) and len(val) == 10 and val.isdigit():
                    codes.append(val)
    
    return list(set(codes)) if codes else None


def detect_manufacture_bid(text: str) -> Optional[bool]:
    """
    제조입찰 여부 판단
    """
    keywords = ["제조", "제작", "물품제조"]
    return any(kw in text for kw in keywords)


def map_to_plan_schema(grouped: Dict[str, List[dict]]) -> PlanSchema:
    """
    역할별 그룹을 PlanSchema로 변환
    
    각 역할에서 가장 확신도 높은 것을 우선 사용
    """
    
    # 확신도 순으로 정렬하는 헬퍼
    def get_best(role_key: str) -> Optional[dict]:
        if role_key not in grouped:
            return None
        items = grouped[role_key]
        # confidence 순: high > medium > low
        conf_order = {"high": 3, "medium": 2, "low": 1}
        sorted_items = sorted(items, key=lambda x: conf_order.get(x["confidence"], 0), reverse=True)
        return sorted_items[0] if sorted_items else None
    
    # 공고명
    notice_title_item = get_best("공고명")
    notice_title = notice_title_item["paragraph"][:200] if notice_title_item else "공고명 미추출"
    
    # 계약기간
    contract_period_item = get_best("계약기간")
    contract_period_text = contract_period_item["paragraph"][:100] if contract_period_item else "계약기간 미추출"
    
    # 예산액 (VAT 포함)
    budget_item = get_best("예산액_vat포함")
    budget_vat_included_krw = 0
    if budget_item:
        # key_values 또는 문단에서 숫자 추출
        if budget_item.get("key_values") and budget_item["key_values"]:
            budget_vat_included_krw = extract_number_from_text(budget_item["key_values"][0]) or 0
        else:
            budget_vat_included_krw = extract_number_from_text(budget_item["paragraph"]) or 0
    
    # 추정가격 (VAT 제외)
    estimated_item = get_best("추정가격_vat제외")
    estimated_price_ex_vat_krw = None
    if estimated_item:
        if estimated_item.get("key_values") and estimated_item["key_values"]:
            estimated_price_ex_vat_krw = extract_number_from_text(estimated_item["key_values"][0])
        else:
            estimated_price_ex_vat_krw = extract_number_from_text(estimated_item["paragraph"])
    
    # 세부품명번호
    item_codes = None
    if "세부품명번호" in grouped:
        item_codes = extract_item_codes(grouped["세부품명번호"])
    
    # 경쟁방식
    competition_item = get_best("경쟁방식")
    contract_method_suggestion = None
    detected_phrases = []
    award_method = None
    bidding_method = None
    
    if competition_item:
        text = competition_item["paragraph"]
        contract_method_suggestion = text[:200]  # 전체 문단 저장 (디버깅용)
        
        # 키워드 추출
        keywords = ["적격심사", "소액수의", "수의계약", "일반경쟁", "제한경쟁", "견적입찰"]
        detected_phrases = [kw for kw in keywords if kw in text]
        
        # [핵심 개선] 입찰방법/낙찰자선정방법과 계약방식을 별개로 파싱
        # 예: "계약방식: 제한경쟁, 입찰방법: 소액수의견적입찰"
        # → "입찰방법" 뒤의 값이 최우선 (사용자 요청: 가장 중요)
        
        # 1단계: 입찰방법/낙찰자선정방법 필드 우선 확인 (최우선)
        award_keywords_pattern = r'(입찰방법|낙찰자선정방법|낙찰자\s*결정\s*방법)[:\s]*(.*?)(?=\s*[,\n]|$)'
        award_match = re.search(award_keywords_pattern, text, re.IGNORECASE)
        
        if award_match:
            # 입찰방법 필드가 명시되어 있음 → 해당 값으로 판단
            award_text = award_match.group(2).strip()
            
            if any(kw in award_text for kw in ["소액수의", "수의", "견적"]):
                award_method = "small_quote"
            elif any(kw in award_text for kw in ["적격심사", "적격"]):
                award_method = "eligible_review"
        
        # 2단계: 계약방식/경쟁방식 필드 확인 (bidding_method 설정용)
        competition_keywords_pattern = r'(계약방식|계약방법|경쟁방식|구매방법)[:\s]*(.*?)(?=\s*[,\n]|$)'
        competition_match = re.search(competition_keywords_pattern, text, re.IGNORECASE)
        
        if competition_match:
            competition_text = competition_match.group(2).strip()
            
            if "일반경쟁" in competition_text:
                bidding_method = "general_competition"
            elif "제한경쟁" in competition_text:
                bidding_method = "limited_competition"
            elif "수의" in competition_text:
                bidding_method = "private_contract"
        
        # 3단계: 필드가 없으면 전체 문단에서 키워드 탐지 (Fallback)
        if not award_method:
            if any(kw in text for kw in ["소액수의", "수의계약", "견적"]):
                award_method = "small_quote"
                if not bidding_method:
                    bidding_method = "private_contract"
            elif any(kw in text for kw in ["적격", "일반경쟁", "제한경쟁"]):
                award_method = "eligible_review"
                if not bidding_method:
                    if "일반경쟁" in text:
                        bidding_method = "general_competition"
                    elif "제한경쟁" in text:
                        bidding_method = "limited_competition"

    
    # 공동계약 - 계약 관련 내용에 "공동"이 명시되어 있을 때만 활성화
    consortium_enabled = False
    consortium_partners = None
    if "공동계약" in grouped:
        consortium_item = get_best("공동계약")
        if consortium_item and "공동" in consortium_item["paragraph"]:
            consortium_enabled = True
    
    # 제조입찰
    is_manufacture_bid = None
    if "제조입찰여부" in grouped:
        manufacture_item = get_best("제조입찰여부")
        if manufacture_item:
            is_manufacture_bid = detect_manufacture_bid(manufacture_item["paragraph"])
    
    # 근거 생성
    rationale = f"문단 역할 분류 기반 추출 완료"
    evidence_snippets = []
    
    if budget_item:
        evidence_snippets.append(budget_item["paragraph"][:200])
    if competition_item:
        evidence_snippets.append(competition_item["paragraph"][:200])
    
    # PlanSchema 생성
    return PlanSchema(
        notice_title=notice_title,
        contract_period_text=contract_period_text,
        budget_vat_included_krw=budget_vat_included_krw,
        estimated_price_ex_vat_krw=estimated_price_ex_vat_krw,
        item_codes=item_codes,
        is_manufacture_bid=is_manufacture_bid,
        contract_method_suggestion=contract_method_suggestion,
        detected_phrases=detected_phrases,
        bidding_method=bidding_method,
        award_method=award_method,
        rationale=rationale,
        evidence_snippets=evidence_snippets if evidence_snippets else None,
        consortium_enabled=consortium_enabled,
        consortium_partners=consortium_partners,
        region_limit_enabled=None,
        region_scope_text=None,
        base_open_datetime=None,
    )
