from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, date


class PlanSchema(BaseModel):
    notice_title: str = Field(..., description="공고명/물품명")
    contract_period_text: str = Field(..., description="계약기간 또는 납품기한 텍스트")
    budget_vat_included_krw: int = Field(..., ge=0, description="예산액(부가세 포함일 수 있음)")
    estimated_price_ex_vat_krw: Optional[int] = Field(
        None, ge=0, description="추정가격(부가세 제외). 없으면 budget_vat_included_krw/1.1로 추정 가능"
    )

    item_codes: Optional[List[str]] = Field(
        None, description="세부품명번호(10자리) 리스트. 식별된 번호가 여러 개면 모두 포함."
    )
    industry_codes: Optional[List[str]] = Field(
        None, description="업종코드(4자리) 리스트 (예: 정보통신공사업 0036 등)"
    )
    industry_names_text: Optional[List[str]] = Field(
        None, description="업종명 리스트 (코드가 없는 경우 텍스트로 추출. 예: '소프트웨어사업자', '정보통신공사업', '엔지니어링활동주체')"
    )
    is_manufacture_bid: Optional[bool] = Field(
        None, description="물품 제조입찰 여부(별표 분기에서 10억 이상 제조입찰 판단에 사용)"
    )

    contract_method_suggestion: Optional[str] = Field(
        None, description="구매계획안에 명시된 계약방법/낙찰자결정방법 (예: 적격심사, 수의계약, 일반경쟁, 제한경쟁, 소액수의 등)"
    )
    
    # Classification Fields
    detected_phrases: Optional[List[str]] = Field(None, description="탐지된 핵심 키워드/문구 리스트")
    bidding_method: Optional[Literal["general_competition", "limited_competition", "private_contract", "unknown"]] = Field(
        None, description="입찰방법 (일반경쟁/제한경쟁/수의계약/미상)"
    )
    award_method: Optional[Literal["eligible_review", "small_quote", "unknown"]] = Field(
        None, description="낙찰자선정방법 (적격심사/소액수의/미상)"
    )
    rationale: Optional[str] = Field(None, description="결론에 대한 한 문장 근거")
    evidence_snippets: Optional[List[str]] = Field(
        None, description="근거 원문 발췌 1~3개. 반드시 '금액' 부분이 드러나는 부분을 포함."
    )



    consortium_enabled: Optional[bool] = Field(None, description="공동계약 유무")
    consortium_partners: Optional[List[str]] = Field(None, description="공동계약 업체명 목록")

    region_limit_enabled: Optional[bool] = Field(None, description="지역제한 유무(1차는 참고값만 저장)")
    region_scope_text: Optional[str] = Field(None, description="지역제한 범위 텍스트")

    base_open_datetime: Optional[str] = Field(
        None,
        description="개찰일시 기준값(없으면 앱에서 사용자가 선택). ISO 문자열 예: 2025-12-16T11:00:00"
    )


NoticeType = Literal["eligible_review", "small_quote"]


class NoticePatch(BaseModel):
    notice_number: Optional[str] = None  # 한국환경공단 입찰공고번호
    notice_type: NoticeType

    notice_title: str
    contract_period_text: str
    budget_vat_included_krw: int
    estimated_price_ex_vat_krw: int

    submission_start_dt: datetime  # 제출 시작일
    submission_period_text: str  # 제출기간 (예: "2025-12-17 ~ 2025-12-24")
    open_datetime_dt: datetime  # 개찰일시 (제출시작일+8일+1h)

    competition_method_text: str

    appendix_text: Optional[str] = None  # 적격심사일 때 별표1/2/3

    sme_limit_text: Literal["소기업", "중소기업", "제한없음"]

    item_code_text: Optional[str] = None
    item_name_api_text: Optional[str] = Field(None, description="API로 조회된 세부품명 (한글)")
    industry_code_text: Optional[str] = Field(None, description="추출된 업종코드 및 명칭")
    industry_name_text: Optional[str] = Field(None, description="업종명만 나열 (예: 정보통신공사업, 전기공사업)")
    
    qualification_text: Optional[str] = Field(None, description="입찰참가자격 요약문 (전체)")
    qualification_item_text: Optional[str] = Field(None, description="입찰참가자격 - 세부품명 부분")
    qualification_industry_text: Optional[str] = Field(None, description="입찰참가자격 - 업종코드 부분")

    consortium_text: str  # 통합 텍스트 (B)
    consortium_status_text: Optional[str] = Field(None, description="공동계약 여부 요약 (A)")

    consortium_deadline_dt: Optional[datetime] = None # 공동수급협정서 제출기한 (개찰일 전일 18:00)

    has_direct_production: bool = False # 직접생산확인증명서 필요 여부
    smpp_confirm_text: str = Field(default="", description="직접생산확인 안내 문구 (has_direct_production이 True일 때만 값 포함)")
    region_limit: Optional[str] = None # 지역제한 텍스트 (예: "경기도")
    region_limit_text: str = Field(default="", description="지역제한 공고문 표시용 텍스트 (예: '부산 제한입니다' 또는 빈 문자열)")

    manager_info: str = Field(
        default="환경처 조달부(☎02-2110-0000, 담당 : 홍길동 대리)",
        description="담당자 정보 - 포맷: ##처 ##부(☎000-000-0000, 담당 : ### ##)"
    )

    posted_date: date


