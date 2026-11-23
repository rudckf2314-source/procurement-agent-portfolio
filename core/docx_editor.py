from docx import Document
from docx.shared import RGBColor
import os
import io

def generate_docx_from_template(template_path, replacements):
    """
    DOCX 템플릿 파일에서 변수를 교체하여 새로운 DOCX 파일을 생성합니다.
    """
    try:
        if not os.path.exists(template_path):
             raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

        # 템플릿 로드
        doc = Document(template_path)

        # 모든 단락에서 텍스트 교체
        for para in doc.paragraphs:
            _replace_in_paragraph(para, replacements)

        # 테이블에서도 교체
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        _replace_in_paragraph(para, replacements)

        # 메모리 버퍼에 저장 (파일 생성 X)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer.getvalue()

    except Exception as e:
        raise Exception(f"DOCX 파일 생성 실패: {str(e)}")

def _replace_in_paragraph(para, replacements):
    """
    단락 내의 텍스트를 치환하되, 가능한 한 원본 서식(Run)을 유지하도록 노력합니다.
    """
    if not para.text or not any(f"{{{key}}}" in para.text for key in replacements):
        return

    # 1. Run 단위 치환 시도 (서식 유지됨)
    # 변수가 하나의 Run 안에 온전히 들어있을 때 동작
    replaced_count = 0
    for run in para.runs:
        for key, value in replacements.items():
            placeholder = f"{{{key}}}"
            if placeholder in run.text:
                run.text = run.text.replace(placeholder, str(value) if value is not None else "")
                # 요청사항: 입력값 파란색 설정
                run.font.color.rgb = RGBColor(0, 0, 255)
                replaced_count += 1
    
    # 2. Run 단위로 처리가 안 되었다면 (변수가 여러 Run에 걸쳐있음)
    # 어쩔 수 없이 단락 전체 텍스트를 교체 (서식 일부 소실 가능성 있음)
    # 이미 처리된 변수 외에 아직 남아있는 변수가 있는지 확인
    still_has_placeholder = any(f"{{{key}}}" in para.text for key in replacements)
    
    if still_has_placeholder:
        # 서식 보존을 위한 시도: 첫 번째 Run의 스타일을 저장
        style_backup = {}
        if para.runs:
            first_run = para.runs[0]
            style_backup['font_name'] = first_run.font.name
            style_backup['font_size'] = first_run.font.size
            style_backup['bold'] = first_run.font.bold
            style_backup['italic'] = first_run.font.italic
            style_backup['underline'] = first_run.font.underline
            # 색상은 강제로 파란색으로 변경할 것이므로 백업 불필요하지만, 혹시 몰라 구조 유지

        for key, value in replacements.items():
            placeholder = f"{{{key}}}"
            if placeholder in para.text:
                para.text = para.text.replace(placeholder, str(value) if value is not None else "")
        
        # 저장된 스타일 복구 (단락 전체가 하나의 Run으로 재생성됨)
        if para.runs:
            new_run = para.runs[0]
            if style_backup:
                if style_backup.get('font_name'): new_run.font.name = style_backup['font_name']
                if style_backup.get('font_size'): new_run.font.size = style_backup['font_size']
                if style_backup.get('bold') is not None: new_run.font.bold = style_backup['bold']
                if style_backup.get('italic') is not None: new_run.font.italic = style_backup['italic']
                if style_backup.get('underline') is not None: new_run.font.underline = style_backup['underline']
            
            # 요청사항: 입력값 파란색 설정 (재생성된 Run에도 적용)
            new_run.font.color.rgb = RGBColor(0, 0, 255)
