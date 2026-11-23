from crewai import Agent

def build_agents():
    plan_parser = Agent(
        role="PlanParserAgent",
        goal="구매계획안 텍스트에서 PlanSchema 필드를 추출한다.",
        backstory="구매계획안에서 필요한 값만 정확히 뽑는다. 추측하지 않는다.",
        allow_delegation=False,
        verbose=False,
    )

    rule_engine = Agent(
        role="RuleEngineAgent",
        goal="PlanSchema를 규칙에 따라 공고문 수정값(Notice Patch)으로 변환한다.",
        backstory="결정은 규칙 기반으로 수행한다.",
        allow_delegation=False,
        verbose=False,
    )

    qa = Agent(
        role="QAComplianceAgent",
        goal="출력 patch가 규칙을 만족하는지 점검하고 누락을 찾는다.",
        backstory="체크리스트 기반으로 오류를 찾아낸다.",
        allow_delegation=False,
        verbose=False,
    )

    return plan_parser, rule_engine, qa

