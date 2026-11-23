# utils/chatbot.py

from __future__ import annotations

import textwrap
from typing import Any, List, Dict

from .config import client, OPENAI_CHAT_MODEL

def generate_chat_response(
    messages: List[Dict[str, str]],
    context: str = ""
) -> str:
    """
    OpenAI ChatCompletion을 사용하여 답변을 생성합니다.
    
    Args:
        messages: 대화 기록 [{'role': 'user', 'content': '...'}, ...]
        context: 현재 분석된 공고문 패치 데이터 (JSON 형태)
    """
    
    # ============================================
    # 데이터 조회 로직 추가 (사용자 질문에서 코드 추출)
    # ============================================
    user_message = messages[-1].get("content", "") if messages else ""
    additional_info = []
    
    # 1. 품명코드 검색 (10자리 숫자)
    import re
    item_codes = re.findall(r'\b\d{10}\b', user_message)
    if item_codes:
        from utils.data_lookup import lookup_item_code
        for code in item_codes[:3]:  # 최대 3개까지
            result = lookup_item_code(code)
            if result.get("item_name") or result.get("is_restricted"):
                info_text = f"\n\n[품명코드 {code} 조회 결과]\n"
                if result.get("item_name"):
                    info_text += f"- 품명: {result['item_name']}\n"
                if result.get("is_restricted"):
                    notice = result.get("notice_info", {})
                    info_text += f"- 중소기업자간 경쟁제품 제한 대상: 예\n"
                    info_text += f"- 직접생산확인증명서: 필요\n"
                    if notice:
                        info_text += f"- 근거: {notice.get('department', '')} 제{notice.get('notice_number', '')}호 ({notice.get('notice_date', '')})\n"
                else:
                    info_text += f"- 중소기업자간 경쟁제품 제한 대상: 아니오\n"
                    info_text += f"- 직접생산확인증명서: 불필요\n"
                additional_info.append(info_text)
    
    # 2. 업종코드 검색 (4자리 숫자)
    industry_codes = re.findall(r'\b\d{4}\b', user_message)
    if industry_codes:
        from utils.data_lookup import get_industry_name_from_cache
        for code in industry_codes[:3]:  # 최대 3개까지
            industry_name = get_industry_name_from_cache(code)
            if industry_name:
                additional_info.append(f"\n[업종코드 {code} 조회 결과]\n- 업종명: {industry_name}\n")
    
    # 추가 정보를 context에 병합
    if additional_info:
        context = (context or "") + "\n\n[실시간 데이터 조회]" + "".join(additional_info)
    
    system_prompt = textwrap.dedent(
        """
        너는 공공 조달(Procurement) 전문가 AI 어시스턴트 'AI 조달 비서'야.
        사용자가 구매계획안 분석 결과, 조달 계약 법령, 공고문 작성 요령 등에 대해 물어보면
        친절하고 전문적인 답변을 제공해줘.
        
        [핵심 역할]
        1. **분석 결과 설명**: 제공된 [현재 분석 컨텍스트]를 바탕으로 예산, 계약 방법, 제한 사항 등을 설명한다.
        2. **법령 가이드**: 조달사업법, 국가계약법, 지방계약법 등 관련 법령에 근거하여 답변한다.
        3. **공고문 작성 지원**: 공고명, 참가자격, 제출기한 등 공고문 작성에 필요한 조언을 제공한다.
        
        [답변 원칙]
        - **데이터 기반**: 반드시 제공된 [현재 분석 컨텍스트]의 데이터(JSON)를 확인하고 답변해라. 추측 금지.
        - **실시간 조회**: 사용자가 품명코드(10자리) 또는 업종코드(4자리)를 질문하면 자동으로 캐시/API에서 조회된 정보가 함께 제공됨.
        - **법적 근거 명시**: '중소기업자간 경쟁제품', '지역제한', '적격심사' 등 판단 근거를 설명해라.
        - **명확성**: 금액은 천 단위 콤마(,)를 붙여서 가독성 있게 표기해라. (예: 50,000,000원)
        - **안내 위주**: "이 공고는 ~입니다"라고 단정하기보다 "분석 결과에 따르면 ~로 보입니다"라고 안내해라.
        
        [컨텍스트 데이터 구조 예시]
        - analysis_result: 공고문 분석 결과 (공고명, 추정가격, 공고 유형 등)
        - legal_report: 법령 검토 결과 (적용 법령, 고시금액 기준, 준법 검토 의견 등)
        - smpp_status: SMPP 데이터베이스 상태 (cache_exists, metadata 등)
        - [실시간 데이터 조회]: 사용자 질문에 포함된 코드로 자동 조회된 품명/업종 정보
        
        [자주 묻는 질문 대응]
        - "법령 API랑 연동되어 있어?" -> "네, 대한민국 현행 조달 관련 법령(조달사업법, 판로지원법 등) 및 최신 고시 정보를 실시간으로 반영하여 분석하고 있습니다." 라고 답변.
        - "어떤 법이 적용됐어?" -> context의 `legal_report.data.gosi_amount.reference` 또는 `statute` 필드를 확인하여 답변.
        - "이거 예산이 얼마야?" -> context의 `analysis_result.budget_vat_included_krw` 값을 확인하여 답변.
        - "지역 제한 있어?" -> context의 `analysis_result.region_limit` 값을 확인.
        - "SMPP 데이터 최신이야?" -> context의 `smpp_status.metadata` 내의 날짜 정보를 확인.
        - "5510159901은 뭐야?" -> [실시간 데이터 조회] 섹션에 자동으로 조회된 품명코드 정보가 있으면 그것을 사용해서 답변.
        - "왜 적격심사야?" -> 추정가격이 고시금액(2.3억 등) 이상이거나 소액수의 범위를 초과하는지 설명.
        - "직생 필요해?" -> context의 `has_direct_production`이 true인지 확인.
        
        [톤앤매너]
        - 전문적이고 신뢰감 있는 톤.
        - 사용자(발주 담당자)의 업무를 돕는 파트너로서의 태도.
        - 답변은 한국어로 작성.
        """
    ).strip()

    if context:
        system_prompt += f"\n\n[현재 분석 컨텍스트 (JSON 데이터)]\n{context}"
    else:
        system_prompt += "\n\n[현재 분석 컨텍스트가 없습니다. 일반적인 조달 법령에 대해 답변해 주세요.]"

    # 메시지 구성
    api_messages = [{"role": "system", "content": system_prompt}]
    
    # 이전 대화 기록 추가
    for msg in messages[-10:]:
        api_messages.append(msg)

    try:
        if client is None:
            return "오류: OpenAI 클라이언트가 초기화되지 않았습니다. API 키를 확인해주세요."
            
        completion = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=api_messages,
            temperature=0.7,
            max_tokens=1000,
        )
        return completion.choices[0].message.content or "죄송합니다. 답변을 생성하지 못했습니다."
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"
