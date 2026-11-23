"""
PDF 생성 헬퍼 함수
Word 문서를 PDF로 변환하는 유틸리티
"""
import os
import tempfile
from typing import Optional

def convert_docx_to_pdf(docx_bytes: bytes) -> Optional[bytes]:
    """
    Word 문서(bytes)를 PDF로 변환
    
    Args:
        docx_bytes: Word 문서의 바이트 데이터
        
    Returns:
        PDF 파일의 바이트 데이터 또는 None (실패 시)
    """
    try:
        # Windows에서 MS Word 사용하여 변환
        import platform
        
        if platform.system() == "Windows":
            # docx2pdf 사용 (MS Word 필요)
            from docx2pdf import convert
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as docx_temp:
                docx_path = docx_temp.name
                docx_temp.write(docx_bytes)
            
            # PDF 경로 설정
            pdf_path = docx_path.replace(".docx", ".pdf")
            
            try:
                # Word -> PDF 변환
                convert(docx_path, pdf_path)
                
                # PDF 읽기
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_bytes = pdf_file.read()
                
                return pdf_bytes
                
            finally:
                # 임시 파일 정리
                if os.path.exists(docx_path):
                    os.remove(docx_path)
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
        
        else:
            # Linux/Mac: LibreOffice 사용
            print("⚠️  Linux/Mac에서는 LibreOffice가 설치되어 있어야 합니다.")
            
            import subprocess
            
            # 임시 디렉토리 생성
            with tempfile.TemporaryDirectory() as tmpdir:
                docx_path = os.path.join(tmpdir, "document.docx")
                pdf_path = os.path.join(tmpdir, "document.pdf")
                
                # Word 파일 저장
                with open(docx_path, 'wb') as f:
                    f.write(docx_bytes)
                
                # LibreOffice로 변환
                result = subprocess.run([
                    'libreoffice',
                    '--headless',
                    '--convert-to', 'pdf',
                    '--outdir', tmpdir,
                    docx_path
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    print(f"❌ LibreOffice 변환 실패: {result.stderr}")
                    return None
                
                # PDF 읽기
                if os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        return f.read()
                else:
                    print("❌ PDF 파일이 생성되지 않았습니다.")
                    return None
                    
    except ImportError as e:
        print(f"❌ 필요한 라이브러리가 설치되지 않았습니다: {e}")
        print("   Windows: pip install docx2pdf")
        print("   Linux/Mac: sudo apt-get install libreoffice")
        return None
        
    except Exception as e:
        print(f"❌ PDF 변환 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return None
