
from typing import List, Optional

# 주요 중소기업자간 경쟁제품 키워드 및 품명군 (2025 고시 기준 반영 예시)
# 출처: 중소벤처기업부 고시 및 공공구매종합정보망(SMPP) 주요 품목
DIRECT_PRODUCTION_KEYWORDS = [
    "인쇄", "경인쇄", "옵셋", "간행물", "소식지", "달력",
    "가구", "책상", "의자", "캐비닛", "사물함", "파티션", "싱크대", "침대",
    "전산장비", "컴퓨터", "서버", "디스크어레이", "스토리지",
    "소프트웨어", "SW개발", "정보시스템", "홈페이지", "전광판", "안내판",
    "방송장비", "영상감시", "CCTV", "카메라",
    "가방", "피복", "근무복", "조끼", "장갑",
    "아스콘", "콘크리트", "레미콘", "블럭",
    "울타리", "펜스", "난간", "체육시설", "운동기구",
    "발전기", "변압기", "배전반", "제어반",
    "공기조화기", "항온항습기",
    "책자", "리플렛", "포스터", "판촉물"
]


# 중소기업자간 경쟁제품 세부품명번호 앞자리(4자리) 매핑
# 출처: 중소벤처기업부 고시 (가구, 인쇄, 전산, 방송, 아스콘 등)
COMPETITION_PRODUCT_PREFIXES = {
    "5610": "가구류 (책상, 의자, 침대 등)",
    "5611": "가구류 (침대, 파티션 등)",
    "5510": "인쇄물 (상업인쇄, 소식지, 정기간행물 등)",
    "4321": "컴퓨터 및 주변기기 (데스크탑, 서버, 스토리지)",
    "4322": "방송장비 (영상감시장치, 구내방송장치)",
    "4617": "보안기기 (CCTV 카메라)",
    "3910": "조명기구 (LED조명 등)",
    "3010": "구조물 (콘크리트블럭, 레미콘)",
    "3011": "토목자재 (아스콘, 철근콘크리트관)",
    "3012": "도로포장재",
    "2611": "전지 (배터리, ESS)",
    "2612": "전선/케이블",
    "4412": "사무용품 (파일, 바인더)",
    "3413": "안전장비 (보호복, 장갑)",
    "5310": "피복 (근무복, 점퍼, 조끼)",
    "5311": "신발 (특수화)",
    "3912": "배전반 및 제어반",
    "4010": "냉동공조 (항온항습기, 공기조화기)",
    "3911": "발전기",
}

def check_direct_production_obligation(title: str, item_codes: Optional[List[str]]) -> bool:
    """
    직접생산확인증명서 제출 의무 여부를 판단합니다.
    1. SMPP 데이터베이스 체크 (최우선)
    2. 세부품명번호(10자리)의 앞 4자리(GS1 Class)를 확인하여 경쟁제품군인지 판단
    3. 제목 키워드 보조 확인
    """
    from core.smpp_download import check_item_in_smpp_database
    
    # 1. SMPP 데이터베이스 체크 (최우선)
    if item_codes:
        for code in item_codes:
            # 특수문자 제거
            c = code.strip().replace("-", "")
            if len(c) == 10:  # 10자리 세부품명번호만 확인
                # SMPP 데이터베이스에서 확인
                if check_item_in_smpp_database(c):
                    print(f"🔍 [SMPP DB] 직접생산확인 대상 식별: 코드 {c} (중기간경쟁제품 제한 목록에 포함)")
                    return True
    
    # 2. 아이템 코드 기반 정밀 검사 (4자리 prefix)
    if item_codes:
        for code in item_codes:
            # 특수문자 제거
            c = code.strip().replace("-", "")
            if len(c) >= 4:
                prefix = c[:4]
                if prefix in COMPETITION_PRODUCT_PREFIXES:
                    print(f"🔍 [Rule] 직접생산확인 대상 식별: 코드 {c} -> {COMPETITION_PRODUCT_PREFIXES[prefix]}")
                    return True
            
    # 3. 키워드 기반 보조 검사
    target_text = title.replace(" ", "")
    for kw in DIRECT_PRODUCTION_KEYWORDS:
        if kw in title or kw in target_text:
            print(f"🔍 [Rule] 직접생산확인 대상 식별: 키워드 '{kw}'")
            return True
            
    return False

def get_direct_production_rationale(is_required: bool) -> str:
    if is_required:
        return "중소기업자간 경쟁제품(인쇄, 가구, SW, 전산장비 등)에 해당하므로 직접생산확인증명서 제한 필수"
    return "-"
