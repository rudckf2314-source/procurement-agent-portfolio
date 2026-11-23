from __future__ import annotations
from datetime import datetime, date
from core.openai_client import extract_plan_with_gpt, extract_plan_with_context
from core.rule_engine import load_rules, get_estimated_ex_vat, decide_notice_type, decide_competition_text, decide_sme_limit, decide_appendix, decide_region_limit, decide_has_direct_production
from core.date_engine import parse_submission_start_dt, calc_submission_period, calc_open_datetime, calc_consortium_deadline
from core.rule_engine import load_rules, get_estimated_ex_vat, decide_notice_type, decide_competition_text, decide_sme_limit, decide_appendix, decide_region_limit, decide_has_direct_production
from core.date_engine import parse_submission_start_dt, calc_submission_period, calc_open_datetime, calc_consortium_deadline
from core.schemas import NoticePatch
from crew.crew_main import run_procurement_crew
from core.api_client import fetch_item_name_from_api
from core.industry_mapper import get_industry_name_by_code, get_code_by_name
def run_pipeline(
    raw_text: str,
    fallback_open_dt: datetime,
    manual_notice_type: str = "auto",
    use_context: bool = True, # 하위 호환성 유지 (이제 무시됨)
    use_crew: bool = True,     # 하위 호환성 유지 (이제 무시됨)
    api_validation: dict = None
) -> dict:
    rules = load_rules()
    
    # [무조건 CrewAI 실행]
    # CrewAI가 법령 조회 + Plan 추출 + 1차 검증을 수행
    crew_res = run_procurement_crew(raw_text, fallback_open_dt)
    
    # [최적화] crew_main.py에서 이미 extract_plan_with_gpt를 수행하여 결과를 반환함
    # 따라서 여기서 중복 호출하지 않고 바로 사용
    plan = crew_res["plan"]
    
    # 금액 검증 (이미 수행되었으나 로직 흐름상 유지)
    P_check = get_estimated_ex_vat(plan, rules)
    if P_check > 0 or plan.budget_vat_included_krw > 0:
        print("   ✅ Plan 추출 성공 (금액 확보됨)")
    else:
        print("   ⚠️ Plan 추출 경고: 금액이 0원입니다.")

    legal_data = crew_res.get("legal_data", {})
    compliance_note = crew_res.get("compliance_note", "")

    # [데이터 품질 검증 및 자동 복구] - 위에서 이미 수행했으므로 P_check 갱신
    P = get_estimated_ex_vat(plan, rules)

    if manual_notice_type in ["eligible_review", "small_quote"]:
        notice_type = manual_notice_type
    else:
        notice_type = decide_notice_type(plan, rules)
    competition_text = decide_competition_text(plan, notice_type, rules)
    sme_limit = decide_sme_limit(P, rules)
    appendix = decide_appendix(plan, P, notice_type, rules)
    
    # 신규 규칙 할당
    region_limit = decide_region_limit(plan, P, rules)
    has_direct_production = decide_has_direct_production(plan)

    # 수정된 날짜 계산 로직
    submission_start_dt = parse_submission_start_dt(plan.base_open_datetime, fallback_open_dt)
    open_datetime_dt = calc_open_datetime(submission_start_dt, notice_type)
    submission_period_text = calc_submission_period(submission_start_dt, open_datetime_dt)
    
    # 공동수급협정서 마감일
    consortium_deadline_dt = calc_consortium_deadline(open_datetime_dt)

    # 공동계약 텍스트 생성
    # 공동계약 텍스트 생성
    # A: 상태 요약 (consortium_status_text)
    # B: 전체 텍스트 (consortium_text)
    
    consortium_status_text = "해당없음"
    consortium_text = "해당사항 없음."

    if plan.consortium_enabled:
        # 공동수급협정서 마감일 포맷팅
        deadline_str = consortium_deadline_dt.strftime("%Y년 %m월 %d일 %H시 %M분")
        
        partners = plan.consortium_partners or []
        partners_text = ", ".join([p for p in partners if p.strip()]) if partners else ""
        
        # A: 상태 요약 (공동계약 허용 + 참여업체)
        consortium_status_text = f"공동계약 허용{'(참여업체: ' + partners_text + ')' if partners_text else ''}"
        
        # 상세 규정 (가~마)
        detail_body = f"""가. 단독 또는 공동이행방식으로만 입찰참여가 가능하며, 공동수급체 구성원은 각각 본 입찰에서 요구하는 입찰참가자격을 모두 갖추어야 합니다.
나. 공동수급체 구성원은 대표사가 참여 지분율이 가장 많아야 하고, 대표사를 포함하여 5개사 이하로 구성하여야 하며, 구성원별 계약참여 최소 지분율은 10% 이상으로 하여야 하며, 공동수급체 구성원은 동일 입찰 건에 대하여 공동수급체를 중복으로 결성하여 입찰에 참가할 수 없습니다.
다. 공동도급 참여시에는 반드시 전자조달시스템의 "입찰정보"를 이용하여 전자조달 시스템 전자입찰특별유의서 제9조에 따라 공동수급협정서를 제출, 대표사는 나라장터에서 공동수급협정서의 승인 여부를 확인하여야 하고, 공동수급협정서 제출마감 후에는 협정서를 제출하거나 변경할 수 없으며, 또한 공동수급협정서 제출마감 이전이더라도 입찰서를 제출한 경우에는 협정서를 제출하거나 변경할 수 없습니다. 공동계약으로 참여시는 반드시 공동계약운용요령을 숙지하여야 하며 숙지하지 못함에 따라 발생된 결과에 대한 책임은 입찰자에게 있습니다.
라. 기타 입찰공고에 명시되지 않은 사항은 (계약예규) 공동계약 운용요령에 따릅니다.
마. 공동수급협정서 제출기한: {deadline_str}, ※해당자에 한함, 나라장터 전자 제출, 공동수급협정서 제출기한은 개찰일 전일로 함."""

        # B: 전체 텍스트 (요약 + 상세 규정)에서 "공동계약 허용" 텍스트 제거
        prefix = consortium_status_text.replace("공동계약 허용", "").strip()
        if prefix:
             consortium_text = f"{prefix}\n\n{detail_body}"
        else:
             consortium_text = detail_body


    # API 기반 세부품명 조회 및 매핑
    item_name_to_code_map = {}
    item_name_api_str = None
    
    if plan.item_codes:
        import re
        api_results = []
        for code in plan.item_codes:
            # 숫자만 추출 (10자리)
            c_clean = re.sub(r'[^0-9]', '', code)
            
            # 기본값
            item_name_to_code_map[code] = ""
            
            if len(c_clean) == 10:
                found = fetch_item_name_from_api(c_clean)
                if found:
                    print(f"   [API] 세부품명 조회 성공: {code} -> {found}")
                    api_results.append(found)
                    item_name_to_code_map[code] = found
        
        if api_results:
            item_name_api_str = ", ".join(api_results)
    
    # 직접생산확인 안내 문구 생성 (세부품명번호 + 품명 동적 삽입)
    # [중요] 품명번호가 없으면 has_direct_production을 false로 강제 변경
    if has_direct_production:
        if not plan.item_codes:
            # 품명번호가 없는데 has_direct_production이 true인 경우 → 로직 오류, 강제 false
            print("⚠️ [경고] 세부품명번호가 없는데 has_direct_production=True로 설정됨. False로 수정합니다.")
            has_direct_production = False
            smpp_confirm_text = ""
        else:
            # 세부품명번호와 품명 정보 구성 - 형식: 코드(품명)
            item_parts = []
            for code in plan.item_codes:
                c_clean = re.sub(r'[^0-9]', '', code)
                if len(c_clean) == 10:
                    name = item_name_to_code_map.get(code, "")
                    if name:
                        # 형식: 코드(품명)
                        item_parts.append(f"{c_clean}({name})")
                    else:
                        item_parts.append(c_clean)
            
            if item_parts:
                # 복수일 때 쉼표로 연결: 5510159901(기타인쇄물), 4710150101(복사용지)
                item_info = ", ".join(item_parts)
                smpp_confirm_text = f"❍ 중소기업제품 구매촉진 및 판로지원에 관한법률 제9조 및 동법 시행규칙 제5조 규정에 의한 직접생산확인증명서[세부품명번호: {item_info}](개찰일 전일까지 발급된 것으로 유효기간 내에 있어야 함)를 소지한 자"
            else:
                # 품명번호는 있지만 유효한(10자리) 코드가 없는 경우
                print("⚠️ [경고] 세부품명번호가 invalid하여 has_direct_production=False로 수정합니다.")
                has_direct_production = False
                smpp_confirm_text = ""
    else:
        smpp_confirm_text = ""
            
    # [자격 요건 텍스트 생성 로직]
    qualification_parts = []
    part1_item = None
    part2_industry = None
    
    # 1. 세부품명번호 파트
    if plan.item_codes:
        items_str_list = []
        for code in plan.item_codes:
            name = item_name_to_code_map.get(code, "")
            items_str_list.append(f"[세부품명번호 : {code}({name})]")
            
        items_joined = ", ".join(items_str_list)
        # 요청사항 4번 포맷 준수: "❍입찰참가..." (띄어쓰기 주의) 
        # 사용자가 "❍ 입찰참가"와 "❍입찰참가"를 혼용했으나 "❍ 입찰참가"가 일반적이므로 유지하되, 복수일 때 대괄호 구조 반영
        part1_item = f"❍ 입찰참가 등록 마감일 기준 {items_joined} 제조 또는 공급물품으로 등록된 자"
        qualification_parts.append(part1_item)

    # 2. 업종코드 파트 (Code + Name Logic)
    final_codes = set(plan.industry_codes or [])
    if plan.industry_names_text:
        # 텍스트로 된 업종명에서 코드 역추적
        for name in plan.industry_names_text:
            found_code = get_code_by_name(name)
            if found_code:
                final_codes.add(found_code)
    
    sorted_codes = sorted(list(final_codes))
    
    # Update plan object for downstream consistency
    # API 검증 결과 매핑 준비
    # API 검증 결과 매핑 준비
    api_ind_map = {}
    if api_validation and "industries" in api_validation:
        for row in api_validation["industries"]:
            if row.get("status") == "OK" and row.get("매칭_업종명"):
                code_key = str(row.get("입력값", "")).strip()
                api_ind_map[code_key] = row.get("매칭_업종명")

    # [CRITICAL Fix] LLM이 놓쳤더라도, 앞단(APP)에서 찾아낸 유효한 코드는 강제로 포함시킨다.
    for code in api_ind_map.keys():
        if code not in sorted_codes:
            print(f"➕ [DEBUG] Adding code {code} found by Regex/API but missed by LLM")
            sorted_codes.append(code)
    sorted_codes.sort()

    plan.industry_codes = sorted_codes
    
    # [NEW] AI가 찾았지만 사전 검증(Regex)에서 놓친 코드에 대한 사후 API 조회 (Just-In-Time)
    from core.item_checker import verify_industry_with_api
    
    missing_codes = [c for c in sorted_codes if c not in api_ind_map]
    if missing_codes:
        print(f"🔎 [DEBUG] AI found new codes {missing_codes}, verifying with API...")
        # API 호출 (캐시 사용됨)
        try:
            post_rows = verify_industry_with_api(industry_codes_4=missing_codes)
            print(f"🔎 [DEBUG] API Result: {post_rows}")
            for row in post_rows:
                if row.get("status") == "OK" and row.get("매칭_업종명"):
                    code_key = str(row.get("입력값", "")).strip()
                    api_ind_map[code_key] = row.get("매칭_업종명")
        except Exception as e:
            print(f"❌ [DEBUG] API Call Failed: {e}")
            
    print(f"✅ [DEBUG] Final Industry Map: {api_ind_map}")

    # 리포트용 업종명 리스트
    final_industry_names = []

    if sorted_codes:
        inds_str_list = []
        for code in sorted_codes:
            # 1순위: API(사전+사후) 검증 결과, 2순위: 내장 매퍼
            name = api_ind_map.get(code) or get_industry_name_by_code(code)
            
            if name:
                inds_str_list.append(f"업종코드 : {code}({name})")
                final_industry_names.append(name)
            else:
                inds_str_list.append(f"업종코드 : {code}")
            
        inds_joined = ", ".join(inds_str_list)
        part2_industry = f"○ (나라장터(G2B) {inds_joined})을 입찰 참가로 등록한 자"
        qualification_parts.append(part2_industry)

    
    qualification_text = "\n".join(qualification_parts) if qualification_parts else None

    # 공고명 정제 (계획안, 붙임 등 제거)
    # 공고명 정제 (계획안, 붙임 등 제거)
    import re
    cleaned_title = plan.notice_title
    if cleaned_title:
        cleaned_title = cleaned_title.strip()
        
        # 1. 파일명 잔재 제거: [1], 붙임, 1. 등
        cleaned_title = re.sub(r"^\[\s*\d+\s*\]", "", cleaned_title)
        cleaned_title = re.sub(r"^붙임\s*\d*", "", cleaned_title).strip()
        
        # 2. 불필요한 접미사/설명 제거: 계획(안), 구매계획, ( )
        # "계획(안)", "계획안", "구매계획안", "구매 계획안" 등
        patterns = [r"계획\(?안\)?", r"구매\s*계획안?", r"\(.*?\)"] 
        for pat in patterns:
            cleaned_title = re.sub(pat, "", cleaned_title)
            
        cleaned_title = cleaned_title.strip()

    # 지역제한 공고문 표시용 텍스트 생성
    if region_limit:
        region_limit_text = f"마. 입찰공고일 전일[신규사업자(법인인 경우 법인등기일, 개인사업자인 경우 사업자등록일을 기준으로 한다)인 경우 입찰공고일 이후를 포함]부터 입찰일(다만 낙찰자는 계약체결일)까지 법인등기사항증명서상 본점 소재지(개인사업자인 경우에는 사업자등록증 또는 관련 법령에 따른 허가·인가·면허·등록·신고 등에 관련된 서류에 기재된 사업장의 소재지)를 계속하여 {region_limit}에 둔 업체"
    else:
        region_limit_text = ""  # 전체 지역 (None일 때 빈 문자열)
    
    patch = NoticePatch(
        notice_type=notice_type,
        notice_title=cleaned_title or plan.notice_title,
        contract_period_text=plan.contract_period_text,
        budget_vat_included_krw=int(plan.budget_vat_included_krw),
        estimated_price_ex_vat_krw=int(P),
        submission_start_dt=submission_start_dt,
        submission_period_text=submission_period_text,
        open_datetime_dt=open_datetime_dt,
        competition_method_text=competition_text,
        appendix_text=appendix,
        sme_limit_text=sme_limit,
        item_code_text=", ".join(plan.item_codes) if plan.item_codes else None,
        item_name_api_text=item_name_api_str,
        industry_code_text=", ".join([f"{c} ({get_industry_name_by_code(c)})" if get_industry_name_by_code(c) else c for c in (plan.industry_codes or [])]) or None,
        industry_name_text=", ".join(final_industry_names) if final_industry_names else None,
        qualification_text=qualification_text,
        qualification_item_text=part1_item,
        qualification_industry_text=part2_industry,
        consortium_text=consortium_text,
        consortium_status_text=consortium_status_text,
        consortium_deadline_dt=consortium_deadline_dt,
        has_direct_production=has_direct_production,
        smpp_confirm_text=smpp_confirm_text,
        region_limit=region_limit,
        region_limit_text=region_limit_text,  # 추가
        manager_info="##부(☎00-000-0000, 담당 : ### ##)",  # 고정값 (추출 안함)
        posted_date=date.today(),
    )

    audit = {
        "rules_version": "v2 (2025)",
        "decisions": {
            "notice_type": notice_type,
            "estimated_price_ex_vat_krw": P,
            "sme_limit_text": sme_limit,
            "region_limit": region_limit,
            "appendix_text": appendix,
            "competition_method_text": competition_text,
        },
        "inputs_present": {
            "item_code_text": bool(plan.item_codes),
            "consortium_enabled": bool(plan.consortium_enabled),
        },
        "legal_report": {
            "data": legal_data,
            "compliance_note": compliance_note
        }
    }

    # 보고서 텍스트 수정: CrewAI가 생성한 보고서의 공고 유형을 최종 판정 결과로 교체
    report_text = crew_res.get("report", "")
    
    # 공고 유형 한글 변환
    notice_type_kr = "적격심사" if notice_type == "eligible_review" else "소액수의"
    
    # 잘못된 공고 유형 키워드 교체
    if notice_type == "eligible_review":
        # 적격심사로 확정되었는데 보고서에 소액수의가 있으면 교체
        report_text = report_text.replace("소액수의견적입찰", "적격심사입찰")
        report_text = report_text.replace("소액수의 견적제출", "적격심사 입찰")
        print(f"📝 [보고서 수정] 공고 유형을 '적격심사'로 통일")
    else:
        # 소액수의로 확정되었는데 보고서에 적격심사가 있으면 교체
        report_text = report_text.replace("적격심사입찰", "소액수의견적입찰")  
        report_text = report_text.replace("적격심사 입찰", "소액수의 견적제출")
        print(f"📝 [보고서 수정] 공고 유형을 '소액수의'로 통일")

    return {
        "plan": plan.model_dump(), 
        "patch": patch.model_dump(), 
        "audit": audit,
        "report": report_text  # 수정된 보고서 사용
    }

