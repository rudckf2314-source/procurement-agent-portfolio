from __future__ import annotations
from typing import Tuple, Optional
from core.schemas import PlanSchema
from core.legal_rule_provider import get_or_update_legal_rules

def load_rules(path: str = None) -> dict:
    """
    법령 정보 로드
    기존의 YAML 파일 대신, API/캐시 기반의 Provider를 통해 규칙을 가져옵니다.
    path 인자는 하위 호환성을 위해 남겨두지만 무시됩니다.
    """
    return get_or_update_legal_rules()

def decide_notice_type(plan: PlanSchema, rules: dict) -> str:
    """
    공고 유형 결정 (최종 규칙)
    
    "소액수의" 키워드가 있을 때:
    - 1억 미만 → 소액수의 (제한경쟁 무시)
    - 1억 이상 → 적격심사
    
    "소액수의" 키워드가 없을 때:
    - 1억 미만 → 소액수의
    - 1억 이상 → 적격심사
    - 제한경쟁 → 적격심사
    """
    P = get_estimated_ex_vat(plan, rules)
    one_hundred_million = rules["thresholds"]["one_hundred_million"]
    
    # 모든 텍스트 필드 결합
    suggestion = plan.contract_method_suggestion or ""
    title = plan.notice_title or ""
    bidding = plan.bidding_method or ""
    award = plan.award_method or ""
    combined_text = f"{suggestion} {title} {bidding} {award}".lower()
    
    print(f"\n🔍 [규칙 엔진] 공고 유형 판정 시작")
    print(f"   검색 텍스트: {combined_text[:100]}...")
    print(f"   추정가격: {P:,}원")
    
    # 소액수의 키워드 목록 (한글 + 영어)
    small_quote_keywords = ["소액수의", "소액", "수의견적", "견적제출", "견적입찰", "small_quote", "small", "quote"]
    has_small_quote_keyword = any(kw in combined_text for kw in small_quote_keywords)
    
    # LLM이 이미 small_quote로 판정했으면 우선 적용
    if plan.award_method == "small_quote":
        has_small_quote_keyword = True
        print(f"   ✓ LLM이 소액수의로 판정 (award_method=small_quote)")
    
    if has_small_quote_keyword:
        found_keyword = next((kw for kw in small_quote_keywords if kw in combined_text), "small_quote")
        print(f"   ✓ 소액수의 키워드 발견: '{found_keyword}'")
    
    # ============================================================
    # [규칙 1] 가격 >= 1억 → 무조건 적격심사 (키워드 무관)
    # ============================================================
    if P >= one_hundred_million:
        if has_small_quote_keyword:
            print(f"❌ [규칙 1] 소액수의 키워드 있지만, 가격 {P:,}원 >= 1억 → 적격심사")
        else:
            print(f"✅ [규칙 1] 가격 {P:,}원 >= 1억 → 적격심사")
        return "eligible_review"
    
    # ============================================================
    # [규칙 2] 가격 < 1억 + 소액수의 키워드 → 소액수의 (제한경쟁 무시)
    # ============================================================
    if has_small_quote_keyword:
        print(f"✅ [규칙 2] 소액수의 키워드 + 가격 {P:,}원 < 1억 → 소액수의")
        print(f"   (제한경쟁 여부 무관)")
        return "small_quote"
    
    # ============================================================
    # [규칙 3] 가격 < 1억 + 수의계약 → 소액수의
    # ============================================================
    if plan.bidding_method == "private_contract" or "수의계약" in combined_text:
        print(f"✅ [규칙 3] 수의계약 → 소액수의")
        return "small_quote"
    
    # ============================================================
    # [규칙 4] 가격 < 1억 + 제한경쟁 → 적격심사
    # ============================================================
    if plan.bidding_method == "limited_competition" or "제한경쟁" in combined_text:
        print(f"✅ [규칙 4] 제한경쟁 → 적격심사")
        return "eligible_review"
    
    # ============================================================
    # [규칙 5] LLM 분류 결과 신뢰
    # ============================================================
    if plan.award_method in ["eligible_review", "small_quote"]:
        print(f"✅ [규칙 5] LLM 분류 결과: {plan.award_method}")
        return plan.award_method
    
    # ============================================================
    # [기본값] 가격 < 1억 → 소액수의
    # ============================================================
    print(f"✅ [기본값] 가격 {P:,}원 < 1억 → 소액수의")
    return "small_quote"


def decide_competition_text(plan: PlanSchema, notice_type: str, rules: dict) -> str:
    if notice_type == "small_quote":
        return rules["defaults"]["smallquote_competition"]
    
    # If explicit competition method is mentioned in bidding_method (LLM)
    if plan.bidding_method == "general_competition": return "일반경쟁"
    if plan.bidding_method == "limited_competition": return "제한경쟁"
    if plan.bidding_method == "private_contract": return "수의계약"

    # Fallback to contract_method_suggestion
    method = plan.contract_method_suggestion
    if method:
        if "일반" in method: return "일반경쟁"
        if "제한" in method: return "제한경쟁"
        
    return rules["defaults"]["eligible_competition"]


def decide_sme_limit(P: int, rules: dict) -> str:
    """
    기업규모 제한 (2025년 기준)
    - P < 1억: 소기업 (필수)
    - 1억 <= P < 고시금액(2.3억): 중소기업 (필수)
    - P >= 2.3억: 제한없음 (국제입찰 등)
    """
    one_hundred = rules["thresholds"]["one_hundred_million"]
    gosi = rules["thresholds"]["gosi_amount"]
    
    if P < one_hundred:
        return "소기업"
    if P < gosi:
        return "중소기업"
    return "제한없음"

def decide_region_limit(plan: PlanSchema, P: int, rules: dict) -> Optional[str]:
    """
    지역제한 결정
    - 고시금액(2.3억) 이상이면 지역제한 불가 (Plan에 있어도 무시)
    - 미만이고 Plan에 있으면 사용
    """
    gosi = rules["thresholds"]["gosi_amount"]
    
    if P >= gosi:
        return None # 고시금액 이상은 지역제한 불가
    
    # Plan에서 지역제한 텍스트가 있으면 반환 (없으면 None)
    return plan.region_scope_text


from core.direct_production import check_direct_production_obligation

def decide_has_direct_production(plan: PlanSchema) -> bool:
    """
    직접생산확인증명서 필요 여부
    - 중소기업자간 경쟁제품인 경우 필수
    - core.direct_production 모듈의 확장된 DB를 사용하여 판단
    """
    # 검색 대상 텍스트 결합
    combined_text = (plan.notice_title or "") + " " + (plan.contract_method_suggestion or "")
    
    return check_direct_production_obligation(combined_text, plan.item_codes)

def decide_appendix(plan: PlanSchema, P: int, notice_type: str, rules: dict) -> Optional[str]:
    if notice_type != "eligible_review":
        return None
    gosi = rules["thresholds"]["gosi_amount"]
    
    
    # 별표 판정 강화 로직 (2025년 기준)
    # 1. 제조 vs 구매 판단
    is_manufacturing = plan.is_manufacture_bid
    
    # 키워드로 재확인 (LLM 보완)
    title_keywords = (plan.notice_title or "").replace(" ", "")
    if "제조" in title_keywords or "제작" in title_keywords:
        is_manufacturing = True
    elif "구매" in title_keywords or "구입" in title_keywords:
        # 구매 키워드가 있어도 제조가 포함되면 제조로 볼 수 있음 (예: 제조구매)
        # 하지만 명확히 '제조'가 없으면 구매로 간주
        if not is_manufacturing:
            is_manufacturing = False

    # 2. 금액별 별표 적용
    # [별표 1] 추정가격 10억원 이상인 제조입찰
    if is_manufacturing and P >= 1_000_000_000:
        return rules["appendix"]["eligible"]["ge_10b_manufacture"]  # [별표1]
        
    # [별표 2] 
    # - 추정가격 10억원 미만 2.3억원(고시금액) 이상인 제조입찰
    # - 추정가격 2.3억원(고시금액) 이상인 구매입찰
    if P >= gosi:
        # 10억 이상 제조는 위에서 걸러짐.
        # 따라서 여기는 (10억 미만 제조) OR (모든 2.3억 이상 구매)
        return rules["appendix"]["eligible"]["ge_gosi_lt_10b"]  # [별표2]
        
    # [별표 3] 추정가격 2.3억원(고시금액) 미만인 제조/구매입찰
    return rules["appendix"]["eligible"]["lt_gosi"]  # [별표3]

def get_estimated_ex_vat(plan: PlanSchema, rules: dict) -> int:
    if plan.estimated_price_ex_vat_krw is not None:
        return int(plan.estimated_price_ex_vat_krw)
    from core.utils import estimate_ex_vat
    return estimate_ex_vat(int(plan.budget_vat_included_krw))

