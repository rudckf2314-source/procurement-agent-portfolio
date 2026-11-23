"""
조달 입찰판정 엔진 - 메인 통합 모듈
모든 레이어를 통합하여 판정 실행
"""

from typing import Optional
from .schemas import DecisionInput, DecisionOutput
from .engine import DecisionEngine
from .explain import ExplanationGenerator
from .qualifications import QualificationBuilder
from .rules import create_current_ruleset


class ProcurementDecisionEngine:
    """
    조달 입찰판정 엔진 (통합)
    
    사용법:
        engine = ProcurementDecisionEngine()
        result = engine.decide(decision_input)
    """
    
    def __init__(self):
        self.ruleset = create_current_ruleset()
        self.decision_engine = DecisionEngine(self.ruleset)
        self.explanation_generator = ExplanationGenerator()
        self.qualification_builder = QualificationBuilder()
    
    def decide(self, decision_input: DecisionInput) -> DecisionOutput:
        """
        입찰판정 실행
        
        Args:
            decision_input: 정규화된 입력 데이터
        
        Returns:
            DecisionOutput: 판정 결과 + 근거 + 법규 + 버전
        """
        # 1. 판정 실행
        decision_result = self.decision_engine.decide(decision_input)
        
        # 2. 자격요건 생성
        qualifications = self.qualification_builder.build_qualifications(decision_input)
        
        # 3. 설명 생성
        rationale = self.explanation_generator.generate_rationale(
            award_method=decision_result["award_method"],
            bidding_method=decision_result["bidding_method"],
            triggered_rules=decision_result["triggered_rules"],
            decision_input=decision_input
        )
        
        # 4. 근거 스니펫 추출
        evidence_snippets = self.explanation_generator.extract_evidence_snippets(decision_input)
        
        # 5. 법적 근거 수집
        legal_basis = []
        for qual in qualifications:
            legal_basis.extend(qual.legal_basis)
        
        # 6. DecisionOutput 생성
        return DecisionOutput(
            case_id=decision_input.case_id,
            source=decision_input.source,
            bidding_method=decision_result["bidding_method"],
            award_method=decision_result["award_method"],
            required_qualifications=qualifications,
            ruleset_version_id=self.ruleset.version_id,
            triggered_rules=decision_result["triggered_rules"],
            rationale=rationale,
            evidence_snippets=evidence_snippets,
            legal_basis=legal_basis,
            confidence=decision_result["confidence"],
            warnings=decision_result["warnings"]
        )
    
    def get_version_info(self) -> dict:
        """엔진 버전 정보"""
        return {
            "engine_version": "1.0.0",
            "ruleset": self.ruleset.get_version_info()
        }
