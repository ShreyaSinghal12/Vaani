"""Indian-style training messages generated from templates.

Why: the Kaggle datasets have almost no Indian bank alerts, so a model trained
only on them calls "Rs 2,450 debited from A/c XX4521" spam. These templates
teach it what normal alerts look like, plus the common Indian scam formats.

These rows are SYNTHETIC. They are used for training only, never for testing,
and the report says how many were used. Replace / extend them with real
messages in ml/data/india_real.csv (columns: text,label  label = ham | scam).

    python -m ml.augment_india      # writes ml/data/india_synthetic.csv
"""
import csv
import random
from pathlib import Path

random.seed(7)
OUT = Path(__file__).parent / "data" / "india_synthetic.csv"

BANKS = [("SBI", "State Bank of India"), ("PNB", "Punjab National Bank"), ("HDFC Bank", "HDFC Bank"),
         ("ICICI Bank", "ICICI Bank"), ("Indian Bank", "Indian Bank"), ("Canara Bank", "Canara Bank"),
         ("Bank of Baroda", "Bank of Baroda"), ("Union Bank", "Union Bank of India"), ("Punjab & Sind Bank", "Punjab & Sind Bank")]
MERCHANTS = ["AMAZON", "FLIPKART", "SWIGGY", "KIRANA STORE", "IRCTC", "JIO RECHARGE", "PETROL PUMP", "MEDICAL STORE", "ZOMATO", "DMART"]
HELPLINES = ["1800 1234", "1800 1800", "1800 202 6161", "1800 1080", "18004250000", "1800 425 0018"]
SCAM_HOSTS = ["{b}-kyc-update.in", "{b}-verify.online", "secure-{b}.xyz", "{b}-rewards.top", "{b}kyc.site", "bit.ly/{b}-kyc", "tinyurl.com/{b}-pan", "{b}-netbank.co"]


def amt():
    return f"{random.choice([99, 120, 250, 499, 800, 1200, 2450, 3200, 4999, 15000, 25000]):,}.{random.choice(['00', '50', '75'])}"


def acct():
    return f"XX{random.randint(1000, 9999)}"


def date():
    return f"{random.randint(1, 28):02d}-{random.randint(1, 12):02d}-26"


def otp():
    return str(random.randint(100000, 999999))


def ham():
    short, name = random.choice(BANKS)
    t = random.choice([
        "Rs {a} debited from A/c {ac} on {d} for UPI/{m}. Not you? Call {h} - {s}",
        "A/c {ac} credited with Rs {a} on {d} by NEFT. Avl Bal Rs {a2}. -{s}",
        "Dear Customer, INR {a} withdrawn at ATM from A/c {ac} on {d}. If not done by you call {h}. {s}",
        "{o} is your OTP for txn of Rs {a} at {m}. Do not share it with anyone. {s}",
        "OTP for your {s} net banking login is {o}. {s} never asks for OTP. Do not share.",
        "Never share OTP/password with anyone. {o} is OTP for {s} card {ac} transaction of Rs {a}.",
        "{s}: EMI of Rs {a} for loan a/c {ac} is due on {d}. Please keep sufficient balance.",
        "{s}: Your auto-debit of Rs {a} for {m} could not be processed due to insufficient balance.",
        "{s}: NACH mandate of Rs {a} failed on {d} due to insufficient funds in A/c {ac}.",
        "Dear Customer, your KYC is due for periodic update. Please visit your home branch with Aadhaar and PAN. -{s}",
        "{s}: Your debit card ending {c4} has been blocked as requested. For help call {h}.",
        "Credit card {ac}: Total amount due Rs {a}, minimum due Rs {a3}. Pay by {d} to avoid charges. -{s}",
        "Your A/c {ac} is credited by Rs {a} on {d} (PM-KISAN). -{s}",
        "Dear UPI user A/C {ac} debited by {a} on date {d} trf to {m}. If not u? call {h}. -{s}",
        "{s}: Cheque no {c6} for Rs {a} presented in A/c {ac} has been cleared on {d}.",
        "Interest of Rs {a3} credited to your savings A/c {ac} for the quarter. -{s}",
        "Aapke khate {ac} se Rs {a} UPI dwara kate gaye, {d}. Aapne nahi kiya? {h} par call karein. -{s}",
        "Aapka OTP {o} hai. Ise kisi ke saath share na karein. -{s}",
    ])
    return t.format(a=amt(), a2=amt(), a3=random.choice(["310.00", "500.00", "1,250.00"]), ac=acct(), d=date(),
                    m=random.choice(MERCHANTS), h=random.choice(HELPLINES), s=short, o=otp(),
                    c4=random.randint(1000, 9999), c6=random.randint(100000, 999999))


def scam():
    short, name = random.choice(BANKS)
    slug = short.split()[0].lower()
    host = random.choice(SCAM_HOSTS).format(b=slug)
    phone = f"{random.choice([6, 7, 8, 9])}{random.randint(100000000, 999999999)}"
    t = random.choice([
        "Dear {s} customer, your KYC has expired. Update now at {u} or your account will be blocked today.",
        "{s}: Your account is suspended due to incomplete PAN. Click {u} to activate within 24 hours.",
        "URGENT: Your {s} debit card will be blocked tonight. Call {p} immediately to unblock.",
        "Dear user, your {s} YONO/netbanking will be deactivated. Update KYC: {u}",
        "Congratulations! You have won Rs {a} cashback from {s}. Claim now: {u}",
        "Your {s} reward points worth Rs {a} expire today. Redeem at {u}",
        "{s} ALERT: Share the OTP received on your phone with our officer to stop account closure.",
        "Rs {a} has been credited to your account by mistake. Please return it using this link {u}",
        "You have received Rs {a}. Enter your UPI PIN to receive the money.",
        "Dear customer install AnyDesk app so our {s} executive can complete your KYC update.",
        "{s}: KYC pending. Download our KYC app from {u}/KYC.apk to avoid account closure.",
        "Income tax refund of Rs {a} approved. Submit your account details at {u}",
        "Your electricity connection will be cut tonight at 9.30 pm. Call officer {p} immediately.",
        "Aapka {s} KYC aaj band ho jayega. Turant update karein: {u}",
        "{s}: aapka ATM card block ho gaya hai. OTP bataye aur card chalu karwaye. Call {p}",
        "Dear customer, your {s} credit card limit increased. Verify at {u} within 24 hours.",
        "Your parcel is on hold. Pay Rs 25 redelivery fee at {u} today.",
        "Part time job, earn Rs {a} daily from home. WhatsApp {p}",
    ])
    return t.format(s=short, u=host, p=phone, a=amt())


def main():
    rows = [(ham(), "ham") for _ in range(700)] + [(scam(), "scam") for _ in range(450)]
    rows = list(dict.fromkeys(rows))  # drop exact repeats
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")


if __name__ == "__main__":
    main()
