# core/smpp_api.py
import os
import requests
from urllib.parse import unquote
import xml.etree.ElementTree as ET

SMPP_PF_URL = "http://apis.data.go.kr/B550598/smppPfCertInfo/getPfCertInfo"  # 성능인증확인서 조회

def fetch_pf_cert_info(bsnm_no: str, page_no: int = 1, num_rows: int = 10):
    """
    성능인증확인서 정보 조회 (예시)
    return: (items, status, error)
      - status: "OK" | "NOT_FOUND" | "API_ERROR"
    """
    api_key = os.getenv("SMPP_API_KEY")  # .env에 저장
    if not api_key:
        return ([], "API_ERROR", "Missing env var: SMPP_API_KEY")

    decoded_key = unquote(api_key)

    params = {
        "serviceKey": decoded_key,
        "pageNo": str(page_no),
        "numOfRows": str(num_rows),
        "bsnmNo": str(bsnm_no),
    }

    try:
        r = requests.get(SMPP_PF_URL, params=params, timeout=10)
        r.raise_for_status()

        root = ET.fromstring(r.text)

        # 결과 코드/메시지(태그명은 API마다 약간 다를 수 있어요)
        result_code = root.findtext(".//resultCode")
        result_msg = root.findtext(".//resultMsg")

        if result_code not in (None, "00"):
            return ([], "API_ERROR", f"{result_code} / {result_msg}")

        items = []
        for it in root.findall(".//item"):
            # 필요 필드만 뽑기(필드명은 실제 응답에 맞춰 조정)
            items.append({child.tag: (child.text or "") for child in list(it)})

        if not items:
            return ([], "NOT_FOUND", None)

        return (items, "OK", None)

    except Exception as e:
        return ([], "API_ERROR", str(e))
