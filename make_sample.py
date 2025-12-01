import pandas as pd
import random
from faker import Faker
import os
import re
import time

# 한국어 및 영어 가짜 데이터 생성기 초기화
fake_ko = Faker('ko_KR')
fake_en = Faker('en_US')

# ==========================================
# 1. 헬퍼 함수들
# ==========================================

def get_random_job(is_foreigner):
    jobs_kr = ["사원", "주임", "대리", "과장", "차장", "부장", "팀장", "실장", "본부장", "이사", "상무", "전무", "대표이사", "연구원", "선임연구원"]
    jobs_en = ["Staff", "Associate", "Manager", "Senior Manager", "Director", "VP", "SVP", "CEO", "CTO", "CFO", "Developer", "Designer"]
    return random.choice(jobs_en) if is_foreigner else random.choice(jobs_kr)

def get_random_age_group():
    age = random.randint(20, 59)
    return f"{age // 10 * 10}대"

def get_random_gender():
    return random.choice(["남성", "여성"])

def get_random_location(is_foreigner):
    if is_foreigner:
        country = fake_en.country()
        region = fake_en.city()
    else:
        country = "대한민국"
        regions_capital = ["서울", "경기", "인천"]
        regions_others = ["부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
        if random.random() < 0.6:
            region = random.choice(regions_capital)
        else:
            region = random.choice(regions_others)
    return country, region

def make_company_email(name, company_name):
    if not company_name: return None
    if re.search('[가-힣]', company_name):
        domain = fake_en.domain_name()
    else:
        clean_comp = company_name.lower()
        suffixes = ['inc', 'corp', 'ltd', 'llc', 'co', 'korea', 'group']
        for s in suffixes:
            clean_comp = re.sub(fr'\b{s}\b', '', clean_comp)
        domain_keyword = re.sub(r'[^a-z0-9]', '', clean_comp)
        if not domain_keyword: domain_keyword = "company"
        domain = f"{domain_keyword}.com"
    user_id = fake_en.user_name()
    return f"{user_id}@{domain}"

def create_random_phone():
    p = fake_ko.phone_number()
    case = random.choice([1, 2, 3, 4, 5])
    if case == 1: return p.replace("-", "") 
    elif case == 2: return p.replace("-", " ") 
    elif case == 3: return f"+82 {p[1:]}" 
    elif case == 4: return None 
    else: return p

def create_messy_company(company_name):
    if not company_name: return company_name
    case = random.choice([1, 2, 3, 4, 5])
    if case == 1: return company_name.upper()
    elif case == 2: return company_name.lower()
    elif case == 3: return f"{company_name} Inc."
    elif case == 4: return f"{company_name} Korea"
    elif case == 5: return company_name.replace(" ", "")
    return company_name

def create_large_sample():
    start_time = time.time()
    
    # 경로 설정
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(current_script_path)
    data_dir = os.path.join(parent_path, "DATA")
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    full_path = os.path.join(data_dir, "참가자_테스트_Sample.xlsx")

    # ==========================================
    # 목표 수량 설정
    # ==========================================
    TARGET_ATTENDEE = 20000  # 참가자 2만명
    TARGET_BOOTH = 5000      # 부스 5천개
    
    print(f"🚀 대량 데이터 생성을 시작합니다. (목표: {TARGET_ATTENDEE + TARGET_BOOTH}건)")
    print("⏳ 생성 중... (약 10~30초 소요됩니다)")

    # ==========================================
    # 2. 참가자 명단 생성 (20,000명)
    # ==========================================
    columns_attendee = [
        "이름 (Name)", "소속 (Company)", "직급", "이메일 (E-mail)", "휴대폰 (Phone)", 
        "성별", "나이대", "국가", "지역", "비고 (테스트 의도)"
    ]

    rows_attendee = []
    base_people = []
    
    famous_companies = {
        '삼성전자': 'Samsung', 'LG전자': 'LGE', '현대자동차': 'Hyundai', 
        'SK텔레콤': 'SKT', '네이버': 'Naver', '카카오': 'Kakao', 
        '쿠팡': 'Coupang', '배달의민족': 'Woowa', '토스': 'Toss',
        'Google Korea': 'Google', 'Apple Korea': 'Apple'
    }
    company_keys = list(famous_companies.keys())

    # (1) Base 데이터 생성 (약 70%는 정상 데이터)
    base_count = int(TARGET_ATTENDEE * 0.7)
    
    for _ in range(base_count):
        is_foreigner = random.random() < 0.3
        
        if is_foreigner:
            name = fake_en.name()
            company = fake_en.company()
            email = make_company_email(name, company)
        else:
            name = fake_ko.name()
            if random.random() < 0.5:
                ko_comp = random.choice(company_keys)
                en_comp = famous_companies[ko_comp]
                company = ko_comp
                email = make_company_email(name, en_comp)
            else:
                company = fake_ko.company()
                email = fake_ko.email()
        
        phone = create_random_phone()
        gender = get_random_gender()
        job = get_random_job(is_foreigner)
        age = get_random_age_group()
        country, region = get_random_location(is_foreigner)

        # Base 리스트에 저장 (나중에 중복 생성용)
        p_data = [name, company, job, email, phone, gender, age, country, region]
        base_people.append(p_data)
        rows_attendee.append(p_data + ["[랜덤] 정상"])

    # (2) Dirty 데이터 생성 (나머지 30%는 중복/누락/오타)
    dirty_count = TARGET_ATTENDEE - base_count
    
    for _ in range(dirty_count):
        target = random.choice(base_people)
        name, company, job, email, phone, gender, age, country, region = target
        
        case = random.choice(['dup', 'missing_email', 'missing_phone', 'no_info', 'typo_company', 'typo_name'])
        row_data = []
        note = ""
        
        if case == 'dup':
            row_data = [name, company, job, email, phone, gender, age, country, region]
            note = "[랜덤] 완전 중복"
        elif case == 'missing_email':
            row_data = [name, company, job, None, phone, gender, age, country, region]
            note = "[랜덤] 이메일 누락"
        elif case == 'missing_phone':
            row_data = [name, company, job, email, None, gender, age, country, region]
            note = "[랜덤] 전화번호 누락"
        elif case == 'no_info':
            row_data = [name, company, None, email, phone, gender, age, country, None]
            note = "[랜덤] 직급/지역 누락"
        elif case == 'typo_company':
            row_data = [name, create_messy_company(company), job, email, phone, gender, age, country, region]
            note = "[랜덤] 회사명 변형"
        elif case == 'typo_name':
            messy_name = " ".join(list(name)) if len(name) < 5 else name
            row_data = [messy_name, company, job, email, phone, gender, age, country, region]
            note = "[랜덤] 이름 공백"

        rows_attendee.append(row_data + [note])

    df1 = pd.DataFrame(rows_attendee, columns=columns_attendee)

    # ==========================================
    # 3. 부스 신청 생성 (5,000개)
    # ==========================================
    columns_booth = [
        "Organization", "Representative", "Job Title", "Contact No.", "Email Address", 
        "Country", "Location", "테스트 의도"
    ]
    
    rows_booth = []
    base_booths = []
    
    # (1) Base 부스 (70%)
    base_booth_count = int(TARGET_BOOTH * 0.7)
    
    for _ in range(base_booth_count):
        comp = random.choice(company_keys) if random.random() < 0.3 else fake_en.company()
        rep = fake_en.name()
        job = random.choice(["CEO", "Marketing Director", "Sales Manager", "VP", "Head of Booth"])
        phone = create_random_phone()
        email = make_company_email(rep, comp)
        is_foreign = random.random() < 0.4
        country, city = get_random_location(is_foreign)
        
        b_data = [comp, rep, job, phone, email, country, city]
        base_booths.append(b_data)
        rows_booth.append(b_data + ["[랜덤] 정상"])

    # (2) Dirty 부스 (30%)
    dirty_booth_count = TARGET_BOOTH - base_booth_count
    
    for _ in range(dirty_booth_count):
        target = random.choice(base_booths)
        comp, rep, job, phone, email, country, city = target
        case = random.choice(['clean', 'dirty_comp', 'missing_info'])
        
        if case == 'clean':
            rows_booth.append([comp, rep, job, phone, email, country, city, "[랜덤] 완전 중복"])
        elif case == 'dirty_comp':
            rows_booth.append([create_messy_company(comp), rep, job, phone, email, country, city, "[랜덤] 회사명 변형"])
        elif case == 'missing_info':
            rows_booth.append([comp, rep, job, None, None, country, city, "[랜덤] 연락처 누락"])

    df2 = pd.DataFrame(rows_booth, columns=columns_booth)

    # ==========================================
    # 4. 파일 저장
    # ==========================================
    print(f"💾 엑셀 파일로 저장 중... (데이터가 많아 시간이 조금 걸립니다)")
    
    try:
        with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
            df1.to_excel(writer, sheet_name="참가자_명단", index=False)
            df2.to_excel(writer, sheet_name="부스_신청", index=False)
        
        elapsed_time = time.time() - start_time
        print(f"✅ '{full_path}' 생성 완료! (소요시간: {elapsed_time:.2f}초)")
        print(f"   - 참가자_명단: {len(df1)}행")
        print(f"   - 부스_신청: {len(df2)}행")
        
    except PermissionError:
        print("\n❌ 파일 저장 실패! 엑셀 파일이 열려있다면 닫고 다시 실행해주세요.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")

if __name__ == "__main__":
    create_large_sample()