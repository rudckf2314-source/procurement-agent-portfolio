from __future__ import annotations
import os
from openai import OpenAI
from core.schemas import PlanSchema

def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어야 합니다.")
    return OpenAI(api_key=api_key)

def extract_plan_with_gpt(raw_text: str) -> PlanSchema:
    """
    [기존 방식] 전체 텍스트를 단일 GPT 호출로 추출
    
    장점: 빠름
    단점: 복잡한 문서에서 키워드 기반 추출 한계
    """
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = get_openai_client()

    system_msg = (
        "너는 '구매계획안 전문 분석가'다. 텍스트를 정밀 분석하여 PlanSchema 필드를 채워라.\n"
        "**절대 원칙: 추측하지 말고 텍스트에 있는 근거로만 추출하라.**\n\n"
        
        "1. 공고명(notice_title) 추출:\n"
        "   - 파일명이 아닌 문서 내의 '건명', '공고명', '사업명', '구매명' 뒤에 오는 텍스트를 찾는다.\n"
        "   - '붙임', '계획안', '( )' 같은 불필요한 파일명 형식은 제거하라.\n\n"

        "2. 금액 추출 (가장 중요):\n"
        "   - '소요예산', '사업비', '추정금액', '배정예산', '기초금액' 주변의 숫자를 모두 찾아라.\n"
        "   - **주의: 0원은 절대 입력하지 마라. 금액을 못 찾으면 null로 두어라.**\n"
        "   - '일금', '금액' 뒤의 한글 금액('일금 오천만원')도 찾아서 숫자로 변환하라.\n"
        "   - '부가세 포함'이면 budget_vat_included_krw, '부가세 별도'면 estimated_price_ex_vat_krw에 넣는다.\n"
        "   - 별도 언급 없으면 보통 budget_vat_included_krw(부가세 포함)이다.\n\n"

        "3. 계약기간(contract_period) 추출:\n"
        "   - 문장 전체를 가져오지 마라. 핵심 기간만 추출하라.\n"
        "   - 예: '계약일로부터 90일간' (O), '납품기한은 계약일로부터...' (X)\n"
        "   - '납품기한', '과업기간', '계약기간' 키워드를 찾아라.\n\n"

        "4. 낙찰자선정/입찰방법 분류:\n"
        "   - 금액이 1억원 이상이면 무조건 'eligible_review' (적격심사).\n"
        "   - 1억원 미만이면 'small_quote' (소액수의).\n"
        "   - 단, 텍스트에 명시적으로 '적격심사', '소액수의'가 있으면 그것을 따른다.\n"
        "   - '제한경쟁' -> 'limited_competition', '수의계약' -> 'private_contract'\n\n"
        
        "5. 세부품명번호(item_codes):\n"
        "   - '세부품명번호', '물품식별번호' 뒤의 10자리 숫자를 리스트로 추출.\n"
        "   - 정확히 10자리여야 한다.\n\n"

        "6. 업종제한(industry_codes / industry_names_text):\n"
        "   - '업종코드', '입찰참가자격' 항목 근처의 4자리 숫자를 찾아 industry_codes에 담아라 (예: 0036, 1120).\n"
        "   - 만약 코드가 없고 업종명(예: 소프트웨어사업자, 정보통신공사업, 엔지니어링활동주체 등)만 있다면, 'industry_names_text' 필드에 정확한 명칭을 담아라.\n"
        "   - 예: '정보통신공사업법에 의한 정보통신공사업 등록자' -> '정보통신공사업' 추출.\n"
        "   - 둘 다 있으면 둘 다 채워라.\n\n"
        
        "7. 지역제한(region_limit_enabled / region_scope_text):\n"
        "   - '지역제한', '지역범위', '참가지역', '지역' 등 키워드를 찾아라.\n"
        "   - 예시:\n"
        "     * '지역제한: 서울' -> region_limit_enabled=True, region_scope_text='서울'\n"
        "     * '지역제한: 경기도' -> region_limit_enabled=True, region_scope_text='경기도'\n"
        "     * '지역제한 : 부산광역시' -> region_limit_enabled=True, region_scope_text='부산광역시'\n"
        "     * '지역제한 없음' 또는 '전국' -> region_limit_enabled=False, region_scope_text=None\n"
        "   - 콜론(:), 쌍점 뒤의 지역명을 정확히 추출하라. 앞뒤 공백 제거.\n\n"
        
        "8. 공동계약(consortium_enabled / consortium_partners):\n"
        "   - '공동계약', '공동수급', '컨소시엄', '공동도급' 키워드를 찾아라.\n"
        "   - '공동계약 허용', '2인 이상 공동도급 가능' -> consortium_enabled=True\n"
        "   - '공동계약 불가', '단독입찰만' -> consortium_enabled=False\n"
        "   - 참여 업체명이 명시되어 있으면 consortium_partners 리스트로 추출.\n\n"
        
        "9. 개찰일시(base_open_datetime):\n"
        "   - '개찰일시', '입찰마감일시', '제출마감' 등 키워드 뒤의 날짜+시간을 찾아라.\n"
        "   - ISO 형식으로 변환: '2025-05-20 14:00' -> '2025-05-20T14:00:00'\n"
        "   - 년도가 없으면 현재 연도로 추정하되, 확실하지 않으면 null로 두어라.\n\n"
        
        "10. 기타:\n"
        "   - rationale��는 판단 근거를 한 문장으로 요약.\n"
        "   - evidence_snippets에는 금액이나 기간이 명시된 원문 텍스트를 발췌.\n"
    )

    # 일관성을 위해 temperature=0 설정 (deterministic output)
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": raw_text},
        ],
        response_format=PlanSchema,
        temperature=0,  # 결정적 출력 (일관성 향상)
        top_p=0.1,      # 다양성 제한
    )

    parsed = completion.choices[0].message.parsed
    
    # 디버그: 추출 실패 시 로그 출력  
    if not parsed.item_codes:
        print("⚠️  세부품명번호가 추출되지 않았습니다.")
        print(f"   입력 텍스트 길이: {len(raw_text)} 글자")
        if '세부품명번호' in raw_text or '물품식별번호' in raw_text:
            print("   ✓ 키워드는 발견됨 (하지만 10자리 숫자 추출 실패)")
        else:
            print("   ✗ 키워드 자체를 찾을 수 없음")
    
    return parsed


def extract_plan_with_context(raw_text: str) -> PlanSchema:
    """
    [신규 방식] 2단계 문맥 기반 추출
    
    1단계: 텍스트를 문단으로 분해
    2단계: 각 문단의 역할(의미)을 LLM으로 분류
    3단계: 역할별로 그룹화하여 PlanSchema로 병합
    
    장점: 키워드가 없어도 문맥으로 정확한 추출
    단점: 여러 번 LLM 호출 (느림)
    """
    from core.paragraph_classifier import split_into_paragraphs, classify_all_paragraphs
    from core.role_mapper import merge_by_role, map_to_plan_schema
    
    client = get_openai_client()
    
    print("📄 1단계: 문단 단위 분해 중...")
    paragraphs = split_into_paragraphs(raw_text)
    print(f"   ✓ {len(paragraphs)}개 문단 추출됨\n")
    
    print("🔍 2단계: 각 문단의 역할 분류 중...")
    classified = classify_all_paragraphs(paragraphs, client)
    print(f"   ✓ 분류 완료\n")
    
    print("🔗 3단계: 역할별 병합 및 정규화 중...")
    grouped = merge_by_role(classified)
    
    # 디버그: 역할별 개수 출력
    print("   역할별 문단 분포:")
    for role, items in grouped.items():
        if role != "기타":
            print(f"     - {role}: {len(items)}개")
    
    plan = map_to_plan_schema(grouped)
    print("   ✓ PlanSchema 변환 완료\n")
    
    # 추가 검증: 1억원 이상이면 award_method 강제 변경
    if plan.estimated_price_ex_vat_krw:
        P = plan.estimated_price_ex_vat_krw
    elif plan.budget_vat_included_krw:
        P = int(plan.budget_vat_included_krw / 1.1)
    else:
        P = 0
    
    if P >= 100_000_000 and plan.award_method != "eligible_review":
        print(f"💡 금액 우선 규칙 적용: {P:,}원 >= 1억원 → 'eligible_review'로 강제 변경")
        plan.award_method = "eligible_review"
    
    return plan
