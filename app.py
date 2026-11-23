import json
import os
from datetime import datetime
import streamlit as st
import pandas as pd
from core.item_checker import (
    extract_candidates_from_text,
    verify_items_with_api,
    verify_industry_with_api,
)
from core.direct_production_checker import judge_direct_production_restriction
from core.smpp_api import fetch_pf_cert_info  # (FIX2에 있던 SMPP 사업자 조회도 같이 쓰려면)
from dotenv import load_dotenv

load_dotenv()

from core.parsers.excel_parser import excel_to_text
from core.parsers.text_parser import normalize_text
from core.parsers.pdf_parser import pdf_to_text
from core.parsers.hwp_parser import get_hwp_text
from core.parsers.docx_parser import docx_to_text
from core.docx_editor import generate_docx_from_template
from crew.crew_runner import run_pipeline

st.set_page_config(page_title="구매계획안 → 공고문 수정값 생성기", layout="wide")

# ✅ SMPP 고시 첨부파일 파라미터 (중앙 관리 - smpp_download.smpp_database_num 사용)
from core.smpp_download import smpp_database_num

SMPP_ATCH_FILE_ID = smpp_database_num["atchFileId"]
SMPP_FILE_SN = smpp_database_num["fileSn"]
SMPP_FILE_KEY = smpp_database_num["fileKey"]

st.title("공고문 생성기")
st.write("구매계획안을 바탕으로 공고문을 생성합니다.")

# ========================================
# 사이드바: SMPP 데이터베이스 정보
# ========================================
with st.sidebar:
    st.subheader(" SMPP 데이터베이스")
    
    from core.smpp_download import load_smpp_from_cache, get_smpp_item_codes_df, save_smpp_to_cache
    from datetime import datetime
    
    # 현재 캐시 정보 로드
    cached_data = load_smpp_from_cache(SMPP_ATCH_FILE_ID)
    
    if cached_data:
        metadata = cached_data.get("metadata", {})
        notice_info = metadata.get("notice_info", {})
        
        # 고시 정보 표시
        st.info(f"""
**📋 현재 사용 중인 고시**

**{notice_info.get('department', '-')} 제 {notice_info.get('notice_number', '-')}호**  
고시일자: {notice_info.get('notice_date', '-')}  
제한 품목: **{metadata.get('total_count', 0)}개**
        """)
        
        # 캐시 상태
        extracted_at_str = metadata.get("extracted_at")
        if extracted_at_str:
            try:
                extracted_at = datetime.fromisoformat(extracted_at_str)
                cache_age = datetime.now() - extracted_at
                expiry_days = metadata.get("cache_expiry_days", 80)
                remaining_days = expiry_days - cache_age.days
                
                if remaining_days > 0:
                    st.success(f" 캐시 유효 (만료까지 {remaining_days}일)")
                else:
                    st.warning(f" 캐시 만료됨 ({cache_age.days}일 경과)")
            except:
                pass
    else:
        st.warning(" SMPP 데이터베이스 캐시 없음")
    
    # 새로고침 버튼
    if st.button(" SMPP 데이터 새로고침", use_container_width=True):
        with st.spinner("SMPP 파일 다운로드 중..."):
            try:
                # 최신 데이터 다운로드 및 자동 분석
                from core.smpp_download import download_and_update_smpp_cache
                
                result = download_and_update_smpp_cache()
                
                total_count = result["total_count"]
                notice_info = result["notice_info"]
                
                st.success(f" {total_count}개 품목 업데이트 완료! (고시: {notice_info.get('notice_number')})")
                st.rerun()
            except Exception as e:
                st.error(f" 다운로드 실패: {e}")
    
    st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("입력")
    mode = st.radio("입력 방식", ["텍스트 붙여넣기", "파일 업로드 (PDF/HWP/Excel/Word)"], horizontal=False)

    raw_text = ""
    if mode == "텍스트 붙여넣기":
        raw_text = st.text_area("구매계획안 텍스트", height=320)
        raw_text = normalize_text(raw_text)
    else:
        f = st.file_uploader("구매계획안 파일", type=["pdf", "hwp", "xlsm", "xlsx", "docx", "doc"])
        if f is not None:
            file_bytes = f.read()
            if f.name.lower().endswith(".pdf"):
                raw_text = pdf_to_text(file_bytes)
            elif f.name.lower().endswith(".hwp"):
                raw_text = get_hwp_text(file_bytes)
            elif f.name.lower().endswith(".docx") or f.name.lower().endswith(".doc"):
                raw_text = docx_to_text(file_bytes)
            else:
                raw_text = excel_to_text(file_bytes)

    open_dt_str = st.text_input("게시일시 (입력 없으면 현재 시간 적용)", value="")
    try:
        if open_dt_str.strip():
            fallback_open_dt = datetime.fromisoformat(open_dt_str.strip())
        else:
            raise ValueError("Empty string")
    except ValueError:
        if open_dt_str.strip():
            st.warning("날짜 형식이 올바르지 않습니다. 기본값(오늘 11:00)을 사용합니다. 형식 예: 2025-05-20 14:00")
        # 기본 제출 시작일(예: 오늘 11:00)
        now = datetime.now()
        fallback_open_dt = now.replace(hour=11, minute=0, second=0, microsecond=0)

    st.subheader("설정")
    
    # 추출 방식 선택 UI 제거 (무조건 CrewAI 사용 + 법령연동)
    st.info(" CrewAI 법령 연동 에이전트가 활성화되었습니다. (2025 최신 조달규정 자동 적용)")
    
    notice_type_kr = st.radio("공고 유형 선택", ["자동", "적격심사", "소액수의"], horizontal=True)

    run_btn = st.button("수정값 생성")


with col2:
    st.subheader("출력")
    if run_btn:
        # Map KR selection to internal code
        notice_map = {"자동": "auto", "적격심사": "eligible_review", "소액수의": "small_quote"}
        selected_type = notice_map.get(notice_type_kr, "auto")

        if not raw_text:
            st.warning("입력 텍스트가 비어 있습니다.")
        else:
            # 디버그: 추출된 텍스트 미리보기
            with st.expander(" 추출된 텍스트 미리보기 (디버그)"):
                st.text_area("파일에서 추출된 원본 텍스트", raw_text, height=200)
                st.info(f"총 {len(raw_text)} 글자 추출됨")
            
            try:
                # 진행 상태 표시 (Status Container)
                with st.status("작업 중입니다...", expanded=True) as status:
                    st.write("최신 조달 법령 및 고시 기준 조회 중...")
                    
                    #  (1단계) 계획안 텍스트에서 후보 추출 → API 검증
                    cand = extract_candidates_from_text(raw_text)
                    #  (추가) SMPP 직접생산확인증명서 제한 판정
                    dp_result = judge_direct_production_restriction(
                        plan_raw_text=raw_text,
                        smpp_atchFileId=SMPP_ATCH_FILE_ID,
                        smpp_fileSn=SMPP_FILE_SN,
                        smpp_fileKey=SMPP_FILE_KEY,
                    )

                    # 결과 메시지 표시
                    if dp_result.get("is_restricted"):
                        st.error(dp_result.get("message", "직접생산확인증명서 제한 대상입니다."))
                        st.write(" 제한에 걸린 세부품목번호:", dp_result.get("hit_codes", []))
                    else:
                        st.success(dp_result.get("message", "직접생산확인증명서 제한 대상이 아닙니다."))

                    st.write("물품 및 업종 정보 API 검증 중...")
                    item_rows = verify_items_with_api(
                        item_codes_10=cand["item_codes_10"],
                        item_name=cand["item_name"],
                    )
                    industry_rows = verify_industry_with_api(
                        industry_codes_4=cand["industry_codes_4"],
                        industry_name=cand["industry_name"],
                    )
                    
                    # 검증 결과 시각화
                    with st.expander(" 조달청 API 검증 결과: 물품/업종", expanded=True):
                        st.write("### 물품 검증")
                        if item_rows:
                            st.dataframe(pd.DataFrame(item_rows), use_container_width=True)
                        else:
                            st.info("계획안에서 '세부품명번호(10자리)' 또는 '품명'을 찾지 못했습니다.")

                        st.write("### 업종 검증")
                        if industry_rows:
                            st.dataframe(pd.DataFrame(industry_rows), use_container_width=True)
                        else:
                            st.info("계획안에서 '업종코드(4자리)' 또는 '업종명'을 찾지 못했습니다.")
                    
                    api_validation = {
                        "items": item_rows,
                        "industries": industry_rows,
                    }

                    # 실제 실행
                    result = run_pipeline(
                        raw_text=raw_text,
                        fallback_open_dt=fallback_open_dt,
                        manual_notice_type=selected_type,
                        use_context=True,
                        use_crew=True,
                        api_validation=api_validation
                    )
                    st.write("구매계획안 정밀 분석 완료!")
                    st.write("법적 요건 검토 및 공고문 수정안 확정 중...")
                    
                    status.update(label="분석 및 생성 완료!", state="complete", expanded=False)
                
                patch = result["patch"]
                audit = result["audit"]

                # 0. 법령 검토 리포트 (최상단 강조)
                if "legal_report" in audit and "data" in audit["legal_report"]:
                    legal_data = audit["legal_report"]["data"]
                    compliance_note = audit["legal_report"].get("compliance_note", "")

                    st.markdown("###  법령 검토 보고서 (2025.1.1 기준)")
                    
                    l_col0, l_col1, l_col2 = st.columns([1.5, 1, 1])
                    
                    with l_col0:
                        st.info(f"**적용 법령/고시**\n\n{legal_data.get('gosi_amount', {}).get('reference', '-')}")
                        st.caption(f"기준: {legal_data.get('gosi_amount', {}).get('statute', '')}")

                    with l_col1:
                        st.metric("현재 고시금액 기준", legal_data.get('gosi_amount', {}).get('content', '-'))
                    
                    with l_col2:
                         st.metric("분석된 추정가격", f"{patch['estimated_price_ex_vat_krw']:,} 원")

                    # 법령 상세 내용 펼치기
                    with st.expander(" 상세 법령 적용 기준 보기 (참고자료)"):
                        st.markdown(f"**1. 기업규모 제한 기준** ({legal_data.get('sme_limit', {}).get('reference', '')})")
                        for rule in legal_data.get("sme_limit", {}).get("rules", []):
                            st.write(f"- {rule['range']} : **{rule['limit']}**")
                        
                        st.markdown("---")
                        st.markdown(f"**2. 적격심사 별표 기준** ({legal_data.get('appendix_criteria', {}).get('reference', '')})")
                        for rule in legal_data.get("appendix_criteria", {}).get("rules", []):
                            st.write(f"- {rule['condition']} : **{rule['appendix']}**")
                            
                    st.success(f"** 법무 검토 의견 (Compliance Note)**\n\n{compliance_note}")
                    st.divider()

                # 1. Summary
                notice_type_map = {"small_quote": "소액수의", "eligible_review": "적격심사"}
                notice_type_kr = notice_type_map.get(patch["notice_type"], patch["notice_type"])
                
                st.subheader(f" 결과 요약: **[{notice_type_kr}]** 진행")
                
                # 2. Key Dates (Emphasized)
                d_col1, d_col2 = st.columns(2)
                d_col1.metric("제출기간", patch["submission_period_text"])
                d_col2.metric("개찰일시", patch["open_datetime_dt"].strftime("%Y-%m-%d %H:%M"))

                # 3. Modification Table
                # 탭 구성
                tab_main, tab_report = st.tabs(["분석 요약", " 생성 보고서"])

                with tab_main:
                    st.subheader("공고문 변경/반영 사항")
                    
                    # 지역 제한 문구 정제
                    region_text = patch["region_limit"]
                    if not region_text:
                        if patch['estimated_price_ex_vat_krw'] >= 230000000:
                            region_text = "전국 (고시금액 2.3억 초과로 제한 불가)"
                        else:
                            region_text = "전국 (지역제한 문구 미발견)"

                    table_data = [
                        {"항목": "공고명", "내용": patch["notice_title"], "key": "notice_title"},
                        {"항목": "계약기간", "내용": patch["contract_period_text"], "key": "contract_period_text"},
                        {"항목": "예산액(VAT포함)", "내용": f"{patch['budget_vat_included_krw']:,} 원", "key": "budget_vat_included_krw"},
                        {"항목": "추정가격(VAT제외)", "내용": f"{patch['estimated_price_ex_vat_krw']:,} 원", "key": "estimated_price_ex_vat_krw"},
                        {"항목": "경쟁방식", "내용": patch["competition_method_text"], "key": "competition_method_text"},
                        {"항목": "업종코드", "내용": patch.get("industry_code_text") or "-", "key": "industry_code_text"},
                        {"항목": "업종명", "내용": patch.get("industry_name_text") or "-", "key": "industry_name_text"},
                        {"항목": "별표(적격심사 시)", "내용": patch["appendix_text"] or "-", "key": "appendix_text"},
                        {"항목": "기업규모 제한", "내용": patch["sme_limit_text"], "key": "sme_limit_text"},
                        {"항목": "지역 제한", "내용": region_text, "key": "region_limit"},
                        {"항목": "직접생산확인", "내용": "필요 (중기간경쟁제품)" if patch["has_direct_production"] else "필요없음", "key": "has_direct_production"},
                        {"항목": "직접생산확인 안내문구", "내용": patch.get("smpp_confirm_text") or "", "key": "smpp_confirm_text"},
                        {"항목": "공동계약", "내용": patch["consortium_text"], "key": "consortium_text"},
                        {"항목": "공동수급협정서 마감", "내용": patch["consortium_deadline_dt"].strftime("%Y-%m-%d %H:%M") if patch["consortium_deadline_dt"] else "-", "key": "consortium_deadline_dt"},
                        {"항목": "세부품명번호", "내용": patch["item_code_text"] or "-", "key": "item_code_text"},
                        {"항목": "세부품명 (API 조회)", "내용": patch.get("item_name_api_text") or "-", "key": "item_name_api_text"},
                        {"항목": "담당자 정보", "내용": patch.get("manager_info") or "환경처 조달부(☎02-2110-0000, 담당 : 홍길동 대리)", "key": "manager_info"},
                    ]
                    
                    st.info("💡 아래 표의 '내용'을 더블클릭하여 직접 수정할 수 있습니다. 수정된 내용은 보고서에 자동 반영됩니다.")
                    edited_data = st.data_editor(
                        table_data, 
                        column_config={
                            "항목": st.column_config.TextColumn(disabled=True),
                            "내용": st.column_config.TextColumn(width="large"),
                            "key": None # Hide key column
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # 수정된 내용 반영 (Update Patch Object)
                    for row in edited_data:
                        key = row.get("key")
                        new_val = row.get("내용")
                        if key and key in patch:
                            # 텍스트 그대로 반영 (원본 데이터 타입 무시하고 덮어씀)
                            patch[key] = new_val
                
                with tab_report:
                    st.subheader("AI 작성 결재 리포트")
                    report_content = result.get("report", "")
                    if report_content:
                        st.markdown(report_content)
                        
                        st.divider()
                        col_md, col_word = st.columns(2)
                        
                        with col_md:
                            st.download_button("보고서 다운로드 (Markdown)", report_content, file_name="report.md")
                            
                        with col_word:
                            try:
                                patch_data = result.get("patch", {})
                                notice_type = patch_data.get("notice_type", "")
                                
                                # 템플릿 파일 선택
                                if "eligible" in notice_type:
                                    tpl_file = "[공고문] 적격심사 양식_smallpdf.docx"
                                    draft_name = "적격심사_보고서.docx"
                                else:
                                    tpl_file = "[공고문] 소액수의 양식_smallpdf.docx"
                                    draft_name = "소액수의_보고서.docx"
                                    
                                tpl_path = os.path.join(os.getcwd(), "file_example", tpl_file)
                                
                                if os.path.exists(tpl_path):
                                    # 포맷팅을 위한 데이터 복사
                                    replacements = patch_data.copy()
                                    
                                    # [추가] 공고 유형 한글 변환 (small_quote -> 소액수의)
                                    type_map = {
                                        "small_quote": "소액수의",
                                        "eligible_review": "적격심사",
                                        "private_contract": "수의계약",
                                        "limited_competition": "제한경쟁",
                                        "general_competition": "일반경쟁"
                                    }
                                    raw_type = replacements.get("notice_type", "")
                                    replacements["notice_type"] = type_map.get(raw_type, raw_type)
                                    
                                    # 날짜 포맷팅
                                    if replacements.get("open_datetime_dt") and hasattr(replacements["open_datetime_dt"], "strftime"):
                                        replacements["open_datetime_dt"] = replacements["open_datetime_dt"].strftime("%Y-%m-%d %H:%M")
                                    if replacements.get("consortium_deadline_dt") and hasattr(replacements["consortium_deadline_dt"], "strftime"):
                                        replacements["consortium_deadline_dt"] = replacements["consortium_deadline_dt"].strftime("%Y-%m-%d %H:%M")

                                    # [추가] 게시일시 한글 포맷 (posted_date_kr)
                                    # submission_start_dt가 게시일시임
                                    sub_start = replacements.get("submission_start_dt")
                                    if sub_start:
                                        if isinstance(sub_start, str):
                                            # 문자열이면 파싱 시도
                                            try:
                                                import dateutil.parser
                                                dt_obj = dateutil.parser.parse(sub_start)
                                            except:
                                                dt_obj = None
                                        else:
                                            # datetime 객체
                                            dt_obj = sub_start
                                        
                                        if dt_obj and hasattr(dt_obj, 'strftime'):
                                            replacements["posted_date_kr"] = dt_obj.strftime("%Y년 %m월 %d일")

                                    # 금액 포맷팅 (천단위 콤마)
                                    for key in ["budget_vat_included_krw", "estimated_price_ex_vat_krw"]:
                                        val = replacements.get(key)
                                        if isinstance(val, (int, float)):
                                            replacements[key] = f"{val:,}"

                                    # DOCX 생성 함수 호출
                                    docx_bytes = generate_docx_from_template(tpl_path, replacements)
                                    
                                    st.download_button(
                                        label="보고서 다운로드 (Word)",
                                        data=docx_bytes,
                                        file_name=draft_name,
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                    )
                                else:
                                    st.warning(f"Word 템플릿(file_example/{tpl_file})을 찾을 수 없습니다.")
                                    
                            except Exception as e:
                                st.error(f"DOCX 생성 오류: {e}")
                    else:
                        st.info("보고서가 생성되지 않았습니다.")

                # 4. JSON & Downloads
                patch_json = json.dumps(patch, ensure_ascii=False, indent=2, default=str)
                audit_json = json.dumps(audit, ensure_ascii=False, indent=2)

                with st.expander(" 상세 JSON 및 로그 확인"):
                    st.text("notice_patch.json")
                    st.code(patch_json, language="json")
                    st.text("audit_log.json")
                    st.code(audit_json, language="json")

                # Downloads - 사용자 요청으로 제거함
                # d_btn1, d_btn2 = st.columns(2)
                # d_btn1.download_button(
                #     "notice_patch.json 다운로드",
                #     data=patch_json.encode("utf-8"),
                #     file_name="notice_patch.json",
                #     mime="application/json",
                # )
                # d_btn2.download_button(
                #     "audit_log.json 다운로드",
                #     data=audit_json.encode("utf-8"),
                #     file_name="audit_log.json",
                #     mime="application/json",
                # )
            except Exception as e:
                st.error(f"실행 실패: {type(e).__name__}")
                st.error(f"상세 오류: {str(e)}")
                
                # 디버그 정보 표시
                with st.expander("디버그 정보"):
                    import traceback
                    st.code(traceback.format_exc(), language="python")
                    
                    # OpenAI 호출 전 단계에서 실패했는지 확인
                    st.write("**가능한 원인:**")
                    st.write("1. HWP 파일 파싱 실패 → 추출된 텍스트 확인")
                    st.write("2. OpenAI API 오류 → API 키 확인")
                    st.write("3. 데이터 구조 불일치 → 스키마 확인")

