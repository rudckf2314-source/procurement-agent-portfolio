import io
from docx import Document

def docx_to_text(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file, including paragraphs and tables.
    """
    try:
        file_stream = io.BytesIO(file_bytes)
        doc = Document(file_stream)
        
        text_parts = []
        
        # Extract text from paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text.strip())
        
        # Extract text from tables
        # Note: This might disrupt the linear flow of the document if tables are interleaved,
        # but unfortunately python-docx stores them separately in .tables vs .paragraphs list (unlike some other libs).
        # Actually, python-docx holds them in document.element.body, but iterating that is complex.
        # For a simple extractor, appending tables at the end or just gathering all text is a starting point.
        # However, a better approach for RAG/LLM is often just getting the chunks. 
        # Let's try to just get all content.
        
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                     if cell.text.strip():
                         row_text.append(cell.text.strip())
                if row_text:
                    text_parts.append(" | ".join(row_text))
                    
        return '\n'.join(text_parts)
    except Exception as e:
        print(f"Error parsing DOCX: {e}")
        # Return empty string or re-raise depending on preference. 
        # Usually for this app we'd want to know if it failed, but returning empty triggers handling upstream.
        return ""
