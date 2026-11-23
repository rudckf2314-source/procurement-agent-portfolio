import os
import requests
from urllib.parse import unquote
import xml.etree.ElementTree as ET


def fetch_item_name_from_api(item_code: str) -> str:
    """
    [1단계 API 검증]
    세부품명번호(10자리)가 조달청 물품목록정보(공공데이터) 기준으로 존재하는지 조회하고,
    존재하면 공식 한글 품명(dtilPrdctClsfcNoNm)을 반환.
    (없으면 "" 반환)
    """

    api_key = os.getenv("G2BNoticeAPI")  # ver7에서 이미 쓰는 환경변수명 유지
    if not api_key:
        return ""  # 키 없음

    # data.go.kr 키는 URL 인코딩된 키/디코딩 키가 섞일 수 있어서 unquote 처리
    decoded_key = unquote(api_key)

    # ✅ 승훈님이 Swagger에서 성공한 엔드포인트로 변경
    url = "https://apis.data.go.kr/1230000/ao/ThngListInfoService/getPrdctClsfcNoUnit10Info"

    params = {
        "serviceKey": decoded_key,
        "pageNo": "1",
        "numOfRows": "1",
        # ✅ 이 API는 clsfNo가 아니라 아래 파라미터로 조회함
        "dtilPrdctClsfcNoBgnNo": item_code,
        "dtilPrdctClsfcNoEndNo": item_code,
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()

        # 응답이 XML(text/xml) 이므로 XML 파싱
        root = ET.fromstring(response.text)

        # resultCode 확인
        result_code = root.findtext("./header/resultCode", default="")
        if result_code != "00":
            # 정상(00)이 아니면 실패로 처리
            return ""

        # item이 없으면 존재하지 않는 것
        item = root.find("./body/items/item")
        if item is None:
            return ""

        # ✅ 공식 한글 품명 필드
        name_kr = item.findtext("dtilPrdctClsfcNoNm", default="").strip()
        return name_kr

    except Exception as e:
        print(f"[API Exception] {str(e)}")
        return ""
