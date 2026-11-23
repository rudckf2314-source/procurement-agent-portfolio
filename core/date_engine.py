from datetime import datetime, timedelta, time
import holidays

def is_business_day(date_obj) -> bool:
    """주말 및 한국 공휴일 여부 확인"""
    kr_holidays = holidays.KR()
    # weekday(): 0=Mon, ... 5=Sat, 6=Sun
    # 주말(토/일)이거나 공휴일이면 False (영업일 아님)
    if date_obj.weekday() >= 5 or date_obj in kr_holidays:
        return False
    return True

def parse_submission_start_dt(date_str: str, default_dt: datetime = None) -> datetime:
    """날짜 문자열 파싱 (실패 시 default_dt 또는 현재 시간)"""
    if default_dt is None:
        default_dt = datetime.now()
        
    if not date_str:
        return default_dt

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        pass
        
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except:
        return default_dt

def subtract_business_days(date_obj, days: int):
    """영업일 기준 days일 전 날짜 계산"""
    current_date = date_obj
    days_subtracted = 0
    while days_subtracted < days:
        current_date -= timedelta(days=1)
        if is_business_day(current_date):
            days_subtracted += 1
    return current_date

def calc_open_datetime(start_dt: datetime, notice_type: str) -> datetime:
    """
    개찰일시 계산 로직 변경
    - 적격심사: 게시일 + 8일 (휴일 무관), 게시 시간 + 1시간
    - 소액수의: 게시일로부터 영업일 기준 4일 소요되는 날짜, 게시 시간 + 1시간
    """
    # 계산은 날짜(date) 기준으로 수행
    current_date = start_dt.date()
    # 게시 시간 기준 + 1시간
    target_time = (start_dt + timedelta(hours=1)).time()
    
    # 공고 구분 (한글/영문 대응)
    is_eligible = "적격" in notice_type or "eligible" in notice_type
    
    if is_eligible:
        # 1. 적격심사: 주말/공휴일 상관없이 8일 후
        target_date = current_date + timedelta(days=8)
    else:
        # 2. 소액수의: 영업일 기준 4일 확보
        days_counted = 0
        temp_date = current_date
        
        while days_counted < 4:
            temp_date += timedelta(days=1)
            # 영업일(평일+비공휴일)인 경우에만 카운트 증가
            if is_business_day(temp_date):
                days_counted += 1
        
        target_date = temp_date

    return datetime.combine(target_date, target_time)

def calc_submission_period(start_dt: datetime, open_dt: datetime) -> str:
    """
    제출기간 텍스트 생성 (로직 변경)
    - 제출시작일시: 개찰일시 영업일 기준 2일 전, 시간 -2시간
    - 제출종료일시: 개찰일시 -1시간
    """
    # 1. 종료일시: 개찰일시 1시간 전
    submission_end_dt = open_dt - timedelta(hours=1)
    
    # 2. 시작일시: 개찰일(Date) 기준 영업일 2일 전, 시간은 개찰시간 - 2시간
    # 날짜 계산 (영업일 역산)
    open_date = open_dt.date()
    start_date = subtract_business_days(open_date, 2)
    
    # 시간 계산
    start_time_dt = open_dt - timedelta(hours=2) # 시간만 참조하기 위함
    submission_start_dt = datetime.combine(start_date, start_time_dt.time())
    
    start_str = submission_start_dt.strftime("%Y-%m-%d %H:%M")
    end_str = submission_end_dt.strftime("%Y-%m-%d %H:%M")
    
    return f"{start_str} ~ {end_str}"

def calc_consortium_deadline(open_dt: datetime) -> datetime:
    """공동수급협정서 마감: 개찰일 전일 18:00"""
    day_before = open_dt - timedelta(days=1)
    return datetime.combine(day_before.date(), time(18, 0))
