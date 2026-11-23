"""
CrewAI Tools: 외부 API 연동 도구
Analyst Agent가 실시간으로 조달청 API를 호출하여 데이터를 검증할 수 있도록 함
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from core.api_client import fetch_item_name_from_api
from core.industry_mapper import get_industry_name_by_code
from core.item_checker import verify_industry_with_api
import json
import re


class ItemCodeInput(BaseModel):
    """Input for Item Validation Tool"""
    item_code: str = Field(..., description="세부품명번호 10자리 (예: 5510159901)")


class ItemValidationTool(BaseTool):
    name: str = "Item Validation Tool"
    description: str = "세부품명번호(10자리)가 조달청에 유효하게 등록된 품목인지 확인합니다."
    args_schema: Type[BaseModel] = ItemCodeInput

    def _run(self, item_code: str) -> str:
        """실행 로직"""
        # 숫자만 추출
        clean_code = re.sub(r'[^0-9]', '', item_code)
        
        if len(clean_code) != 10:
            return json.dumps({
                "valid": False,
                "error": "품명코드는 10자리 숫자여야 합니다.",
                "input": item_code
            }, ensure_ascii=False)
        
        # API 호출
        item_name = fetch_item_name_from_api(clean_code)
        
        if item_name:
            return json.dumps({
                "valid": True,
                "item_code": clean_code,
                "item_name": item_name,
                "message": "조달청에 등록된 유효한 품명입니다."
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "valid": False,
                "item_code": clean_code,
                "message": "조달청 품명목록에서 찾을 수 없습니다."
            }, ensure_ascii=False)


class IndustryCodeInput(BaseModel):
    """Input for Industry Validation Tool"""
    industry_code: str = Field(..., description="업종코드 4자리 (예: 7468)")


class IndustryValidationTool(BaseTool):
    name: str = "Industry Validation Tool"
    description: str = "업종코드(4자리)가 조달청에 유효하게 등록된 업종인지 확인합니다."
    args_schema: Type[BaseModel] = IndustryCodeInput

    def _run(self, industry_code: str) -> str:
        """실행 로직"""
        # 숫자만 추출
        clean_code = re.sub(r'[^0-9]', '', industry_code)
        
        if len(clean_code) != 4:
            return json.dumps({
                "valid": False,
                "error": "업종코드는 4자리 숫자여야 합니다.",
                "input": industry_code
            }, ensure_ascii=False)
        
        # 1차: 내장 매퍼로 확인
        industry_name = get_industry_name_by_code(clean_code)
        
        if industry_name:
            return json.dumps({
                "valid": True,
                "industry_code": clean_code,
                "industry_name": industry_name,
                "source": "internal_mapper",
                "message": "유효한 업종코드입니다."
            }, ensure_ascii=False)
        
        # 2차: API 호출
        try:
            api_results = verify_industry_with_api(industry_codes_4=[clean_code])
            if api_results and len(api_results) > 0:
                row = api_results[0]
                if row.get("status") == "OK" and row.get("매칭_업종명"):
                    return json.dumps({
                        "valid": True,
                        "industry_code": clean_code,
                        "industry_name": row.get("매칭_업종명"),
                        "source": "api",
                        "message": "유효한 업종코드입니다 (API 검증)."
                    }, ensure_ascii=False)
        except Exception as e:
            pass
        
        return json.dumps({
            "valid": False,
            "industry_code": clean_code,
            "message": "조달청 업종목록에서 찾을 수 없습니다."
        }, ensure_ascii=False)


# Tool 인스턴스 생성
validate_item_code = ItemValidationTool()
validate_industry_code = IndustryValidationTool()
