from crewai import Agent, Task, Crew, Process
import json
import os
from datetime import datetime
from crew.tools_legal import legal_tool, _legal_search_logic
from crew.tools_extract import extract_tool
from crew.tools_api import validate_item_code, validate_industry_code
from core.openai_client import extract_plan_with_context, extract_plan_with_gpt

# 기본 모델 설정
os.environ["OPENAI_MODEL_NAME"] = "gpt-4o-mini"

def run_procurement_crew(raw_text: str, fallback_open_dt: datetime) -> dict:
    """
    CrewAI를 사용하여 구매계획안 분석, 법령 검토, 그리고 **보고서 작성**까지 수행
    """
    print("[DEBUG] CrewAI Starting...")
    
    # 1. 에이전트 정의
    legal_advisor = Agent(
        role='Legal Advisor',
        goal='조달 관련 최신 법령 및 고시 기준(고시금액, 기업규모 제한 등)을 정확히 파악한다.',
        backstory='20년 경력의 조달청 법령 전문가입니다.',
        tools=[legal_tool],
        verbose=True,
        allow_delegation=False
    )

    analyst = Agent(
        role='Procurement Analyst',
        goal='구매계획안 텍스트에서 핵심 정보(예산, 품명, 입찰방식 등)를 추출하고, 추출한 코드가 실제로 유효한지 API로 검증한다.',
        backstory='꼼꼼한 성격의 조달 공고 분석가입니다. 품명코드나 업종코드를 찾으면 반드시 조달청 API로 유효성을 확인합니다.',
        tools=[extract_tool, validate_item_code, validate_industry_code],  # API 도구 추가
        verbose=True,
        allow_delegation=False
    )

    compliance_officer = Agent(
        role='Compliance Officer',
        goal='법령 정보와 분석 결과를 결합하여 최종 공고 조건(적격/소액 여부)을 결정한다.',
        backstory='''당신은 빈틈없는 계약관입니다.
        [중요 원칙]
        1. 금액 비교 시 반드시 모든 쉼표(,)를 제거하고 숫자로 변환한 뒤 판단하세요.
        2. "157,580,500원"은 1억 5천만원대이므로 10억원을 초과하지 않습니다. 절대 오판하지 마세요.
        3. 소액수의(10억 미만)와 적격심사(고시금액 이상)의 기준을 엄격히 적용하세요.
        ''',
        verbose=True,
        allow_delegation=False
    )

    report_writer = Agent(
        role='Report Writer',
        goal='분석된 정보를 바탕으로 주석 지침에 따라 완벽한 보고서를 작성한다.',
        backstory='당신은 행정 문서 작성의 달인입니다. 주어진 텍스트 템플릿의 주석(#...)을 해석하여 올바른 값으로 치환하고, 스타일(굵게, 색상)을 Markdown으로 적용합니다.',
        verbose=True,
        allow_delegation=False
    )

    # 2. 태스크 정의
    task_legal = Task(
        description="Legal Search Tool을 사용하여 2025년 기준 관련 법령(고시금액, 소기업 범위 등)을 조회하라.",
        expected_output="법령 JSON",
        agent=legal_advisor
    )
    
    truncated_text = raw_text[:4000]
    task_analyze = Task(
        description=f"구매계획안 텍스트 분석:\n{truncated_text}...",
        expected_output="PlanSchema JSON",
        agent=analyst
    )

    task_compliance = Task(
        description="""
        분석된 예산과 법령 기준을 비교하여 최종 공고 조건을 결정하고, 아래 형식으로 명확하게 요약하라.
        중간 계산 과정이나 생각(Chain of Thought)은 출력하지 말고 최종 결론만 작성할 것.

        [필수 출력 형식]
        1. 공고 유형: (소액수의 / 적격심사)
           - 근거: 추정가격 OOO원 (고시금액 미만/이상)
        2. 기업규모 제한: (소기업 / 중소기업 / 제한없음)
        3. 지역제한 여부: (전국 / OOO지역 제한)
        4. 중소기업자간 경쟁제품: (해당 / 미해당)
        5. 종합 의견: (한 줄 요약)
        """,
        expected_output="명확한 요약 보고서",
        agent=compliance_officer,
        context=[task_legal, task_analyze]
    )

    task_report = Task(
        description=(
            "아래 양식 중에서 조건에 맞는 Case를 선택하여 Markdown 보고서를 작성하라.\n"
            "**[Streamlit Markdown 스타일 사용]**: 굵은 파란색은 :blue[**텍스트**], 굵은 빨간색은 :red[**텍스트**] 형식을 사용하라.\n\n"
            
            "**[Case 1: 적격심사]** (추정가격 1억 이상)\n"
            "지속가능한 미래, 함께 누리는 환경, 탄소중립시대를 선도하는 글로벌 환경전문기관\n\n"
            "# **:blue[{notice_type} 입찰공고]**\n"
            "**한국환경공단 입찰공고번호 : N1-2025XXXX-XX**\n\n"
            "< 본 계약은 청렴계약제가 적용됩니다 >\n"
            "이 계약은 「국가를 당사자로 하는 계약에 관한 법률」또는 「지방자치단체를 당사자로 하는 계약에 관한 법률」에 따른 청렴계약제가 적용됩니다. (중략 - 청렴계약 내용 포함)\n"
            "1. 금품.향응 등...\n"
            "2. 입찰가격의 사전 협의...\n"
            "3. 공정한 직무수행 방해...\n"
            "4. 손해배상액 납부...\n\n"
            "우리 공단은 입찰담합 방지 및 공정거래질서 확립을 위해... (중략)\n"
            "지속가능한 미래, 함께 누리는 환경, 탄소중립시대를 선도하는 글로벌 환경전문기관\n\n"
            
            "1. 입찰에 부치는 사항\n"
            "가. 공 고 명 : {notice_title}\n"
            "나. 용역기간 : {contract_period_text}\n"
            "다. 예 산 액 : {budget_vat_included_krw}원(부가가치세, 배송비 포함)\n"
            "라. 구매범위 : 물품규격서 및 붙임 참조\n"
            "   - 물품내용 문의 : 00000처 00000부 000 ☎000-000-0000\n"
            "마. 전자입찰서 제출기간 : {submission_period_text}\n"
            "바. 개찰일시 및 장소 : {open_datetime_dt}, 국가종합전자조달시스템(나라장터)\n\n"
            
            "2. 견적(입찰) 및 계약방식\n"
            "가. {competition_method_text}(총액), 전자입찰대상 용역입니다.\n"
            "나. 적격심사대상 물품입니다. **{appendix_text}**\n"
            "※ 추정가격은 부가세 제외 금액임.\n"
            "※ 공단 물품구매 적격심사세부기준은 공단홈페이지(http://www.keco.or.kr/)\"입찰정보/집행기준“ 참고\n"
            "다. 청렴계약이행 서약제 대상입니다.\n"
            "라. 가격입찰은 전자입찰로만 집행되며, 입찰서는 반드시 국가종합전자조달시스템(G2B) 이용 제출...\n"
            "마. 입찰금액은 부가가치세를 포함한 금액으로...\n\n"
            
            "3. 입찰참가자격: 아래의 입찰참가자격을 모두 갖춘 자이어야 합니다.\n"
            "가. 국가종합전자조달시스템 입찰참가자격등록규정에 따라... 입찰참가자격으로 등록한 자\n"
            "❍ :blue[**{item_code_text}**] 제조 또는 공급물품으로 등록된 자\n"
            "(만약 직접생산확인 대상(has_direct_production=True)인 경우, 아래 문구 추가)\n"
            "❍ 중소기업제품 구매촉진 및 판로지원에 관한법률... 직접생산확인증명서[세부품명번호: :blue[**{item_code_text}**]](개찰일 전일까지 발급 유효)를 소지한 자\n\n"
            "나. 부정당업자의 입찰참가 자격제한에 해당되지 아니한 업체\n"
            "다. 조세포탈 등을 한 자로서... (생략)\n"
            "라. 「중소기업기본법」 제2조에 따른 :red[**{sme_limit_text}**] 또는 「소상공인 보호 및 지원에 관한 법률」... :red[**{sme_limit_text}**]·소상공인확인서 (유효기간 내) 소지 업체\n"
            "※ <중소기업.소상공인확인서>는 중소기업공공구매 종합정보망에서 확인하며...\n\n"

            "**[Case 2: 소액수의]** (추정가격 1억 미만)\n"
            "지속가능한 미래, 함께 누리는 환경, 탄소중립시대를 선도하는 글로벌 환경전문기관\n\n"
            "# **:blue[{notice_type} 견적제출 공고]**\n"
            "**한국환경공단 입찰공고번호 : N1-2025XXXX-XX**\n\n"
            "< 본 계약은 청렴계약제가 적용됩니다 >\n"
            "(청렴계약 내용 중략)\n\n"
            "1. 견적(입찰)에 부치는 사항\n"
            "가. 공 고 명 : :blue[**{notice_title}**]\n"
            "나. 계약기간 : {contract_period_text}\n"
            "다. 예 산 액 : {budget_vat_included_krw}원(부가가치세 포함)\n"
            "라. 구매범위 : 물품규격서 등 참조\n"
            "마. 전자입찰서 제출기간 : {submission_period_text}\n"
            "바. 개찰일시 및 장소 : {open_datetime_dt}, 국가종합전자조달시스템(나라장터)\n\n"
            "2. 견적(입찰) 및 계약방식\n"
            "가. {competition_method_text}(총액, 전자)대상입니다.\n"
            "나. 소액수의(총액, 전자)대상으로, 적격심사 제외대상입니다.\n"
            "... (소액수의 관련 내용)\n"
            "3. 입찰참가자격\n"
            "... (기업규모 제한 :red[**{sme_limit_text}**] 등 동일 적용)\n"
        ),
        expected_output="Markdown 형식의 결재 보고서",
        agent=report_writer,
        context=[task_compliance, task_analyze, task_legal]
    )

    # 3. Crew 실행
    crew = Crew(
        agents=[legal_advisor, analyst, compliance_officer, report_writer],
        tasks=[task_legal, task_analyze, task_compliance, task_report],
        verbose=True,
        process=Process.sequential
    )

    try:
        print("[DEBUG] Kickoff...")
        crew.kickoff()
    except Exception as e:
        print(f"[ERROR] Crew Kickoff Failed: {e}")
    
    # 4. 결과 조합
    legal_data = json.loads(_legal_search_logic("전체 조회"))
    # [최적화] extract_plan_with_context(문단 분석) 대신 단일 GPT 추출 사용
    # 이유 1: 속도가 훨씬 빠름
    # 이유 2: 개발자 주석에 따르면 단일 GPT 방식의 성능이 더 좋음 (crew_runner.py 참조)
    plan = extract_plan_with_gpt(raw_text)
    
    return {
        "plan": plan, 
        "legal_data": legal_data,
        "compliance_note": str(task_compliance.output),
        "report": str(task_report.output)
    }
