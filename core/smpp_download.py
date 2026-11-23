import re
import requests
import pandas as pd
import json
import os
from datetime import datetime

NOTICE_URL = "https://www.smpp.go.kr/cst/notice/selectNoticeVw.do"  # 파일이 걸린 게시글 페이지
DOWNLOAD_URL = "https://www.smpp.go.kr/cmm/fms/FileDown.do"

# ✅ SMPP 데이터베이스 설정 (중앙 관리)
# 직접생산확인증명서 제한대상 세부품명번호 지정 고시 파일
smpp_database_num = {
    "atchFileId": "FILE_000000020843296",
    "fileSn": "1",
    "fileKey": "161128",
    "notice_info": {
        "department": "중소벤처기업부",
        "notice_number": "2025-96",
        "notice_date": "2025.08.29",
        "title": "「중소기업자간 경쟁제품」 지정(스마트조명및설비) 등 고시 알림"
    }
}


def download_smpp_file(atchFileId: str, fileSn: str, fileKey: str, notice_url: str = NOTICE_URL) -> bytes:
    """
    SMPP 첨부파일 다운로드 (bytes 반환)
    - notice_url: 실제 파일이 달린 게시글 URL (쿠키/세션 받기용)
    """
    s = requests.Session()

    # 1) 게시글 페이지를 먼저 열어 세션 쿠키 받기(중요)
    s.get(notice_url, timeout=20)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": notice_url,
        "Accept": "*/*",
    }
    params = {
        "atchFileId": atchFileId,
        "fileSn": fileSn,
        "fileKey": fileKey,
    }

    r = s.get(
        DOWNLOAD_URL,
        params=params,
        headers=headers,
        timeout=20,
        allow_redirects=True,
    )
    r.raise_for_status()

    # 혹시 HTML(에러페이지) 내려오는 경우 방지용 간단 체크
    head = r.content[:200]
    if b"<html" in head.lower() or b"<!doctype html" in head.lower():
        raise RuntimeError("다운로드 응답이 파일이 아니라 HTML입니다(세션/파라미터/권한 문제 가능).")

    return r.content


def extract_item_codes_from_hwpx_bytes(hwpx_bytes: bytes) -> pd.DataFrame:
    """
    hwpx bytes -> 텍스트 -> (세부품명번호)만 추출 -> DataFrame 반환
    반환 컬럼: ['세부품명번호']
    """
    from core.parsers.hwpx_parser import hwpx_bytes_to_text

    text = hwpx_bytes_to_text(hwpx_bytes) or ""

    # 1) 정규식으로 10자리 숫자 후보 수집(문서 전체에서)
    #    (세부품명번호는 '10자리 숫자' 형태로 문서에 반복 등장하므로 이 방식이 가장 견고함)
    codes = re.findall(r"\b\d{10}\b", text)

    # 2) 정리 (중복 제거, 길이 재검증)
    df = pd.DataFrame({"세부품명번호": codes})
    if df.empty:
        return df

    df["세부품명번호"] = df["세부품명번호"].astype(str).str.strip()
    df = df[df["세부품명번호"].str.fullmatch(r"\d{10}")]

    df = df.drop_duplicates().sort_values("세부품명번호").reset_index(drop=True)
    return df


def extract_item_codes_from_notice_text_parser(text: str) -> pd.DataFrame:
    """
    (옵션) 이미 만들어둔 core.smpp_notice_parser 기반으로 추출하고 싶을 때 사용.
    - 기존 extract_item_pairs_from_notice_text() 결과가 (세부품명번호, 품명) 형태라면
      여기서 '세부품명번호'만 뽑아 DataFrame으로 정리함.
    """
    from core.smpp_notice_parser import extract_item_pairs_from_notice_text

    pairs = extract_item_pairs_from_notice_text(text) or []
    if not pairs:
        return pd.DataFrame(columns=["세부품명번호"])

    df = pd.DataFrame(pairs)

    # 여러 이름 케이스 대응
    rename_map = {
        "dtilPrdctClsfcNo": "세부품명번호",
        "item_code": "세부품명번호",
        "세부품명번호": "세부품명번호",
    }
    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})

    if "세부품명번호" not in df.columns:
        return pd.DataFrame(columns=["세부품명번호"])

    df = df[["세부품명번호"]].dropna()
    df["세부품명번호"] = df["세부품명번호"].astype(str).str.strip()
    df = df[df["세부품명번호"].str.fullmatch(r"\d{10}")]
    df = df.drop_duplicates().sort_values("세부품명번호").reset_index(drop=True)
    return df


def get_smpp_item_codes_df(
    atchFileId: str,
    fileSn: str,
    fileKey: str,
    notice_url: str = NOTICE_URL,
    use_notice_parser: bool = False,
) -> pd.DataFrame:
    """
    SMPP 첨부(hwpx) 다운로드 -> 파싱 -> 세부품명번호 DataFrame 반환
    - CSV 저장 없음
    """
    hwpx_bytes = download_smpp_file(atchFileId, fileSn, fileKey, notice_url=notice_url)

    if use_notice_parser:
        # notice_parser를 쓰려면 텍스트로 변환 후 pairs 기반 추출
        from core.parsers.hwpx_parser import hwpx_bytes_to_text
        text = hwpx_bytes_to_text(hwpx_bytes) or ""
        return extract_item_codes_from_notice_text_parser(text)

    # 기본은 정규식 기반 10자리 코드 추출(가장 견고)
    return extract_item_codes_from_hwpx_bytes(hwpx_bytes)


def save_smpp_to_cache(
    df: pd.DataFrame,
    atchFileId: str,
    fileSn: str,
    fileKey: str,
    cache_dir: str = None,
    notice_info: dict = None
) -> str:
    """
    추출된 세부품명번호를 JSON 형식으로 캐시 폴더에 저장
    
    Args:
        df: 세부품명번호 DataFrame
        atchFileId: 첨부파일 ID
        fileSn: 파일 순번
        fileKey: 파일 키
        cache_dir: 캐시 저장 경로 (기본: 프로젝트/cache)
        notice_info: 고시 정보 dict (department, notice_number, notice_date, title)
    
    반환: 저장된 파일 경로
    """
    if cache_dir is None:
        # 기본 캐시 디렉토리 (프로젝트 루트/cache)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(current_dir, "cache")
    
    # 캐시 디렉토리 생성 (없으면)
    os.makedirs(cache_dir, exist_ok=True)
    
    # 기본 고시 정보 (실제 SMPP 파일 정보)
    if notice_info is None:
        notice_info = {
            "department": "중소벤처기업부",
            "notice_number": "2024-138",  # 실제 고시번호 (예시)
            "notice_date": "2024.11.06",   # 실제 고시일자 (예시)
            "title": "직접생산확인증명서 제한대상 세부품명번호 지정 고시"
        }
    
    # JSON 데이터 구조
    data = {
        "metadata": {
            "atchFileId": atchFileId,
            "fileSn": fileSn,
            "fileKey": fileKey,
            "extracted_at": datetime.now().isoformat(),
            "total_count": len(df),
            "cache_expiry_days": 80,
            "notice_info": notice_info
        },
        "item_codes": df["세부품명번호"].tolist() if not df.empty else []
    }
    
    # 파일명 생성 (파일ID 기반)
    filename = f"smpp_{atchFileId}.json"
    filepath = os.path.join(cache_dir, filename)
    
    # JSON 저장
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath


def load_smpp_from_cache(
    atchFileId: str,
    cache_dir: str = None,
    force_refresh: bool = False
) -> dict:
    """
    캐시에서 SMPP 데이터 로드 (80일 이상 경과 시 자동 만료)
    
    Args:
        atchFileId: 첨부파일 ID
        cache_dir: 캐시 디렉토리 경로
        force_refresh: True이면 캐시 무시하고 None 반환
    
    반환: {"metadata": {...}, "item_codes": [...]} 또는 None (캐시 없거나 만료됨)
    """
    if force_refresh:
        return None
        
    if cache_dir is None:
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cache_dir = os.path.join(current_dir, "cache")
    
    filename = f"smpp_{atchFileId}.json"
    filepath = os.path.join(cache_dir, filename)
    
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 캐시 만료 검사 (80일)
    extracted_at_str = data.get("metadata", {}).get("extracted_at")
    if extracted_at_str:
        try:
            extracted_at = datetime.fromisoformat(extracted_at_str)
            cache_age = datetime.now() - extracted_at
            cache_expiry_days = data.get("metadata", {}).get("cache_expiry_days", 80)
            
            if cache_age.days >= cache_expiry_days:
                print(f"⚠️  캐시 만료됨 ({cache_age.days}일 경과, 만료 기준: {cache_expiry_days}일)")
                print(f"   캐시를 삭제하고 최신 데이터를 다운로드합니다.")
                # 만료된 캐시 파일 삭제
                os.remove(filepath)
                return None
        except Exception as e:
            print(f"⚠️  캐시 만료 검사 실패: {e}")
            pass
    
    return data


def check_item_in_smpp_database(item_code_text: str) -> bool:
    """
    item_code_text가 SMPP 데이터베이스(제한 대상 품목)에 존재하는지 확인
    
    Args:
        item_code_text: 세부품명번호 (10자리, 쉼표로 구분 가능)
    
    Returns:
        True: 제한 대상 품목에 포함됨 (직접생산확인 필요)
        False: 제한 대상 아님 (직접생산확인 필요없음)
    """
    if not item_code_text or item_code_text.strip() == "-":
        return False
    
    # smpp_database_num에서 파라미터 가져오기
    atchFileId = smpp_database_num["atchFileId"]
    
    # 캐시에서 SMPP 데이터 로드 (없으면 다운로드)
    cached_data = load_smpp_from_cache(atchFileId)
    
    if not cached_data:
        # 캐시 없으면 새로 다운로드
        df = get_smpp_item_codes_df(
            atchFileId=smpp_database_num["atchFileId"],
            fileSn=smpp_database_num["fileSn"],
            fileKey=smpp_database_num["fileKey"]
        )
        
        # 캐시에 저장
        save_smpp_to_cache(
            df=df,
            atchFileId=smpp_database_num["atchFileId"],
            fileSn=smpp_database_num["fileSn"],
            fileKey=smpp_database_num["fileKey"],
            notice_info=smpp_database_num["notice_info"]
        )
        
        smpp_codes = set(df["세부품명번호"].tolist())
    else:
        smpp_codes = set(cached_data.get("item_codes", []))
    
    # item_code_text 파싱 (쉼표로 여러 개 올 수 있음)
    codes = re.findall(r"\d{10}", item_code_text.replace(",", " ").replace("-", ""))
    
    # 하나라도 SMPP 데이터베이스에 있으면 True
    for code in codes:
        if code in smpp_codes:
            return True
    
    return False


def extract_notice_info_from_text(text: str) -> dict:
    """
    텍스트에서 고시 번호와 날짜, 제목(유추)을 추출
    """
    info = {
        "department": "중소기업자간 경쟁제품",
        "notice_date": datetime.now().strftime("%Y.%m.%d"),
        "title": "중소기업자간 경쟁제품 지정 고시"
    }
    
    if not text:
        return info

    # 1. 고시 번호 추출 (예: 제2025-96호, 제 2025-96 호)
    # 패턴: "제" + 공백? + (숫자4개-숫자+) + 공백? + "호"
    match_no = re.search(r"제\s?(\d{4}-\d+)\s?호", text)
    if match_no:
        info["notice_number"] = match_no.group(1)

    # 2. 날짜 추출 (예: 2025. 8. 29, 2025.08.29)
    # 문서 앞부분(500자 이내)에서 주로 날짜가 나옴
    head_text = text[:1000]
    match_date = re.search(r"20\d{2}[\.\-]\s?\d{1,2}[\.\-]\s?\d{1,2}", head_text)
    if match_date:
        # 공백 제거 및 포맷 통일
        raw_date = match_date.group(0).replace("-", ".")
        info["notice_date"] = raw_date
        
    return info


def download_and_update_smpp_cache() -> dict:
    """
    SMPP 파일 다운로드 -> 텍스트 파싱 -> 정보 추출(고시번호 등) -> 캐시 저장
    (하드코딩된 정보 대신 파일 내용을 바탕으로 업데이트)
    """
    from core.parsers.hwpx_parser import hwpx_bytes_to_text
    
    # 설정 가져오기
    atchFileId = smpp_database_num["atchFileId"]
    fileSn = smpp_database_num["fileSn"]
    fileKey = smpp_database_num["fileKey"]
    
    # 1. 다운로드
    hwpx_bytes = download_smpp_file(atchFileId, fileSn, fileKey)
    
    # 2. 텍스트 추출
    text = hwpx_bytes_to_text(hwpx_bytes) or ""
    
    # 3. 데이터프레임 생성 (세부품명번호 추출)
    df = extract_item_codes_from_hwpx_bytes(hwpx_bytes)
    
    # 4. 고시 정보 자동 추출 (동적 변수화)
    extracted_info = extract_notice_info_from_text(text)
    
    # 제목은 설정 파일의 기본값 사용하되, 번호/날짜는 추출된 값 우선
    base_info = smpp_database_num.get("notice_info", {}).copy()
    base_info.update(extracted_info)
    
    # 5. 캐시 저장
    saved_path = save_smpp_to_cache(
        df=df,
        atchFileId=atchFileId,
        fileSn=fileSn,
        fileKey=fileKey,
        notice_info=base_info
    )
    
    return {
        "success": True,
        "total_count": len(df),
        "saved_path": saved_path,
        "notice_info": base_info
    }


# -------------------------
# 테스트 실행 (터미널에서만)
# -------------------------
if __name__ == "__main__":
    # smpp_database_num 변수에서 파라미터 가져오기
    ATCH_FILE_ID = smpp_database_num["atchFileId"]
    FILE_SN = smpp_database_num["fileSn"]
    FILE_KEY = smpp_database_num["fileKey"]
    NOTICE_INFO = smpp_database_num["notice_info"]
    
    print("=" * 60)
    print("SMPP 세부품명번호 추출 및 캐시 저장")
    print("=" * 60)
    print(f"\n📌 사용 중인 SMPP 데이터베이스:")
    print(f"   - 파일 ID: {ATCH_FILE_ID}")
    print(f"   - 고시: {NOTICE_INFO['department']} 제 {NOTICE_INFO['notice_number']}호")
    print(f"   - 고시일자: {NOTICE_INFO['notice_date']}")
    
    # 캐시에서 먼저 로드 시도
    print("\n[1] 캐시에서 로드 시도...")
    cached_data = load_smpp_from_cache(ATCH_FILE_ID)
    
    if cached_data:
        metadata = cached_data.get('metadata', {})
        notice_info = metadata.get('notice_info', {})
        
        print(f"✅ 캐시 발견!")
        print(f"\n📋 고시 정보:")
        print(f"   - 발행기관: {notice_info.get('department', '-')}")
        print(f"   - 고시번호: {notice_info.get('department', '-')} 제 {notice_info.get('notice_number', '-')}호")
        print(f"   - 고시일자: {notice_info.get('notice_date', '-')}")
        print(f"   - 제목: {notice_info.get('title', '-')}")
        
        # 캐시 연령 계산
        extracted_at_str = metadata.get('extracted_at')
        if extracted_at_str:
            extracted_at = datetime.fromisoformat(extracted_at_str)
            cache_age = datetime.now() - extracted_at
            expiry_days = metadata.get('cache_expiry_days', 80)
            remaining_days = expiry_days - cache_age.days
            
            print(f"\n⏱️  캐시 정보:")
            print(f"   - 추출일시: {extracted_at.strftime('%Y.%m.%d %H:%M')}")
            print(f"   - 캐시 연령: {cache_age.days}일 경과")
            print(f"   - 만료까지: {remaining_days}일 남음 (만료 기준: {expiry_days}일)")
        
        print(f"\n   총 {metadata.get('total_count', 0)}개 품목")
        print("\n세부품명번호 목록 (샘플):")
        for code in cached_data['item_codes'][:10]:  # 처음 10개만 표시
            print(f"  - {code}")
        if len(cached_data['item_codes']) > 10:
            print(f"  ... 외 {len(cached_data['item_codes']) - 10}개")
    else:
        print("❌ 캐시 없음. SMPP에서 다운로드합니다...")
        
        # SMPP에서 다운로드 및 추출
        print("\n[2] SMPP 파일 다운로드 및 파싱 중...")
        df = get_smpp_item_codes_df(
            atchFileId=ATCH_FILE_ID,
            fileSn=FILE_SN,
            fileKey=FILE_KEY,
            use_notice_parser=False,  # True로 바꾸면 기존 notice_parser 기반 사용
        )

        if df.empty:
            print("⚠️ 추출 결과 없음(세부품명번호를 찾지 못함)")
        else:
            print(f"✅ {len(df)}개 세부품명번호 추출 완료")
            print("\n추출된 데이터 (샘플):")
            print(df.head(10).to_string(index=False))
            if len(df) > 10:
                print(f"... 외 {len(df) - 10}개")
            
            # 캐시에 저장 (고시 정보 포함)
            print("\n[3] JSON 캐시 저장 중...")
            
            saved_path = save_smpp_to_cache(
                df=df,
                atchFileId=ATCH_FILE_ID,
                fileSn=FILE_SN,
                fileKey=FILE_KEY,
                notice_info=NOTICE_INFO  # smpp_database_num에서 가져온 고시 정보 사용
            )
            print(f"✅ 저장 완료: {saved_path}")
            
            # 저장된 파일 확인
            print("\n[4] 저장된 JSON 메타데이터 확인:")
            with open(saved_path, "r", encoding="utf-8") as f:
                saved_content = json.load(f)
            
            metadata = saved_content.get('metadata', {})
            notice = metadata.get('notice_info', {})
            
            print(f"   - 발행기관: {notice.get('department', '-')}")
            print(f"   - 고시: {notice.get('department', '-')} 제 {notice.get('notice_number', '-')}호 ({notice.get('notice_date', '-')})")
            print(f"   - 추출일시: {metadata.get('extracted_at', '-')}")
            print(f"   - 캐시 만료: {metadata.get('cache_expiry_days', 80)}일 후")
            print(f"   - 총 품목수: {metadata.get('total_count', 0)}개")
    
    print("\n" + "=" * 60)
