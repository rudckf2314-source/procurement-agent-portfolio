let appState = {
    inputMode: 'file',
    selectedFile: null,
    noticeType: 'auto',
    currentResult: null,
    smppStatus: null
};

// Mock data for demonstration
const mockResult = {
    notice_type: 'small_quote',
    notice_title: '사무용품 구매 공고',
    contract_period_text: '계약일로부터 30일',
    budget_vat_included_krw: 55000000,
    estimated_price_ex_vat_krw: 50000000,
    competition_method_text: '제한경쟁계약 (중소기업자간 경쟁)',
    appendix_text: '별표1',
    sme_limit_text: '중소기업만 참가 가능',
    region_limit: '전국',
    has_direct_production: true,
    consortium_text: '2인 이상 공동도급 가능',
    consortium_deadline_dt: '2025-05-25 15:00',
    item_code_text: '42151501',
    item_name_api_text: '사무용 의자',
    submission_period_text: '2025-05-20 11:00 ~ 2025-05-27 15:00',
    open_datetime_dt: '2025-05-27 15:30',
    legal_report: {
        gosi_amount: {
            reference: '조달사업에 관한 법률 시행령 제43조',
            statute: '중소기업제품 구매촉진 및 판로지원에 관한 법률',
            content: '2억 3천만원'
        },
        compliance_note: '해당 계약은 고시금액 이하이므로 중소기업 제품 구매 의무가 적용됩니다. 지역제한은 없으나, 중소기업자 간 경쟁으로 제한됩니다.'
    }
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    setDefaultDateTime();
    setComplianceYear();
    setInitialInputMode();
});

// Set initial input mode display
function setInitialInputMode() {
    const textArea = document.getElementById('textInputArea');
    const fileArea = document.getElementById('fileInputArea');

    // Show file input by default
    textArea.style.display = 'none';
    fileArea.style.display = 'block';
}

// Set current year for compliance message
function setComplianceYear() {
    const currentYear = new Date().getFullYear();
    const complianceText = `${currentYear}년 최신 조달규정 자동 적용 중`;
    document.getElementById('complianceYear').textContent = complianceText;
}

// Event Listeners
function initializeEventListeners() {
    // Input mode radio buttons
    document.querySelectorAll('input[name="inputMode"]').forEach(radio => {
        radio.addEventListener('change', handleInputModeChange);
    });

    // Notice type radio buttons
    document.querySelectorAll('input[name="noticeType"]').forEach(radio => {
        radio.addEventListener('change', handleNoticeTypeChange);
    });

    // File upload
    const fileUploadZone = document.getElementById('fileUploadZone');
    const fileInput = document.getElementById('fileInput');

    fileUploadZone.addEventListener('click', () => {
        if (!document.getElementById('fileSelected').style.display ||
            document.getElementById('fileSelected').style.display === 'none') {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', handleFileSelect);

    // Drag and drop
    fileUploadZone.addEventListener('dragover', handleDragOver);
    fileUploadZone.addEventListener('dragleave', handleDragLeave);
    fileUploadZone.addEventListener('drop', handleFileDrop);

    // Remove file button
    document.getElementById('removeFile').addEventListener('click', (e) => {
        e.stopPropagation();
        removeFile();
    });

    // Generate button
    document.getElementById('generateBtn').addEventListener('click', handleGenerate);

    // Tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.addEventListener('click', handleTabChange);
    });


    // Download buttons
    document.getElementById('downloadPDF')?.addEventListener('click', () => downloadReport('pdf'));
    document.getElementById('downloadWord')?.addEventListener('click', () => downloadReport('word'));


    // Table edit controls
    document.getElementById('editTableBtn')?.addEventListener('click', enableTableEdit);
    document.getElementById('applyTableBtn')?.addEventListener('click', applyTableChanges);
    document.getElementById('resetTableBtn')?.addEventListener('click', resetTableData);
}

// Set default date/time to today 11:00
function setDefaultDateTime() {
    const now = new Date();
    now.setHours(11, 0, 0, 0);
    const dateString = now.toISOString().slice(0, 16);
    document.getElementById('postingDate').value = dateString;
}

// Handle input mode change
function handleInputModeChange(e) {
    appState.inputMode = e.target.value;

    const textArea = document.getElementById('textInputArea');
    const fileArea = document.getElementById('fileInputArea');

    if (appState.inputMode === 'text') {
        textArea.style.display = 'block';
        fileArea.style.display = 'none';
        removeFile();
    } else {
        textArea.style.display = 'none';
        fileArea.style.display = 'block';
        document.getElementById('procurementText').value = '';
    }
}

// Handle notice type change
function handleNoticeTypeChange(e) {
    appState.noticeType = e.target.value;
}

// File upload handlers
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        displaySelectedFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
}

function handleFileDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');

    const file = e.dataTransfer.files[0];
    if (file) {
        const allowedTypes = ['.pdf', '.hwp', '.xlsm', '.xlsx', '.docx', '.doc'];
        const fileExt = '.' + file.name.split('.').pop().toLowerCase();

        if (allowedTypes.includes(fileExt)) {
            document.getElementById('fileInput').files = e.dataTransfer.files;
            displaySelectedFile(file);
        } else {
            alert('지원하지 않는 파일 형식입니다. PDF, HWP, Excel, Word 파일만 업로드 가능합니다.');
        }
    }
}

function displaySelectedFile(file) {
    appState.selectedFile = file;

    const uploadContent = document.querySelector('.file-upload-content');
    const fileSelected = document.getElementById('fileSelected');
    const fileName = document.getElementById('fileName');

    uploadContent.style.display = 'none';
    fileSelected.style.display = 'flex';
    fileName.textContent = file.name;
}

function removeFile() {
    appState.selectedFile = null;
    document.getElementById('fileInput').value = '';

    const uploadContent = document.querySelector('.file-upload-content');
    const fileSelected = document.getElementById('fileSelected');

    uploadContent.style.display = 'block';
    fileSelected.style.display = 'none';
}

// Handle generate button click
async function handleGenerate() {
    // Validate input
    if (appState.inputMode === 'text') {
        const text = document.getElementById('procurementText').value.trim();
        if (!text) {
            alert('구매계획안 텍스트를 입력해주세요.');
            return;
        }
    } else {
        if (!appState.selectedFile) {
            alert('파일을 업로드해주세요.');
            return;
        }
    }

    // Show loading state
    showLoadingState();

    // Call real backend API
    try {
        let result;

        if (appState.inputMode === 'text') {
            result = await analyzeText();
        } else {
            result = await analyzeFile();
        }

        // Display results
        displayResults(result);
    } catch (error) {
        console.error('API Error:', error);
        alert('오류가 발생했습니다: ' + error.message);
        showInitialState();
    }
}

// API 호출: 텍스트 분석
async function analyzeText() {
    const text = document.getElementById('procurementText').value.trim();
    const postingDate = document.getElementById('postingDate').value;
    const noticeType = appState.noticeType;
    const noticeNumber = document.getElementById('noticeNumber').value.trim() || null;

    const API_URL = 'http://localhost:8000/api/analyze/text';

    const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: text,
            posting_date: postingDate || null,
            notice_type: noticeType,
            notice_number: noticeNumber
        })
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '서버 오류가 발생했습니다.');
    }

    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || '분석에 실패했습니다.');
    }

    return data.data;
}

// API 호출: 파일 분석
async function analyzeFile() {
    const file = appState.selectedFile;
    const postingDate = document.getElementById('postingDate').value;
    const noticeType = appState.noticeType;
    const noticeNumber = document.getElementById('noticeNumber').value.trim() || '';

    const API_URL = 'http://localhost:8000/api/analyze/file';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('posting_date', postingDate || '');
    formData.append('notice_type', noticeType);
    formData.append('notice_number', noticeNumber);

    const response = await fetch(API_URL, {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '서버 오류가 발생했습니다.');
    }

    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || '분석에 실패했습니다.');
    }

    return data.data;
}

// Show loading state
function showLoadingState() {
    document.getElementById('initialState').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('resultState').style.display = 'none';
}

// Show initial state
function showInitialState() {
    document.getElementById('initialState').style.display = 'block';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('resultState').style.display = 'none';
}

// Display results
function displayResults(apiResponse) {
    appState.currentResult = apiResponse;

    // Extract data from backend response
    const patch = apiResponse.patch;
    const audit = apiResponse.audit;
    const report = apiResponse.report;

    // Update legal report
    if (audit && audit.legal_report) {
        const legalReport = audit.legal_report;
        const legalData = legalReport.data || {};

        if (legalData.gosi_amount) {
            document.getElementById('legalReference').textContent =
                legalData.gosi_amount.reference || '-';
            document.getElementById('legalStatute').textContent =
                '기준: ' + (legalData.gosi_amount.statute || '');
            document.getElementById('gosiAmount').textContent =
                legalData.gosi_amount.content || '-';
        }

        document.getElementById('complianceNote').textContent =
            legalReport.compliance_note || '법무 검토 내용 없음';
    }

    // Update estimated price
    document.getElementById('estimatedPrice').textContent =
        formatNumber(patch.estimated_price_ex_vat_krw) + ' 원';

    // Update summary
    const noticeTypeMap = {
        'small_quote': '소액수의',
        'eligible_review': '적격심사'
    };
    document.getElementById('noticeTypeBadge').textContent =
        noticeTypeMap[patch.notice_type] || patch.notice_type;

    document.getElementById('submissionPeriod').textContent =
        patch.submission_period_text;
    document.getElementById('openDateTime').textContent =
        formatDateTime(patch.open_datetime_dt);

    // Update modification table
    const tableData = [
        { item: '한국환경공단 입찰공고번호', content: patch.notice_number || '- (미입력)' },
        { item: '공고명', content: patch.notice_title },
        { item: '계약기간', content: patch.contract_period_text },
        { item: '예산액(VAT포함)', content: formatNumber(patch.budget_vat_included_krw) + ' 원' },
        { item: '추정가격(VAT제외)', content: formatNumber(patch.estimated_price_ex_vat_krw) + ' 원' },
        { item: '경쟁방식', content: patch.competition_method_text },
        { item: '별표(적격심사 시)', content: patch.appendix_text || '-' },
        { item: '기업규모 제한', content: patch.sme_limit_text },
        { item: '지역 제한', content: patch.region_limit || '전국' },
        { item: '직접생산확인', content: patch.has_direct_production ? '필요 (중기간경쟁제품)' : '-' },
        { item: '공동계약', content: patch.consortium_text },
        { item: '공동수급협정서 마감', content: formatDateTime(patch.consortium_deadline_dt) || '-' },
        { item: '세부품명번호', content: patch.item_code_text || '-' },
        { item: '세부품명 (API 조회)', content: patch.item_name_api_text || '- (API 권한 필요)' },
        { item: '업종코드', content: patch.industry_code_text || '-' },
        { item: '업종명', content: patch.industry_name_text || '-' },
        { item: '담당자 정보', content: patch.manager_info || '환경처 조달부(☎02-2110-0000, 담당 : 홍길동 대리)' }
    ];

    const tbody = document.querySelector('#modificationTable tbody');
    tbody.innerHTML = '';

    tableData.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${row.item}</strong></td>
            <td>${row.content}</td>
        `;
        tbody.appendChild(tr);
    });

    // Always generate report from current patch data (instead of using backend report)
    // This ensures any edits in the analysis summary are reflected in the report
    const generatedReport = generateReportContent(patch);
    document.getElementById('reportContent').innerHTML = formatMarkdown(generatedReport);

    // Update JSON displays
    document.getElementById('patchJson').textContent =
        JSON.stringify(patch, null, 2);
    document.getElementById('auditJson').textContent =
        JSON.stringify(audit, null, 2);

    // Show result state
    document.getElementById('initialState').style.display = 'none';
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('resultState').style.display = 'block';
}

// Format datetime string
function formatDateTime(dtString) {
    if (!dtString) return '';
    try {
        const dt = new Date(dtString);
        return dt.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).replace(/\. /g, '-').replace('.', '');
    } catch {
        return dtString;
    }
}

// Simple markdown to HTML converter
function formatMarkdown(markdown) {
    if (!markdown) return '';

    let html = markdown
        // Streamlit :blue[] syntax
        .replace(/:blue\[(.*?)\]/g, '<span style="color: #2563eb; font-weight: 600;">$1</span>')
        .replace(/:red\[(.*?)\]/g, '<span style="color: #ef4444; font-weight: 600;">$1</span>')
        .replace(/:green\[(.*?)\]/g, '<span style="color: #10b981; font-weight: 600;">$1</span>')
        // Headers
        .replace(/^### (.*$)/gim, '<h4>$1</h4>')
        .replace(/^## (.*$)/gim, '<h3>$1</h3>')
        .replace(/^# (.*$)/gim, '<h2>$1</h2>')
        // Bold
        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
        // Lists
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        // Line breaks
        .replace(/\n/gim, '<br>');

    // Wrap lists
    html = html.replace(/(<li>.*<\/li>)/gis, '<ul>$1</ul>');

    return html;
}

// Handle tab change
function handleTabChange(e) {
    const tabName = e.target.dataset.tab;

    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    e.target.classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    if (tabName === 'analysis') {
        document.getElementById('analysisTab').classList.add('active');
    } else if (tabName === 'report') {
        document.getElementById('reportTab').classList.add('active');
    }
}


// Download functions
async function downloadReport(format) {
    if (!appState.currentResult) {
        alert('먼저 분석을 실행해주세요.');
        return;
    }

    if (format === 'pdf') {
        try {
            // 백엔드에서 PDF 파일 생성 요청
            const API_URL = 'http://localhost:8000/api/download/pdf';

            console.log('PDF 다운로드 요청 시작...');

            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(appState.currentResult.patch)
            });

            if (!response.ok) {
                const errorText = await response.text() || 'PDF 파일 생성에 실패했습니다.';
                throw new Error(errorText);
            }

            // Blob으로 받아서 다운로드
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            // 공고 유형에 따라 파일명 결정
            const noticeType = appState.currentResult.patch.notice_type;
            const filename = noticeType === 'eligible_review'
                ? '적격심사_보고서.pdf'
                : '소액수의_보고서.pdf';

            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

            console.log(`PDF 다운로드 완료: ${filename}`);

        } catch (error) {
            console.error('PDF 다운로드 오류:', error);
            alert('PDF 문서 다운로드 중 오류가 발생했습니다.\n\n' +
                '확인사항:\n' +
                '1. 백엔드 서버가 실행 중인지 확인\n' +
                '2. docx2pdf 라이브러리가 설치되어 있는지 확인\n' +
                '3. Windows의 경우 MS Word가 설치되어 있어야 합니다.\n\n' +
                '오류: ' + error.message);
        }
    } else if (format === 'word') {
        try {
            // 백엔드에서 Word 파일 생성 요청
            const API_URL = 'http://localhost:8000/api/download/word';

            const response = await fetch(API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(appState.currentResult.patch)
            });

            if (!response.ok) {
                throw new Error('Word 파일 생성에 실패했습니다.');
            }

            // Blob으로 받아서 다운로드
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            // 공고 유형에 따라 파일명 결정
            const noticeType = appState.currentResult.patch.notice_type;
            const filename = noticeType === 'eligible_review'
                ? '적격심사_보고서.docx'
                : '소액수의_보고서.docx';

            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error('Word 다운로드 오류:', error);
            alert('Word 문서 다운로드 중 오류가 발생했습니다. 백엔드 서버가 실행 중인지 확인해주세요.');
        }
    }
}

function generateReportContent(patch) {
    const noticeTypeMap = {
        'small_quote': '소액수의',
        'eligible_review': '적격심사'
    };

    return `# 공고문 수정값 생성 보고서

## 공고 유형
${noticeTypeMap[patch.notice_type] || patch.notice_type}

## 기본 정보
- **공고명**: ${patch.notice_title}
- **계약기간**: ${patch.contract_period_text}
- **예산액(VAT포함)**: ${formatNumber(patch.budget_vat_included_krw)} 원
- **추정가격(VAT제외)**: ${formatNumber(patch.estimated_price_ex_vat_krw)} 원

## 일정
- **제출기간**: ${patch.submission_period_text}
- **개찰일시**: ${formatDateTime(patch.open_datetime_dt)}

## 계약 조건
- **경쟁방식**: ${patch.competition_method_text}
- **기업규모 제한**: ${patch.sme_limit_text}
- **지역 제한**: ${patch.region_limit || '전국'}
- **별표**: ${patch.appendix_text || '-'}

---
*생성일시: ${new Date().toLocaleString('ko-KR')}*
`;
}



// Utility function to format numbers
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Add smooth scroll behavior
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

// Table Edit Functions
let originalTableData = null;

function enableTableEdit() {
    try {
        console.log('수정하기 버튼 클릭됨');

        // Save original data
        const table = document.getElementById('modificationTable');
        if (!table) {
            console.error('테이블을 찾을 수 없습니다');
            return;
        }

        const rows = table.querySelectorAll('tbody tr');
        console.log(`총 ${rows.length}개 행 발견`);

        originalTableData = [];

        rows.forEach((row, index) => {
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) {
                console.warn(`행 ${index}에 충분한 셀이 없습니다`);
                return;
            }

            originalTableData.push({
                item: cells[0].textContent,
                content: cells[1].textContent
            });

            // Make second column editable
            const contentCell = cells[1];
            const currentText = contentCell.textContent;
            contentCell.innerHTML = `<textarea class="table-edit-input" rows="3">${currentText}</textarea>`;
        });

        console.log('원본 데이터 저장 완료:', originalTableData);

        // Toggle button visibility
        const editBtn = document.getElementById('editTableBtn');
        const applyBtn = document.getElementById('applyTableBtn');
        const resetBtn = document.getElementById('resetTableBtn');

        if (editBtn) editBtn.style.display = 'none';
        if (applyBtn) applyBtn.style.display = 'inline-flex';
        if (resetBtn) resetBtn.style.display = 'inline-flex';

        console.log('편집 모드 활성화 완료');
    } catch (error) {
        console.error('편집 모드 활성화 중 오류:', error);
        alert('편집 모드 활성화 중 오류가 발생했습니다: ' + error.message);
    }
}

function applyTableChanges() {
    const table = document.getElementById('modificationTable');
    const rows = table.querySelectorAll('tbody tr');

    // Apply changes from textareas
    rows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        const textarea = cells[1].querySelector('textarea');
        if (textarea) {
            const newValue = textarea.value;
            cells[1].textContent = newValue;

            // Update appState.currentResult.patch data
            const itemName = cells[0].textContent;
            updatePatchData(itemName, newValue);
        }
    });

    // Update original data to new values
    originalTableData = [];
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        originalTableData.push({
            item: cells[0].textContent,
            content: cells[1].textContent
        });
    });

    // Toggle button visibility
    document.getElementById('editTableBtn').style.display = 'inline-flex';
    document.getElementById('applyTableBtn').style.display = 'none';
    document.getElementById('resetTableBtn').style.display = 'none';

    // Regenerate report with updated data
    if (appState.currentResult && appState.currentResult.patch) {
        const generatedReport = generateReportContent(appState.currentResult.patch);
        document.getElementById('reportContent').innerHTML = formatMarkdown(generatedReport);
        console.log('보고서가 최신 데이터로 업데이트되었습니다');
    }

    alert('변경사항이 반영되었습니다!');
}

function resetTableData() {
    if (!originalTableData) return;

    const table = document.getElementById('modificationTable');
    const rows = table.querySelectorAll('tbody tr');

    // Restore original data
    rows.forEach((row, index) => {
        const cells = row.querySelectorAll('td');
        if (originalTableData[index]) {
            cells[1].textContent = originalTableData[index].content;
        }
    });

    // Toggle button visibility
    document.getElementById('editTableBtn').style.display = 'inline-flex';
    document.getElementById('applyTableBtn').style.display = 'none';
    document.getElementById('resetTableBtn').style.display = 'none';
}

function updatePatchData(itemName, newValue) {
    if (!appState.currentResult || !appState.currentResult.patch) return;

    const patch = appState.currentResult.patch;

    //  Map Korean item names to patch field names
    const fieldMap = {
        '한국환경공단 입찰공고번호': 'notice_number',
        '공고명': 'notice_title',
        '계약기간': 'contract_period_text',
        '예산액(VAT포함)': 'budget_vat_included_krw',
        '추정가격(VAT제외)': 'estimated_price_ex_vat_krw',
        '경쟁방식': 'competition_method_text',
        '별표(적격심사 시)': 'appendix_text',
        '기업규모 제한': 'sme_limit_text',
        '지역 제한': 'region_limit',
        '직접생산확인': 'has_direct_production',
        '공동계약': 'consortium_text',
        '공동수급협정서 마감': 'consortium_deadline_dt',
        '세부품명번호': 'item_code_text',
        '세부품명 (API 조회)': 'item_name_api_text'
    };

    const fieldName = fieldMap[itemName];
    if (fieldName) {
        // Handle special cases
        if (fieldName === 'budget_vat_included_krw' || fieldName === 'estimated_price_ex_vat_krw') {
            // Remove commas and " 원" suffix
            patch[fieldName] = parseInt(newValue.replace(/[,원\s]/g, '')) || 0;
        } else if (fieldName === 'has_direct_production') {
            patch[fieldName] = newValue.includes('필요');
        } else {
            patch[fieldName] = newValue;
        }
    }
}

// ========================================
// SMPP Database Functions
// ========================================

// Load SMPP database status on page load
async function loadSmppStatus() {
    try {
        const API_URL = 'http://localhost:8000/api/smpp/status';
        const response = await fetch(API_URL);

        if (!response.ok) {
            throw new Error('SMPP 상태 조회 실패');
        }

        const data = await response.json();
        appState.smppStatus = data;
        displaySmppStatus(data);
    } catch (error) {
        console.error('SMPP 상태 로딩 오류:', error);
        document.getElementById('smppNoticeInfo').innerHTML = '로드 실패 (서버 확인 필요)';
    }
}

// Display SMPP database status
function displaySmppStatus(data) {
    const noticeInfo = document.getElementById('smppNoticeInfo');
    const statusDiv = document.getElementById('smppStatus');

    if (data.cache_exists) {
        const metadata = data.metadata;
        const notice = metadata.notice_info;

        // Notice info
        noticeInfo.innerHTML = `
            <strong style="font-size: 1rem;">${notice.department} 제 ${notice.notice_number}호</strong><br>
            <span style="font-size: 0.85rem;">고시일자: ${notice.notice_date}</span><br>
            <span style="font-size: 0.85rem;">제한 품목: <strong>${metadata.total_count}개</strong></span>
        `;

        // Cache status
        const cacheAge = data.cache_age_days;
        const expiryDays = metadata.cache_expiry_days;
        const remaining = expiryDays - cacheAge;

        if (remaining > 0) {
            statusDiv.innerHTML = `
                <div style="background: #dcfce7; color: #166534; padding: 0.75rem; border-radius: 8px;">
                    캐시 유효 (만료까지 ${remaining}일)
                </div>
            `;
        } else {
            statusDiv.innerHTML = `
                <div style="background: #fef3c7; color: #92400e; padding: 0.75rem; border-radius: 8px;">
                    캐시 만료됨 (${cacheAge}일 경과)
                </div>
            `;
        }
    } else {
        noticeInfo.innerHTML = 'SMPP 데이터베이스 캐시 없음';
        statusDiv.innerHTML = `
            <div style="background: #fee2e2; color: #991b1b; padding: 0.75rem; border-radius: 8px;">
                 캐시 없음 - 새로고침 필요
            </div>
        `;
    }
}

// Refresh SMPP database
async function refreshSmppDatabase() {
    const button = document.getElementById('refreshSmppBtn');
    button.disabled = true;
    button.innerHTML = `
        <svg style="width: 16px; height: 16px; animation: spin 1s linear infinite;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        다운로드 중...
    `;

    try {
        const API_URL = 'http://localhost:8000/api/smpp/refresh';
        const response = await fetch(API_URL, { method: 'POST' });

        if (!response.ok) {
            throw new Error('SMPP 새로고침 실패');
        }

        const data = await response.json();

        if (data.success) {
            alert(` ${data.total_count}개 품목 업데이트 완료!`);
            await loadSmppStatus(); // Reload status
        } else {
            throw new Error(data.message || '새로고침 실패');
        }
    } catch (error) {
        console.error('SMPP 새로고침 오류:', error);
        alert('SMPP 데이터 새로고침 실패\n\n' + error.message);
    } finally {
        button.disabled = false;
        button.innerHTML = `
            <svg style="width: 16px; height: 16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            SMPP 데이터 새로고침
        `;
    }
}

// Add refresh button event listener
document.addEventListener('DOMContentLoaded', () => {
    loadSmppStatus(); // Load on page load

    const refreshBtn = document.getElementById('refreshSmppBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshSmppDatabase);
    }
});

// Add CSS for spin animation
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// ========================================
// Chatbot Logic
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    const chatbotToggler = document.querySelector(".chatbot-toggler");
    const closeBtn = document.querySelector(".close-btn");
    const chatbox = document.querySelector(".chatbox");
    const chatInput = document.querySelector(".chat-input textarea");
    const sendChatBtn = document.querySelector(".chat-input span");

    if (!chatbotToggler) return;

    let userMessage = null;
    const inputInitHeight = chatInput ? chatInput.scrollHeight : 0;

    const createChatLi = (message, className) => {
        const chatLi = document.createElement("li");
        chatLi.classList.add("chat", className);
        let chatContent = className === "outgoing" ? `<p></p>` : `<span class="material-symbols-outlined">smart_toy</span><p></p>`;
        chatLi.innerHTML = chatContent;
        chatLi.querySelector("p").textContent = message;
        return chatLi;
    }

    const generateResponse = async (chatElement) => {
        const API_URL = "http://localhost:8000/api/chat";
        const messageElement = chatElement.querySelector("p");

        let context = "";
        // Use appState from global scope if available
        if (typeof appState !== 'undefined') {
            const contextData = {};
            if (appState.currentResult && appState.currentResult.patch) {
                contextData.analysis_result = appState.currentResult.patch;
            }
            if (appState.currentResult && appState.currentResult.audit && appState.currentResult.audit.legal_report) {
                contextData.legal_report = appState.currentResult.audit.legal_report;
            }
            if (appState.smppStatus) {
                contextData.smpp_status = appState.smppStatus;
            }
            if (Object.keys(contextData).length > 0) {
                context = JSON.stringify(contextData, null, 2);
            }
        }

        const requestOptions = {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                messages: [{ role: "user", content: userMessage }],
                context: context
            })
        }

        try {
            const response = await fetch(API_URL, requestOptions);
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "오류가 발생했습니다.");

            messageElement.textContent = data.response;
        } catch (error) {
            messageElement.classList.add("error");
            messageElement.textContent = error.message;
        } finally {
            chatbox.scrollTo(0, chatbox.scrollHeight);
        }
    }

    const handleChat = () => {
        userMessage = chatInput.value.trim();
        if (!userMessage) return;

        chatInput.value = "";
        chatInput.style.height = `${inputInitHeight}px`;

        chatbox.appendChild(createChatLi(userMessage, "outgoing"));
        chatbox.scrollTo(0, chatbox.scrollHeight);

        const incomingChatLi = createChatLi("생각 중입니다...", "incoming");
        chatbox.appendChild(incomingChatLi);
        chatbox.scrollTo(0, chatbox.scrollHeight);

        generateResponse(incomingChatLi);
    }

    if (chatInput) {
        chatInput.addEventListener("input", () => {
            chatInput.style.height = `${inputInitHeight}px`;
            chatInput.style.height = `${chatInput.scrollHeight}px`;
        });

        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey && window.innerWidth > 800) {
                e.preventDefault();
                handleChat();
            }
        });
    }

    if (sendChatBtn) {
        sendChatBtn.addEventListener("click", handleChat);
    }

    if (closeBtn) {
        closeBtn.addEventListener("click", () => document.body.classList.remove("show-chatbot"));
    }

    if (chatbotToggler) {
        chatbotToggler.addEventListener("click", () => document.body.classList.toggle("show-chatbot"));
    }
});
