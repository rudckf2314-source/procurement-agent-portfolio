# core/direct_production_checker.py
import re
from typing import Optional, Dict, Any, List, Set, Tuple


# -----------------------------
# 1) 계획안(텍스트/파일) -> raw_text 통일
# -----------------------------
def plan_to_text(
    raw_text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
) -> str:
    """
    계획안 입력을 텍스트로 통일해서 반환.
    - raw_text가 있으면 그걸 우선 사용
    - file_bytes+filename이 있으면 확장자로 파서 선택
    """
    if raw_text and raw_text.strip():
        return raw_text

    if not file_bytes or not filename:
        return ""

    name = filename.lower()

    if name.endswith(".pdf"):
        from core.parsers.pdf_parser import pdf_to_text
        return pdf_to_text(file_bytes) or ""

    if name.endswith(".hwp"):
        from core.parsers.hwp_parser import get_hwp_text
        return get_hwp_text(file_bytes) or ""

    if name.endswith(".hwpx"):
        from core.parsers.hwpx_parser import hwpx_bytes_to_text
        return hwpx_bytes_to_text(file_bytes) or ""

    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        from core.parsers.excel_parser import excel_to_text
        return excel_to_text(file_bytes) or ""

    # 알 수 없는 형식이면 빈값
    return ""


# -----------------------------
# 2) 계획안 텍스트에서 세부품목번호(10자리)만 추출
# -----------------------------
def extract_plan_item_codes_10(raw_text: str) -> List[str]:
    """
    계획안 텍스트에서 10자리 숫자(세부품목번호/세부품명번호)만 추출.
    """
    text = raw_text or ""
    # 공백/하이픈이 끼어있는 경우가 있어 제거한 버전도 함께 탐색
    compact = re.sub(r"[\s\-]", "", text)

    codes = re.findall(r"\b\d{10}\b", compact)
    # 중복 제거 + 정렬
    codes = sorted(set(codes))
    return codes


# -----------------------------
# 3) SMPP 제한 목록(10자리) 가져오기
# -----------------------------
def fetch_smpp_restricted_codes(
    atchFileId: str,
    fileSn: str,
    fileKey: str,
) -> Set[str]:
    """
    SMPP 고시 첨부(hwpx 등)에서 제한 목록 세부품목번호(10자리) set으로 반환.
    (CSV 저장 없음)
    """
    from core.smpp_download import get_smpp_item_codes_df

    df = get_smpp_item_codes_df(
        atchFileId=atchFileId,
        fileSn=fileSn,
        fileKey=fileKey,
        use_notice_parser=False,  # 가장 견고한 정규식 기반 추출 사용
    )

    if df is None or df.empty:
        return set()

    # df 컬럼명이 '세부품명번호'로 되어있을 수도 있어 방어
    col = None
    for c in ["세부품목번호", "세부품명번호", "세부품명번호", "세부품명번호", "세부품명번호"]:
        if c in df.columns:
            col = c
            break
    # 우리가 만든 df는 '세부품명번호'로 나오도록 되어있음
    if col is None and "세부품명번호" in df.columns:
        col = "세부품명번호"
    if col is None and "세부품목번호" in df.columns:
        col = "세부품목번호"
    if col is None:
        # get_smpp_item_codes_df가 반환하는 기본 컬럼명은 '세부품명번호'였음
        # 여기까지 오면 구조가 바뀐 것
        return set()

    codes = df[col].astype(str).str.replace(r"\D", "", regex=True)
    codes = codes[codes.str.len() == 10]
    return set(codes.tolist())


# -----------------------------
# 4) 최종 판정 함수
# -----------------------------
def judge_direct_production_restriction(
    *,
    plan_raw_text: Optional[str] = None,
    plan_file_bytes: Optional[bytes] = None,
    plan_filename: Optional[str] = None,
    smpp_atchFileId: str,
    smpp_fileSn: str,
    smpp_fileKey: str,
    smpp_restricted_codes: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    반환:
      {
        "is_restricted": bool,
        "hit_codes": [..],
        "plan_codes": [..],
        "message": str
      }
    """
    # 1) 계획안 -> 텍스트
    raw_text = plan_to_text(plan_raw_text, plan_file_bytes, plan_filename)

    # 2) 계획안 10자리 코드 추출
    plan_codes = extract_plan_item_codes_10(raw_text)

    # 3) SMPP 제한 목록 로드(외부에서 set을 주면 재다운로드 안 함)
    if smpp_restricted_codes is None:
        smpp_restricted_codes = fetch_smpp_restricted_codes(
            atchFileId=smpp_atchFileId,
            fileSn=smpp_fileSn,
            fileKey=smpp_fileKey,
        )

    # 4) 교집합 판정
    hit = sorted(set(plan_codes) & set(smpp_restricted_codes))

    is_restricted = len(hit) > 0
    if is_restricted:
        msg = "해당 계획안은 직접생산확인증명서 제한에 해당하는 제품입니다."
    else:
        msg = "해당 계획안은 직접생산확인증명서 제한 대상이 아닙니다."

    return {
        "is_restricted": is_restricted,
        "hit_codes": hit,
        "plan_codes": plan_codes,
        "message": msg,
    }
