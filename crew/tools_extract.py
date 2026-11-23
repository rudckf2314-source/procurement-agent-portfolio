try:
    from crewai_tools import tool
except ImportError:
    try:
        from crewai.tools import tool
    except ImportError:
        from crewai import tool

from core.openai_client import extract_plan_with_context
from core.schemas import PlanSchema
import json

@tool("Procurement Plan Extraction Tool")
def extract_tool(text: str):
    """
    구매계획안 텍스트를 분석하여 예산, 공고명, 계약기간 등을 구조화된 데이터로 추출합니다. 
    입력으로 구매계획안 원문 텍스트를 받습니다.
    """
    return _extraction_logic(text)

def _extraction_logic(text: str) -> str:
    """
    구매계획안 추출 로직 (내부 함수)
    """
    try:
        # 기존 문맥 기반(2단계) 추출 엔진 사용
        plan: PlanSchema = extract_plan_with_context(text)
        
        # Pydantic 모델을 JSON 문자열로 변환하여 에이전트에게 전달
        return plan.model_dump_json()
    except Exception as e:
        return f"추출 실패: {str(e)}"
