from __future__ import annotations

def estimate_ex_vat(budget_vat_included_krw: int) -> int:
    # 예산이 부가세 포함이라고 가정할 때의 보수적 추정
    # 필요한 경우 UI에서 “부가세 포함/제외” 토글을 추가해서 정확도 올릴 수 있음
    return int(round(budget_vat_included_krw / 1.1))

