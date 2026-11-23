# core/smpp_notice_parser.py
import re
from typing import List, Dict, Tuple


def _clean_text(text: str) -> str:
    t = text or ""
    # 공백 정리
    t = re.sub(r"[ \t]+", " ", t)
    # 이상한 제어문자 제거(필요 시 확장)
    t = t.replace("\x00", " ")
    return t


def _is_plausible_item_name(name: str) -> bool:
    """
    품명 후보 필터:
    - 너무 짧거나 너무 길면 제외
    - 숫자만/기호만은 제외
    """
    if not name:
        return False
    name = name.strip()
    if len(name) < 2 or len(name) > 80:
        return False
    if re.fullmatch(r"[0-9\-\(\)\[\]\s]+", name):
        return False
    # 한글/영문이 거의 없는 경우 제외
    if not re.search(r"[가-힣A-Za-z]", name):
        return False
    return True


def extract_item_pairs_from_notice_text(text: str) -> List[Dict[str, str]]:
    """
    SMPP 고시(보통 표 기반) 텍스트에서
    - 세부품명번호(10자리)
    - 품명
    페어를 최대한 뽑아냅니다.

    반환 형식:
      [{"세부품명번호":"4111319901", "품명":"대기오염측정기"}, ...]
    """
    t = _clean_text(text)

    # 1) 정밀 추출: "세부품명번호 10자리 + 품명"이 가까이 붙어 있는 패턴
    #    예: 4111319901 대기오염측정기
    #    예: 4111319901 | 대기오염측정기
    precise_pattern = re.compile(
        r"(?P<code>\b\d{10}\b)\s*[:\|\-\–]?\s*(?P<name>[가-힣A-Za-z0-9][^,\n\r]{1,80})"
    )

    pairs: List[Tuple[str, str]] = []
    for m in precise_pattern.finditer(t):
        code = m.group("code")
        name = m.group("name").strip()

        # 끝에 불필요한 꼬리 제거(표 줄바꿈이 깨지면 다음 열이 붙는 경우가 있음)
        name = re.split(r"(?:\b\d{10}\b|세부품명번호|품명|규격|단위|비고)\b", name)[0].strip()
        name = name.strip(" -|:：·")

        if _is_plausible_item_name(name):
            pairs.append((code, name))

    # 2) 보강 추출: 10자리 코드만 먼저 수집하고, "근처" 텍스트에서 품명을 추정
    #    - 표가 깨져서 "코드"와 "품명"이 줄바꿈으로 분리될 때 대응
    codes = re.findall(r"\b\d{10}\b", t)

    # 주변 60자 window에서 품명 후보를 잡아 페어로 만들기
    # (중복/오염을 줄이기 위해 이미 precise에서 잡힌 코드는 제외)
    already = set(pairs)
    for code in codes:
        if any(code == c for c, _ in pairs):
            continue

        idx = t.find(code)
        if idx < 0:
            continue
        window = t[idx: idx + 120]  # 코드 뒤 120자

        # 코드 뒤에 나오는 첫 "문자열 덩어리"를 품명 후보로
        m2 = re.search(rf"{code}\s*[:\|\-\–]?\s*([가-힣A-Za-z][^,\n\r]{{1,80}})", window)
        if not m2:
            continue
        name = m2.group(1).strip()
        name = re.split(r"(?:\b\d{10}\b|세부품명번호|품명|규격|단위|비고)\b", name)[0].strip()
        name = name.strip(" -|:：·")

        if _is_plausible_item_name(name):
            already.add((code, name))
            pairs.append((code, name))

    # 3) 정리: 같은 코드가 여러 번 나오면 가장 "짧고 깔끔한" 품명 우선
    best = {}
    for code, name in pairs:
        # 괄호 뒤 설명이 붙은 것보다 깔끔한 걸 우선
        score = (len(name), 0 if "(" not in name else 5)
        if code not in best or score < best[code][0]:
            best[code] = (score, name)

    out = [{"세부품명번호": code, "품명": name} for code, (_, name) in best.items()]

    # 4) 안정성: 코드순 정렬
    out.sort(key=lambda x: x["세부품명번호"])
    return out


# --- 간단 테스트 ---
if __name__ == "__main__":
    sample = """
    중소기업자간 경쟁제품 목록
    4111319901 대기오염측정기
    4111309901 수질측정기
    세부품명번호: 4111222200 | 공기청정기
    """
    items = extract_item_pairs_from_notice_text(sample)
    for it in items:
        print(it)

