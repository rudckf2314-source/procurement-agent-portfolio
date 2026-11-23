"""
FastAPI REST API Server for Procurement Plan Analyzer
HTML 프론트엔드와 연동을 위한 백엔드 서버
"""
import os
import io
import tempfile
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from core.parsers.pdf_parser import pdf_to_text
from core.parsers.hwp_parser import get_hwp_text
from core.parsers.excel_parser import excel_to_text
from core.parsers.docx_parser import docx_to_text
from core.parsers.text_parser import normalize_text
# from crew.crew_runner import run_pipeline  <-- Moved to lazy import
from chat_api import router as chat_router

# FastAPI 앱 초기화
app = FastAPI(
    title="구매계획안 분석 API",
    description="구매계획안 기반 공고문 수정값 생성 REST API",
    version="1.0.0"
)

app.include_router(chat_router, prefix="/api", tags=["Chatbot"])

# CORS 설정 (HTML 파일에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response 모델
class TextAnalysisRequest(BaseModel):
    text: str
    posting_date: Optional[str] = None
    notice_type: str = "auto"
    notice_number: Optional[str] = None

class AnalysisResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

# 상수


@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "status": "running",
        "service": "구매계획안 분석 API",
        "version": "1.0.0",
        "endpoints": [
            "/api/analyze/text",
            "/api/analyze/file",
            "/api/health"
        ]
    }

@app.get("/api/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/analyze/text")
async def analyze_text(request: TextAnalysisRequest):
    """
    텍스트 기반 구매계획안 분석
    """
    try:
        # 입력 검증
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="텍스트가 비어 있습니다.")
        
        # 텍스트 정규화
        raw_text = normalize_text(request.text)
        
        # 게시일시 파싱
        fallback_open_dt = parse_posting_date(request.posting_date)
        
        # 분석 실행
        print(f"텍스트 분석 시작 (공고 유형: {request.notice_type})")
        from crew.crew_runner import run_pipeline
        result = run_pipeline(
            raw_text=raw_text,
            fallback_open_dt=fallback_open_dt,
            manual_notice_type=request.notice_type,
            use_context=True,
            use_crew=True
        )
        
        # Add notice_number to patch
        if request.notice_number:
            result['patch']['notice_number'] = request.notice_number
        
        print("분석 완료")
        
        return AnalysisResponse(
            success=True,
            data=result
        )
        
    except Exception as e:
        print(f"분석 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"분석 중 오류가 발생했습니다: {str(e)}"
        )

@app.post("/api/analyze/file")
async def analyze_file(
    file: UploadFile = File(...),
    posting_date: Optional[str] = Form(None),
    notice_type: str = Form("auto"),
    notice_number: Optional[str] = Form(None)
):
    """
    파일 업로드 기반 구매계획안 분석
    지원 형식: PDF, HWP, Excel (XLSX, XLSM)
    """
    try:
        # 파일 검증
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일이 없습니다.")
        
        file_ext = file.filename.lower().split('.')[-1]
        allowed_extensions = ['pdf', 'hwp', 'xlsx', 'xlsm', 'docx', 'doc']
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
            )
        
        print(f"파일 업로드: {file.filename} ({file_ext})")
        
        # 파일 읽기
        file_bytes = await file.read()
        
        # 파일 타입별 텍스트 추출
        raw_text = extract_text_from_file(file_bytes, file_ext)
        
        if not raw_text or not raw_text.strip():
            raise HTTPException(
                status_code=400,
                detail="파일에서 텍스트를 추출할 수 없습니다."
            )
        
        print(f"📄 텍스트 추출 완료: {len(raw_text)} 글자")
        
        # 게시일시 파싱
        fallback_open_dt = parse_posting_date(posting_date)
        
        # 분석 실행
        print(f"파일 분석 시작 (공고 유형: {notice_type})")
        from crew.crew_runner import run_pipeline
        result = run_pipeline(
            raw_text=raw_text,
            fallback_open_dt=fallback_open_dt,
            manual_notice_type=notice_type,
            use_context=True,
            use_crew=True
        )
        
        # Add notice_number to patch
        if notice_number:
            result['patch']['notice_number'] = notice_number
        
        print("분석 완료")
        
        return AnalysisResponse(
            success=True,
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"파일 분석 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"파일 분석 중 오류가 발생했습니다: {str(e)}"
        )

@app.post("/api/download/word")
async def download_word(patch_data: dict):
    """
    Word 문서 생성 및 다운로드
    """
    try:
        from core.docx_editor import generate_docx_from_template
        from datetime import datetime
        
        print(" Word 문서 생성 시작...")
        
        # 공고 유형에 따라 템플릿 선택
        notice_type = patch_data.get("notice_type", "")
        
        if "eligible" in notice_type:
            tpl_file = "[공고문] 적격심사 양식_smallpdf.docx"
        else:
            tpl_file = "[공고문] 소액수의 양식_smallpdf.docx"
        
        tpl_path = os.path.join(os.getcwd(), "file_example", tpl_file)
        
        if not os.path.exists(tpl_path):
            raise HTTPException(
                status_code=404,
                detail=f"템플릿 파일을 찾을 수 없습니다: {tpl_file}"
            )
        
        # 데이터 포맷팅
        replacements = patch_data.copy()
        
        # 공고 유형 한글 변환
        type_map = {
            "small_quote": "소액수의",
            "eligible_review": "적격심사",
            "private_contract": "수의계약",
            "limited_competition": "제한경쟁",
            "general_competition": "일반경쟁"
        }
        raw_type = replacements.get("notice_type", "")
        replacements["notice_type"] = type_map.get(raw_type, raw_type)
        
        # 날짜 포맷팅
        for date_field in ["open_datetime_dt", "consortium_deadline_dt"]:
            if date_field in replacements and replacements[date_field]:
                try:
                    if isinstance(replacements[date_field], str):
                        dt_obj = datetime.fromisoformat(replacements[date_field].replace('Z', '+00:00'))
                        replacements[date_field] = dt_obj.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
        
        # 게시일시 한글 포맷
        if "submission_start_dt" in replacements and replacements["submission_start_dt"]:
            try:
                if isinstance(replacements["submission_start_dt"], str):
                    dt_obj = datetime.fromisoformat(replacements["submission_start_dt"].replace('Z', '+00:00'))
                else:
                    dt_obj = replacements["submission_start_dt"]
                    
                if hasattr(dt_obj, 'strftime'):
                    replacements["posted_date_kr"] = dt_obj.strftime("%Y년 %m월 %d일")
            except:
                pass
        
        # 금액 포맷팅
        for key in ["budget_vat_included_krw", "estimated_price_ex_vat_krw"]:
            if key in replacements and isinstance(replacements[key], (int, float)):
                replacements[key] = f"{replacements[key]:,}"
        
        # DOCX 생성
        docx_bytes = generate_docx_from_template(tpl_path, replacements)
        
        # 파일명 결정
        filename = "적격심사_보고서.docx" if "eligible" in notice_type else "소액수의_보고서.docx"
        
        print(f"Word 문서 생성 완료: {filename}")
        
        # 파일 반환 (한글 파일명 인코딩 처리)
        from fastapi.responses import Response
        from urllib.parse import quote
        
        # 한글 파일명을 URL 인코딩
        encoded_filename = quote(filename)
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                # RFC 2231 형식으로 한글 파일명 지원
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except Exception as e:
        print(f"Word 생성 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"Word 문서 생성 중 오류가 발생했습니다: {str(e)}"
        )

@app.post("/api/download/pdf")
async def download_pdf(patch_data: dict):
    """
    PDF 문서 생성 및 다운로드 (Word -> PDF 변환)
    """
    try:
        from core.docx_editor import generate_docx_from_template
        from core.pdf_generator import convert_docx_to_pdf
        from datetime import datetime
        
        print("PDF 문서 생성 시작...")
        
        # 공고 유형에 따라 템플릿 선택
        notice_type = patch_data.get("notice_type", "")
        
        if "eligible" in notice_type:
            tpl_file = "[공고문] 적격심사 양식_smallpdf.docx"
        else:
            tpl_file = "[공고문] 소액수의 양식_smallpdf.docx"
        
        tpl_path = os.path.join(os.getcwd(), "file_example", tpl_file)
        
        if not os.path.exists(tpl_path):
            raise HTTPException(
                status_code=404,
                detail=f"템플릿 파일을 찾을 수 없습니다: {tpl_file}"
            )
        
        # 데이터 포맷팅
        replacements = patch_data.copy()
        
        # 공고 유형 한글 변환
        type_map = {
            "small_quote": "소액수의",
            "eligible_review": "적격심사",
            "private_contract": "수의계약",
            "limited_competition": "제한경쟁",
            "general_competition": "일반경쟁"
        }
        raw_type = replacements.get("notice_type", "")
        replacements["notice_type"] = type_map.get(raw_type, raw_type)
        
        # 날짜 포맷팅
        for date_field in ["open_datetime_dt", "consortium_deadline_dt"]:
            if date_field in replacements and replacements[date_field]:
                try:
                    if isinstance(replacements[date_field], str):
                        dt_obj = datetime.fromisoformat(replacements[date_field].replace('Z', '+00:00'))
                        replacements[date_field] = dt_obj.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
        
        # 게시일시 한글 포맷
        if "submission_start_dt" in replacements and replacements["submission_start_dt"]:
            try:
                if isinstance(replacements["submission_start_dt"], str):
                    dt_obj = datetime.fromisoformat(replacements["submission_start_dt"].replace('Z', '+00:00'))
                else:
                    dt_obj = replacements["submission_start_dt"]
                    
                if hasattr(dt_obj, 'strftime'):
                    replacements["posted_date_kr"] = dt_obj.strftime("%Y년 %m월 %d일")
            except:
                pass
        
        # 금액 포맷팅
        for key in ["budget_vat_included_krw", "estimated_price_ex_vat_krw"]:
            if key in replacements and isinstance(replacements[key], (int, float)):
                replacements[key] = f"{replacements[key]:,}"
        
        print("   Step 1: Word 문서 생성 중...")
        # DOCX 생성
        docx_bytes = generate_docx_from_template(tpl_path, replacements)
        
        print("   Step 2: PDF로 변환 중...")
        # PDF 변환
        pdf_bytes = convert_docx_to_pdf(docx_bytes)
        
        if not pdf_bytes:
            raise HTTPException(
                status_code=500,
                detail="PDF 변환에 실패��습니다. docx2pdf 라이브러리 또는 MS Word가 설치되어 있는지 확인하세요."
            )
        
        # 파일명 결정
        filename = "적격심사_보고서.pdf" if "eligible" in notice_type else "소액수의_보고서.pdf"
        
        print(f"PDF 문서 생성 완료: {filename}")
        
        # 파일 반환 (한글 파일명 인코딩 처리)
        from fastapi.responses import Response
        from urllib.parse import quote
        
        # 한글 파일명을 URL 인코딩
        encoded_filename = quote(filename)
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                # RFC 2231 형식으로 한글 파일명 지원
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
        
    except Exception as e:
        print(f"PDF 생성 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"PDF 문서 생성 중 오류가 발생했습니다: {str(e)}"
        )


@app.get("/api/smpp/status")
async def get_smpp_status():
    """
    SMPP 데이터베이스 상태 조회
    """
    try:
        from core.smpp_download import load_smpp_from_cache, smpp_database_num
        from datetime import datetime
        
        atchFileId = smpp_database_num["atchFileId"]
        cached_data = load_smpp_from_cache(atchFileId)
        
        if cached_data:
            metadata = cached_data.get("metadata", {})
            extracted_at_str = metadata.get("extracted_at")
            
            cache_age_days = 0
            if extracted_at_str:
                extracted_at = datetime.fromisoformat(extracted_at_str)
                cache_age = datetime.now() - extracted_at
                cache_age_days = cache_age.days
            
            return {
                "cache_exists": True,
                "metadata": metadata,
                "cache_age_days": cache_age_days
            }
        else:
            return {
                "cache_exists": False,
                "metadata": None,
                "cache_age_days": None
            }
            
    except Exception as e:
        print(f"SMPP 상태 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"SMPP 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )


@app.post("/api/smpp/refresh")
async def refresh_smpp():
    """
    SMPP 데이터베이스 새로고침 (최신 데이터 다운로드)
    """
    try:

        from core.smpp_download import download_and_update_smpp_cache
        
        print("SMPP 데이터 다운로드 및 자동 분석 시작...")
        
        # 최신 데이터 다운로드 및 자동 분석 (고시번호 동적 추출)
        result = download_and_update_smpp_cache()
        
        total_count = result["total_count"]
        notice_info = result["notice_info"]
        print(f"SMPP 데이터 업데이트 완료: {total_count}개 품목")
        print(f"   (식별된 고시: {notice_info.get('notice_number')}, {notice_info.get('notice_date')})")
        
        return {
            "success": True,
            "total_count": total_count,
            "saved_path": result["saved_path"],
            "message": f"{total_count}개 품목이 업데이트되었습니다. (고시: {notice_info.get('notice_number')})"
        }
        
    except Exception as e:
        print(f"SMPP 새로고침 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=500,
            detail=f"SMPP 데이터 새로고침 중 오류가 발생했습니다: {str(e)}"
        )




# 헬퍼 함수들
def extract_text_from_file(file_bytes: bytes, file_ext: str) -> str:
    """파일에서 텍스트 추출"""
    try:
        if file_ext == 'pdf':
            return pdf_to_text(file_bytes)
        elif file_ext == 'hwp':
            return get_hwp_text(file_bytes)
        elif file_ext in ['xlsx', 'xlsm']:
            return excel_to_text(file_bytes)
        elif file_ext in ['docx', 'doc']:
            return docx_to_text(file_bytes)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
    except Exception as e:
        raise Exception(f"파일 파싱 오류 ({file_ext}): {str(e)}")

def parse_posting_date(date_str: Optional[str]) -> datetime:
    """게시일시 파싱"""
    if date_str and date_str.strip():
        try:
            # ISO 형식 파싱
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            try:
                # 다른 형식 시도
                from dateutil import parser
                return parser.parse(date_str)
            except:
                pass
    
    # 기본값: 오늘 11:00
    now = datetime.now()
    return now.replace(hour=11, minute=0, second=0, microsecond=0)

# 서버 실행 코드
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("구매계획안 분석 API 서버 시작")
    print("=" * 60)
    print("주소: http://localhost:8000")
    print("문서: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )
