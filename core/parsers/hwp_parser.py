import olefile
import zlib
import struct
from io import BytesIO

def get_hwp_text(file_content: bytes) -> str:
    """
    HWP 5.0 파일에서 텍스트를 추출합니다.
    """
    f = BytesIO(file_content)
    try:
        ole = olefile.OleFileIO(f)
    except Exception as e:
        return f"파일을 열 수 없습니다. 올바른 HWP 파일인지 확인해주세요. (오류: {str(e)})"

    dirs = ole.listdir()
    
    # Check for HWP 5.0 signature
    if ["FileHeader"] not in dirs and ["\x05HwpSummaryInformation"] not in dirs:
        return "지원되지 않는 HWP 형식입니다. HWP 5.0 이상 파일만 지원됩니다."

    text = ""
    section_count = 0
    i = 0
    
    while i < 100:  # 최대 100개 섹션까지만 시도
        stream_path = f"BodyText/Section{i}"
        
        # 스트림 존재 여부 확인
        if not ole.exists(stream_path):
            break
        
        try:
            stream = ole.openstream(stream_path)
            data = stream.read()
            
            if len(data) == 0:
                i += 1
                continue
            
            # Try to decompress (wbits=-15 for raw deflate)
            try:
                unpacked_data = zlib.decompress(data, -15)
            except zlib.error:
                # 압축되지 않은 데이터일 수도 있음
                unpacked_data = data
            
            # Extract text from records
            pos = 0
            size_unpacked = len(unpacked_data)
            
            while pos < size_unpacked:
                if pos + 4 > size_unpacked:
                    break
                
                header = struct.unpack('<I', unpacked_data[pos:pos+4])[0]
                tag = header & 0x3ff
                size = (header >> 20) & 0xfff
                
                pos += 4
                
                if size == 0xfff:
                    if pos + 4 > size_unpacked:
                        break
                    size = struct.unpack('<I', unpacked_data[pos:pos+4])[0]
                    pos += 4
                    
                if pos + size > size_unpacked:
                    break
                    
                # HWPTAG_PARA_TEXT = 67
                if tag == 67:
                    try:
                        chunk = unpacked_data[pos:pos+size].decode('utf-16-le', errors='ignore')
                        # 제어 문자 제거 (NULL, 일부 특수문자 등)
                        chunk = ''.join(char for char in chunk if char.isprintable() or char in '\n\r\t ')
                        text += chunk
                        # 문단 끝에 개행 추가
                        if chunk and not chunk.endswith('\n'):
                            text += "\n"
                    except Exception:
                        pass
                
                pos += size
            
            section_count += 1
                
        except Exception as e:
            # 에러가 발생해도 계속 진행
            text += f"\n[Section {i} 읽기 오류: {type(e).__name__}]\n"
        
        i += 1
    
    if not text.strip():
        return "텍스트를 추출할 수 없습니다. 파일이 비어있거나 암호화되어 있을 수 있습니다."
    
    return text.strip()
