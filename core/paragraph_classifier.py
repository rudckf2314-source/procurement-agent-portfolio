from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, List, Optional
from openai import OpenAI
import os

# 문단 역할 타입 정의
ParagraphRole = Literal[
    "공고명",
    "계약기간", 
    "예산액_vat포함",
    "추정가격_vat제외",
    "경쟁방식",
    "입찰참가자격",
    "세부품명번호",
    "공동계약",
    "제조입찰여부",
    "기타"
]

class ParagraphRoleSchema(BaseModel):
    """문단의 역할(의미) 분류 결과"""
    role: ParagraphRole = Field(
        ..., 
        description="이 문단이 수행하는 역할/의도"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ..., 
        description="분류 확신도"
    )
    key_values: Optional[List[str]] = Field(
        None,
        description="문단에서 추출된 핵심 값 (숫자, 날짜, 코드 등)"
    )
    reasoning: str = Field(
        ...,
        description="왜 이 역할로 분류했는지 한 문장 설명"
    )


def split_into_paragraphs(text: str) -> List[str]:
    """
    텍스트를 의미 단위 문단으로 분해
    
    규칙:
    - 연속된 빈 줄 2개 이상 → 문단 구분
    - 숫자로 시작하는 항목(1. 2. 가. 나.) → 새 문단
    - 표 형식 (|나 탭 구분) → 하나의 문단으로 유지
    """
    # 1단계: 빈 줄 기준 분할
    chunks = text.split('\n\n')
    
    paragraphs = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        
        # 너무 짧은 조각은 이전 문단에 병합 (5글자 미만)
        if len(chunk) < 5 and paragraphs:
            paragraphs[-1] += " " + chunk
        else:
            paragraphs.append(chunk)
    
    # 2단계: 항목 번호 기준 추가 분할
    refined = []
    for para in paragraphs:
        lines = para.split('\n')
        current = []
        
        for line in lines:
            line = line.strip()
            # 새 항목 시작 패턴 (1., 가., -, *)
            if line and (
                line[0].isdigit() and '. ' in line[:4] or
                line.startswith(('- ', '* ', '가.', '나.', '다.'))
            ):
                if current:
                    refined.append('\n'.join(current))
                    current = []
            current.append(line)
        
        if current:
            refined.append('\n'.join(current))
    
    # 최종: 너무 짧은 문단 필터링 (10글자 미만 제외)
    return [p for p in refined if len(p.strip()) >= 10]


def classify_paragraph_role(paragraph: str, client: OpenAI) -> ParagraphRoleSchema:
    """
    문단의 역할(의미)을 LLM으로 분류
    
    문맥 인식 규칙:
    - 특정 키워드가 없어도 "문장의 역할"을 기준으로 판단
    - 다양한 표현 방식을 동일한 역할로 매핑
    """
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    system_msg = """너는 구매계획안 문단의 '역할(의미)'을 분류하는 전문가다.

[핵심 원칙]
단어나 키워드가 아닌, 문장이 수행하는 "역할"을 기준으로 판단한다.
표현, 조사, 구조가 달라도 같은 의도면 같은 역할로 분류한다.

[분류 기준 - 각 문단에 다음 질문을 적용]

1) "이 문단은 사업/구매의 전체 명칭을 설명하는가?"
   → 공고명

2) "이 문단은 언제까지 계약·납품·수행되는지를 설명하는가?"
   → 계약기간

3) "이 문단은 총 금액(부가세 포함)을 설명하는가?"
   → 예산액_vat포함

4) "이 문단은 부가세를 제외한 금액을 설명하는가?"
   → 추정가격_vat제외

5) "이 문단은 경쟁 방식이나 계약 방식을 설명하는가?"
   예: 일반경쟁, 제한경쟁, 수의계약, 적격심사, 소액수의 등
   → 경쟁방식

6) "이 문단은 업체의 자격, 규모, 제한사항을 설명하는가?"
   예: 중소기업, 소기업, 지역제한 등
   → 입찰참가자격

7) "이 문단은 나라장터 등록 코드/번호를 설명하는가?"
   예: 세부품명번호, 물품식별번호, G2B 분류번호
   → 세부품명번호

8) "이 문단은 여러 업체가 함께 참여 가능한지를 설명하는가?"
   예: 공동계약, 컨소시엄
   → 공동계약

9) "이 문단은 제조입찰 여부를 설명하는가?"
   → 제조입찰여부

10) 위 어느 것에도 해당하지 않음
    → 기타

[출력 규칙]
- role: 위 분류 결과
- confidence: 확신도 (high/medium/low)
- key_values: 숫자, 날짜, 코드 등 추출된 값 리스트
- reasoning: 한 문장으로 분류 근거 설명

예시:
문단: "소요예산은 총 39,996,000원(부가가치세 포함)이며"
→ role: "예산액_vat포함", confidence: "high", 
   key_values: ["39996000"], 
   reasoning: "총 금액과 부가세 포함 명시"
"""

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"문단:\n{paragraph}"}
            ],
            response_format=ParagraphRoleSchema,
            temperature=0,
            top_p=0.1,
        )
        
        return completion.choices[0].message.parsed
    
    except Exception as e:
        # 실패 시 기타로 분류
        return ParagraphRoleSchema(
            role="기타",
            confidence="low",
            key_values=None,
            reasoning=f"분류 실패: {str(e)}"
        )


def classify_all_paragraphs(paragraphs: List[str], client: OpenAI) -> List[dict]:
    """
    모든 문단을 분류하고 결과 반환
    
    Returns:
        [{"paragraph": str, "role": str, "confidence": str, "key_values": List, "reasoning": str}, ...]
    """
    results = []
    
    for i, para in enumerate(paragraphs):
        print(f"🔍 문단 {i+1}/{len(paragraphs)} 분류 중...")
        classification = classify_paragraph_role(para, client)
        
        results.append({
            "paragraph": para,
            "role": classification.role,
            "confidence": classification.confidence,
            "key_values": classification.key_values or [],
            "reasoning": classification.reasoning
        })
        
        # 디버그 출력
        if classification.role != "기타":
            print(f"   ✓ [{classification.role}] (확신도: {classification.confidence})")
            print(f"     → {classification.reasoning}")
    
    return results
