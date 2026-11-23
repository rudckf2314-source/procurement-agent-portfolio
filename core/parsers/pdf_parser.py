"""
Enhanced PDF parser with multiple fallback methods for better text extraction.
Tries pdfplumber (best for tables), pymupdf (fastest), and pypdf (basic) in order.
"""
from io import BytesIO
import sys

def pdf_to_text(file_content: bytes) -> str:
    """
    Extract text from a PDF file using multiple methods for best results.
    
    Tries in order:
    1. pdfplumber - Best for complex layouts and tables
    2. pymupdf (fitz) - Fast and reliable
    3. pypdf - Basic fallback
    
    Args:
        file_content: PDF file as bytes
        
    Returns:
        Extracted text as string
    """
    
    # Method 1: Try pdfplumber (best for tables and complex layouts)
    try:
        import pdfplumber
        
        with pdfplumber.open(BytesIO(file_content)) as pdf:
            text_parts = []
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text
                page_text = page.extract_text()
                
                # Extract tables separately for better formatting
                tables = page.extract_tables()
                
                if page_text:
                    text_parts.append(f"[Page {page_num}]\n{page_text}")
                
                # Add table data in structured format
                if tables:
                    for table_idx, table in enumerate(tables, 1):
                        text_parts.append(f"\n[Table {table_idx} on Page {page_num}]")
                        for row in table:
                            if row:
                                # Filter out None values and join
                                row_text = " | ".join([str(cell).strip() if cell else "" for cell in row])
                                if row_text.strip():
                                    text_parts.append(row_text)
                
                text_parts.append("\n")  # Page separator
            
            result = "\n".join(text_parts).strip()
            
            if result and len(result) > 50:  # Valid content check
                print(f"✅ PDF parsed successfully with pdfplumber ({len(result)} chars)")
                return result
            else:
                raise ValueError("pdfplumber extracted insufficient text")
                
    except ImportError:
        print("⚠️  pdfplumber not installed, trying pymupdf...")
    except Exception as e:
        print(f"⚠️  pdfplumber failed: {str(e)}, trying pymupdf...")
    
    # Method 2: Try pymupdf (PyMuPDF) - very fast and reliable
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=file_content, filetype="pdf")
        text_parts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Extract text with layout preservation
            page_text = page.get_text("text")
            
            if page_text and page_text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{page_text}")
            
            # Also try extracting tables/blocks for better structure
            blocks = page.get_text("blocks")
            if blocks and not page_text:
                # If normal text extraction failed, try blocks
                block_texts = [block[4] for block in blocks if len(block) > 4]
                if block_texts:
                    text_parts.append("\n".join(block_texts))
        
        doc.close()
        
        result = "\n\n".join(text_parts).strip()
        
        if result and len(result) > 50:
            print(f"✅ PDF parsed successfully with pymupdf ({len(result)} chars)")
            return result
        else:
            raise ValueError("pymupdf extracted insufficient text")
            
    except ImportError:
        print("⚠️  pymupdf not installed, trying pypdf...")
    except Exception as e:
        print(f"⚠️  pymupdf failed: {str(e)}, trying pypdf...")
    
    # Method 3: Fallback to pypdf (basic but always available)
    try:
        from pypdf import PdfReader
        
        reader = PdfReader(BytesIO(file_content))
        text_parts = []
        
        for page_num, page in enumerate(reader.pages, 1):
            # Try layout mode first (better spacing)
            try:
                page_text = page.extract_text(extraction_mode="layout")
            except:
                # Fallback to basic extraction
                page_text = page.extract_text()
            
            if page_text and page_text.strip():
                text_parts.append(f"[Page {page_num}]\n{page_text}")
        
        result = "\n\n".join(text_parts).strip()
        
        if result:
            print(f"✅ PDF parsed with pypdf ({len(result)} chars)")
            return result
        else:
            return "⚠️  PDF appears to be empty or contains only images (OCR not supported)"
            
    except Exception as e:
        error_msg = f"❌ All PDF parsing methods failed: {str(e)}"
        print(error_msg)
        return error_msg
