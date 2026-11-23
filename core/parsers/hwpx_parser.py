# core/parsers/hwpx_parser.py
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List


def _collect_hwpx_section_xml_names(zf: zipfile.ZipFile) -> List[str]:
    """
    HWPX 내부에서 본문 텍스트가 들어있는 section*.xml 파일들을 찾아 정렬해서 반환
    (보통 Contents/section0.xml, Contents/section1.xml ... 형태)
    """
    names = zf.namelist()
    section_xmls = [n for n in names if n.lower().endswith(".xml") and "contents/section" in n.lower()]
    # 예: Contents/section0.xml, Contents/section1.xml ... 순서대로 정렬
    def _section_key(n: str):
        m = re.search(r"section(\d+)\.xml$", n, flags=re.IGNORECASE)
        return int(m.group(1)) if m else 999999
    section_xmls.sort(key=_section_key)
    return section_xmls


def _extract_text_from_xml_bytes(xml_bytes: bytes) -> str:
    """
    section*.xml에서 모든 텍스트를 긁어오는 함수.
    HWPX는 네임스페이스가 다양해서 '모든 element.text'를 안전하게 수집하는 방식 사용.
    """
    try:
        # 일부 파일은 BOM/인코딩 혼합이 있어 decode 없이 ET.fromstring(bytes)로 파싱
        root = ET.fromstring(xml_bytes)
    except Exception:
        # 파싱 실패 시 빈 문자열
        return ""

    texts = []
    # 모든 노드를 순회하며 text 수집
    for elem in root.iter():
        if elem.text:
            t = elem.text.strip()
            if t:
                texts.append(t)

    # 너무 촘촘히 붙는 경우가 있어 공백으로 합친 뒤, 줄바꿈은 나중에 정리
    return " ".join(texts)


def hwpx_bytes_to_text(file_bytes: bytes) -> str:
    """
    HWPX 파일(bytes)을 입력받아 전체 텍스트를 반환.
    """
    if not file_bytes:
        return ""

    # HWPX는 zip 기반이라 PK로 시작하는 경우가 많음
    bio = io.BytesIO(file_bytes)

    try:
        with zipfile.ZipFile(bio, "r") as zf:
            section_xmls = _collect_hwpx_section_xml_names(zf)

            # section*.xml이 안 잡히면 xml 전체에서라도 텍스트 수집(백업)
            if not section_xmls:
                xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                section_xmls = xml_names

            chunks = []
            for name in section_xmls:
                try:
                    xml_bytes = zf.read(name)
                except Exception:
                    continue
                chunk = _extract_text_from_xml_bytes(xml_bytes)
                if chunk:
                    chunks.append(chunk)

            raw = "\n".join(chunks)
    except zipfile.BadZipFile:
        # zip이 아니면 hwpx가 아닌 데이터
        return ""

    # 텍스트 후처리(공백/줄바꿈 정리)
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


# 간단 테스트용 (터미널에서 python -m core.parsers.hwpx_parser 로 실행 가능)
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else ""
    if not path:
        print("Usage: python -m core.parsers.hwpx_parser <file.hwpx>")
        raise SystemExit(1)

    with open(path, "rb") as f:
        b = f.read()
    text = hwpx_bytes_to_text(b)
    print(text[:2000])
    print("\n---\nLEN:", len(text))
