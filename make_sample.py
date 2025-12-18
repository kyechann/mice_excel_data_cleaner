import pandas as pd
import random
from faker import Faker
import os
import re
import time
from datetime import datetime, timedelta

fake_ko = Faker("ko_KR")
fake_en = Faker("en_US")

# =========================
# 설정값 (여기만 조절하면 됨)
# =========================
TARGET_ROWS = 20000
OUTPUT_FILENAME = "참가자_SUDO.xlsx"
SHEET_NAME = "DB규격_10컬럼"  # ✅ 시트명만 10컬럼으로 변경(원하면 원래대로 둬도 됨)

# 비율 (합이 1.0이 아니어도 됨: 내부에서 자동 정규화)
RATIO_CLEAN = 0.72        # 정상
RATIO_DUP_FULL = 0.12     # 완전 중복(행 그대로 복제)
RATIO_DUP_PARTIAL = 0.10  # 부분 중복(이름/전화/이메일 중 일부 동일)
RATIO_MISSING = 0.04      # 이메일/전화 누락 강화
RATIO_FORMAT_SHAKE = 0.02 # 전화/이메일 포맷 흔들기 강화

# ✅ (변경) 컬럼 2개 추가
COLUMNS = ["이름", "소속", "직함", "전화번호", "이메일", "참가구분", "등록일", "비고", "평점(0-10)", "리뷰(코멘트)"]

JOBS_KR = ["사원", "주임", "대리", "과장", "차장", "부장", "팀장", "실장", "본부장", "이사", "상무", "전무", "대표", "연구원"]
JOBS_EN = ["Staff", "Associate", "Manager", "Senior Manager", "Director", "VP", "SVP", "CEO", "CTO", "CFO"]
ATTEND_TYPES = ["일반참가", "VIP", "스피커", "부스담당", "미디어", "스태프", "초청", "학생"]

NOTES = ["", None, "현장등록", "사전등록", "식사: 채식", "식사: 알레르기", "휠체어 지원", "동반 1인", "결제 대기", "재참가"]
FAMOUS_COMPANIES = ["삼성전자", "LG전자", "현대자동차", "SK텔레콤", "네이버", "카카오", "쿠팡", "배달의민족", "토스",
                    "KT", "포스코", "한화", "CJ", "아모레퍼시픽"]

def normalize_weights(w):
    s = sum(w.values())
    if s <= 0:
        raise ValueError("비율 합이 0입니다.")
    return {k: v / s for k, v in w.items()}

def random_date_str(days_back=365):
    d = datetime.now() - timedelta(days=random.randint(0, days_back))
    return d.strftime("%Y-%m-%d")

def create_company():
    return random.choice(FAMOUS_COMPANIES) if random.random() < 0.6 else fake_ko.company()

def create_name(is_foreigner):
    return fake_en.name() if is_foreigner else fake_ko.name()

def create_job(is_foreigner):
    return random.choice(JOBS_EN) if is_foreigner else random.choice(JOBS_KR)

def phone_to_digits(p):
    if p is None:
        return None
    return re.sub(r"[^0-9]", "", str(p))

def format_phone_messy(digits: str | None):
    if not digits:
        return None
    # digits 예: 01012345678
    case = random.choice([1, 2, 3, 4, 5, 6])
    if case == 1:
        return digits
    if case == 2:
        # 010-1234-5678
        if len(digits) == 11:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        return digits
    if case == 3:
        # 010 1234 5678
        if len(digits) == 11:
            return f"{digits[:3]} {digits[3:7]} {digits[7:]}"
        return digits
    if case == 4:
        # +82 10xxxx
        if digits.startswith("0"):
            return "+82 " + digits[1:]
        return "+82 " + digits
    if case == 5:
        # 앞/뒤 공백
        return f" {digits} "
    # case 6: 일부 누락(테스트)
    return digits[:-1] if len(digits) > 5 else digits

def create_phone(base_allow_none=True):
    # Faker 기반 생성 후 디짓으로 표준화 -> 다시 흔들기
    p = fake_ko.phone_number()
    digits = phone_to_digits(p)
    if base_allow_none and random.random() < 0.08:
        return None
    return format_phone_messy(digits)

def create_email(company):
    # 20% 누락
    if random.random() < 0.20:
        return None
    user = fake_en.user_name()

    if re.search(r"[가-힣]", str(company)):
        domain = fake_en.domain_name()
    else:
        clean = re.sub(r"[^a-z0-9]", "", str(company).lower())
        domain = (clean if clean else "company") + ".com"

    email = f"{user}@{domain}"

    # 포맷 흔들기(일부는 대문자/공백)
    case = random.choice([1, 2, 3, 4, 5])
    if case == 1:
        return email
    if case == 2:
        return email.upper()
    if case == 3:
        return " " + email + " "
    if case == 4:
        # dot 제거 등 약간 깨진 이메일(테스트)
        return email.replace(".", "")
    return email.lower()

# ✅ (추가) 평점/리뷰 생성
def get_rating_and_review():
    rating = random.choices(range(11), weights=[1,1,2,2,3,5,8,15,20,25,18])[0]

    reviews_high = [
        "행사 운영이 매우 매끄러웠습니다.", "유익한 시간이었습니다.", "네트워킹 기회가 좋았어요.",
        "내년에도 꼭 참가하고 싶네요.", "강연 내용이 알찼습니다.", "전반적으로 만족스러운 행사였습니다.",
        "Great event!", "Excellent organization.", "Insightful sessions."
    ]
    reviews_mid = [
        "그럭저럭 괜찮았습니다.", "무난한 행사였습니다.", "일부 세션은 지루했어요.",
        "식사가 조금 아쉬웠습니다.", "와이파이가 느렸어요.", "Not bad.", "Average experience."
    ]
    reviews_low = [
        "최악의 행사였습니다.", "시간 낭비였네요.", "준비가 너무 미흡합니다.",
        "등록 대기 시간이 너무 길었습니다.", "Terrible experience.", "다시는 안 옵니다."
    ]

    if rating >= 9:
        review = random.choice(reviews_high)
    elif rating >= 7:
        review = random.choice(reviews_high + reviews_mid)
    elif rating >= 4:
        review = random.choice(reviews_mid)
    else:
        review = random.choice(reviews_low)

    # 20% 확률로 리뷰 미작성
    if random.random() < 0.2:
        review = None

    return rating, review

def create_clean_row():
    is_foreigner = random.random() < 0.25
    name = create_name(is_foreigner)
    company = create_company()
    job = create_job(is_foreigner)

    phone = create_phone(base_allow_none=True)
    email = create_email(company)

    attend_type = random.choice(ATTEND_TYPES)
    reg_date = random_date_str(365)
    note = random.choice(NOTES)

    # ✅ (추가) 평점/리뷰
    rating, review = get_rating_and_review()

    return [name, company, job, phone, email, attend_type, reg_date, note, rating, review]

def make_partial_dup(base_row):
    """
    부분 중복: (이름/전화/이메일) 중 1~2개를 동일하게 유지하고,
    나머지는 랜덤하게 바꾸어 '부분 중복' 상황을 만든다.
    """
    name, company, job, phone, email, attend_type, reg_date, note, rating, review = base_row  # ✅ (변경)

    keep = set(random.sample(["이름", "전화번호", "이메일"], k=random.choice([1, 2])))

    is_foreigner = random.random() < 0.25
    new_name = name if "이름" in keep else create_name(is_foreigner)
    new_company = company if random.random() < 0.4 else create_company()
    new_job = job if random.random() < 0.6 else create_job(is_foreigner)

    # 전화: 유지면 포맷만 조금 흔들 수도 있음
    if "전화번호" in keep:
        digits = phone_to_digits(phone)
        new_phone = format_phone_messy(digits) if random.random() < 0.6 else phone
    else:
        new_phone = create_phone(base_allow_none=True)

    # 이메일: 유지면 공백/대소문자 정도만 흔들기
    if "이메일" in keep:
        if email is None:
            new_email = None
        else:
            new_email = email
            if random.random() < 0.6:
                new_email = (" " + new_email + " ") if random.random() < 0.5 else new_email.upper()
    else:
        new_email = create_email(new_company)

    new_attend = attend_type if random.random() < 0.5 else random.choice(ATTEND_TYPES)
    new_date = reg_date if random.random() < 0.7 else random_date_str(365)
    new_note = "[테스트] 부분중복" if random.random() < 0.8 else random.choice(NOTES)

    # ✅ (추가) 평점/리뷰도 일부는 유지/일부는 새로 생성
    if random.random() < 0.6:
        new_rating, new_review = rating, review
    else:
        new_rating, new_review = get_rating_and_review()

    return [new_name, new_company, new_job, new_phone, new_email, new_attend, new_date, new_note, new_rating, new_review]

def make_missing_row(base_row):
    row = base_row.copy()
    # 이메일/전화 누락을 강하게 발생
    if random.random() < 0.6:
        row[3] = None  # 전화번호
    if random.random() < 0.75:
        row[4] = None  # 이메일

    # ✅ (추가) 리뷰/평점도 일부 누락시키기
    if random.random() < 0.35:
        row[8] = None  # 평점
    if random.random() < 0.55:
        row[9] = None  # 리뷰

    row[7] = "[테스트] 누락값"
    return row

def make_format_shake_row(base_row):
    row = base_row.copy()
    # 전화 포맷 흔들기
    digits = phone_to_digits(row[3])
    row[3] = format_phone_messy(digits)

    # 이메일 포맷 흔들기
    if row[4] is not None:
        e = str(row[4]).strip()
        row[4] = random.choice([e.upper(), " " + e + " ", e.replace(".", ""), e.lower()])

    row[7] = "[테스트] 형식흔들기"
    return row

def main():
    start = time.time()

    weights = normalize_weights({
        "clean": RATIO_CLEAN,
        "dup_full": RATIO_DUP_FULL,
        "dup_partial": RATIO_DUP_PARTIAL,
        "missing": RATIO_MISSING,
        "format": RATIO_FORMAT_SHAKE,
    })

    # 저장 경로: 현재 스크립트 상위 폴더/DATA
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(current_script_path)
    data_dir = os.path.join(parent_path, "DATA")
    os.makedirs(data_dir, exist_ok=True)
    full_path = os.path.join(data_dir, OUTPUT_FILENAME)

    print(f"🚀 생성 시작: {TARGET_ROWS:,}행 / 10컬럼(DB규격 + 평점/리뷰)")
    print(f"   - clean={weights['clean']:.2%}, full_dup={weights['dup_full']:.2%}, partial_dup={weights['dup_partial']:.2%}, missing={weights['missing']:.2%}, format={weights['format']:.2%}")

    # base pool(정상 데이터) 만들어두고 중복/부분중복은 여기에서 뽑아서 생성
    base_pool_size = max(2000, int(TARGET_ROWS * 0.25))
    base_pool = [create_clean_row() for _ in range(base_pool_size)]

    rows = []
    for _ in range(TARGET_ROWS):
        pick = random.random()
        # 누적확률 방식
        acc = 0.0

        acc += weights["clean"]
        if pick < acc:
            rows.append(create_clean_row())
            continue

        acc += weights["dup_full"]
        if pick < acc:
            # 완전 중복
            rows.append(random.choice(base_pool).copy())
            if rows[-1][7] is None or rows[-1][7] == "":
                rows[-1][7] = "[테스트] 완전중복"
            continue

        acc += weights["dup_partial"]
        if pick < acc:
            rows.append(make_partial_dup(random.choice(base_pool)))
            continue

        acc += weights["missing"]
        if pick < acc:
            rows.append(make_missing_row(random.choice(base_pool)))
            continue

        # format shake
        rows.append(make_format_shake_row(random.choice(base_pool)))

    df = pd.DataFrame(rows, columns=COLUMNS)

    print("💾 엑셀 저장 중...")
    with pd.ExcelWriter(full_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    elapsed = time.time() - start
    print(f"✅ 완료! {elapsed:.2f}초")
    print(f"📌 저장 위치: {full_path}")
    print(f"📌 컬럼: {', '.join(COLUMNS)}")

if __name__ == "__main__":
    main()