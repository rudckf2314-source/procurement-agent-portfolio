"""
PDF Parser Test Script
Tests the enhanced PDF parser with multiple fallback methods.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parsers.pdf_parser import pdf_to_text

def test_pdf_parser():
    """
    Test the PDF parser with a sample file.
    You can create a simple test PDF or use an actual procurement plan PDF.
    """
    
    print("=" * 60)
    print("PDF Parser Test")
    print("=" * 60)
    print()
    
    # Check if test PDF exists
    test_pdf_path = "test_sample.pdf"
    
    if not os.path.exists(test_pdf_path):
        print(f"⚠️  Test PDF not found: {test_pdf_path}")
        print()
        print("To test the PDF parser:")
        print("1. Place a PDF file named 'test_sample.pdf' in the hackerton directory")
        print("2. Run this script again: python core/test_pdf_parser.py")
        print()
        print("Or upload a PDF through the web interface:")
        print("- Run: python api_server.py")
        print("- Open: http://localhost:8000")
        print()
        return
    
    # Read the PDF file
    with open(test_pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    print(f"📄 Testing PDF: {test_pdf_path}")
    print(f"📊 File size: {len(pdf_bytes):,} bytes")
    print()
    print("🔄 Starting extraction (trying multiple methods)...")
    print("-" * 60)
    
    # Extract text
    text = pdf_to_text(pdf_bytes)
    
    print("-" * 60)
    print()
    
    # Display results
    if text and not text.startswith("❌") and not text.startswith("⚠️"):
        print("✅ PDF Parsing Successful!")
        print()
        print(f"📝 Extracted {len(text)} characters")
        print(f"📄 Extracted {len(text.split())} words")
        print(f"📋 Extracted {text.count('[Page')} pages")
        print()
        
        # Show preview
        print("Preview (first 500 characters):")
        print("-" * 60)
        print(text[:500])
        if len(text) > 500:
            print("...")
        print("-" * 60)
        
        # Save to file
        output_file = "extracted_text.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print()
        print(f"💾 Full text saved to: {output_file}")
        
    else:
        print("❌ PDF Parsing Failed!")
        print()
        print("Error message:")
        print(text)
        print()
        print("Possible reasons:")
        print("- PDF contains only scanned images (OCR not supported)")
        print("- PDF is encrypted or corrupted")
        print("- Required libraries not installed")
        print()
        print("Try installing additional PDF libraries:")
        print("  pip install pdfplumber pymupdf")
    
    print()
    print("=" * 60)

if __name__ == "__main__":
    test_pdf_parser()
