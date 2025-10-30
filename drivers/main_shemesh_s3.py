# ========================================================
# License: Personal Use Only  
# This file (`main_shemesh_s3.py`) is licensed for **personal use only**.  
# You may **not** modify, edit, or alter this file in any way.  
# Commercial use is strictly prohibited.  
# If you wish to use this file for business or organizational purposes,  
# please contact the author.  
# ========================================================

# משתנה גלובלי שמציין את גרסת התוכנה למעקב אחרי עדכונים
VERSION = "31/10/2025"

######################################################################################################################

# סיכום קצר על התוצאות המעשיות של הכפתורים בקוד הזה
# לחיצה על שתי הכפתורים בו זמנית כאשר מדליקים את המכשיר: עדכון תוכנת המכשיר
# אם כפתור המיקומים לחוץ בשעת הכניסה לתוכנה: עדכון השעון מהרשת 

# הבסיס של החישובים הגיע מכאן
# https://github.com/peterhinch/micropython-samples/tree/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy
# לגבי בעיות עם המסך שבס"ד נפתרו ראו כאן
# https://github.com/Xinyuan-LilyGO/T-Display-S3/issues/300

import time, math, machine, utime, esp32, network, ntptime, os, ujson
from math import sin, cos, tan, radians, degrees
from machine import I2C, SoftI2C, Pin, ADC, PWM, RTC
import gc # חשוב נורא לניקוי הזיכרון
from halacha_clock.sun_moon_sgb import RiSet  # ספריית חישובי שמש
from halacha_clock.moonphase_sgb import MoonPhase  # ספריית חישובי שלב הירח
from halacha_clock.ds3231 import DS3231 # שעון חיצוני
from halacha_clock import mpy_heb_date # לחישוב תאריך עברי מתאריך לועזי. ספרייה שלי
from halacha_clock import bme280 # לחיישן טמפרטורה ולחות


# פונטים
import halacha_clock.miriam20 as FontHeb20
import halacha_clock.miriam25 as FontHeb25
import halacha_clock.miriam30 as FontHeb30
import halacha_clock.miriam40 as FontHeb40

# למסך
import halacha_clock.tft_config as tft_config
import s3lcd

# הגדרת המסך
tft = tft_config.config(rotation=3) # כיוון סיבוב התצוגה שאני רוצה בגלל הבליטה של השעון החיצוני
tft.init() # כך חייבים לעשות


####################################################################3


# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח

    
# משתנה למעקב אחר מצב הכוח כלומר האם המכשיר כבוי או פועל
# המשמעות של זה מגיעה לידי ביטוי בפונקצייה הראשית: main
# זה משתנה חשוב נורא
power_state = True

# משתנה מאוד חשוב שמגדיר האם המכשיר ייכנס למצב שינה אוטומטי לאחר מספר דקות של פעילות
# המשתנה הזה מוגדר בתוך פונקציית main_halach_clock לפי אם שבת או יום חול
automatic_deepsleep = False

##########################################################################################################
# הגדרת ADC על GPIO4 לצורך קריאת כמה מתח המכשיר מקבל
adc = ADC(Pin(4))  
adc.atten(ADC.ATTN_11DB)  # קביעת טווח מתח עד כ-3.6V
adc.width(ADC.WIDTH_12BIT)  # רזולוציה של 12 ביט (ערכים בין 0 ל-4095)

# משתנה חשוב שמגדיר מה המתח המירבי שיכול להיות לסוללה הפנימית ומעל זה קובעים שסימן שמחובר לחשמל או למקור מתח חיצוני
max_battery_v = 4.55

# משתנה מאוד חשוב ששומר את המתח בשנייה הקודמת כדי להשוות אליו ולבדוק האם חובר חשמל או נותק
# זה מתעדכן כל שנייה מחדש בפונקציית מיין-מיין
last_voltage = None # שומר את המתח האחרון שנמדד
last_battery_percentage = None # שומר את אחוזי הסוללה האחרונים שנמדדו
last_is_charging = None # שולט על כל הדברים שדורשים לדעת האם כעת המכשיר מחובר לחשמל

# פונקציה למדידת מתח סוללה מתוך ממוצע של 10 קריאות מתח
def read_battery_voltage(samples=10):
    total = 0
    for _ in range(samples):
        total += adc.read()
        time.sleep(0.005)  # חצי מילישנייה בין קריאות
    avg = total / samples
    voltage = (avg / 4095) * 3.6 * 2  # המרה למתח אמיתי
    return voltage

# כדי לדעת אם מחובר כעת לחשמל, כדאי לבדוק מספר קריאות רצופות
def is_charging_function(voltage, threshold=max_battery_v, stable_reads=5):
    count = 0
    for _ in range(stable_reads):
        if read_battery_voltage() > threshold:
            count += 1
        time.sleep(0.01)
    return count >= stable_reads

def get_battery_percentage(voltage, min_voltage=3.6, max_voltage=4.4):
    """ מחשב אחוז סוללה על פי המתח הנמדד ומונע ערכים מחוץ לטווח 0%-100% """
    percentage = ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100
    return round(max(0, min(100, percentage)))


##############################################3

# לאחר מכן להפעיל PWM כדי לשלוט במידת התאורה האחורית של המסך
BACKLIGHT = PWM(Pin(38, Pin.OUT), freq=2000) # ה: פרק, חשוב מאוד לגבי התדר וקובע גם את סוג הצפצופים שנשמעים בעיקר כשמחובר לחשמל
PWM_MAX = 1023 # תאורה הכי גבוהה
PWM_MIN = 0 # התאורה כבוייה

#############################################

# משתנה גלובלי שמפנה לשעון הפנימי של המכשיר
rtc_system = machine.RTC()

###########################################################################################################

#הגדרת ערוצי I2C הגדרת האם ולאיפה מחוברים DS3231 שזה שעון חיצוני וגם BME280 שזה חיישן טמפרטורה

# יצירת אובייקט I2C עם נגדי pull-up פנימיים עבור הפינים שהלחמתי במכשיר
# אם מגדירים את הפינים ישירות בלי נגדים פנימיים זה עושה כאילו יש הרבה התקני I2C מחוברים למרות שבאמת אין
solder_pin_plus = Pin(17, Pin.OUT, value=1) # חייבים קודם להפעיל כך את הפין החיובי המולחם אחרת החיישן שמחובר ל I2C המולחם לא יעבוד
solder_pin_scl = Pin(16, Pin.OPEN_DRAIN, pull=Pin.PULL_UP)
solder_pin_sda = Pin(21, Pin.OPEN_DRAIN, pull=Pin.PULL_UP)
solder_pins_i2c = SoftI2C(scl=solder_pin_scl, sda=solder_pin_sda)

# זה I2C הרגיל המובנה במכשיר והוא כבר יש לו נגדים מובנים
original_i2c = I2C(scl=Pin(44), sda=Pin(43))

######################################################################################################

# משתנים גלובליים של שמות ההתקנים שיכולים להיות מחוברים ליציאת I2C עבור תוכנה זו
ds3231_bitname = 0x68 
bme280_bitname = 0x76 # או 0x77 רק כאשר מחברים את הפין SDO ל-VCC

# פונקצייה מאוד חשובה שבודקת האם ולאיפה מחוברים DS3231 או BME280 מתוך יציאות I2C שהוגדרו לעיל
def check_i2c_device(device_bitname):
    
    # סריקת כל אחד מ I2C כדי לדעת אילו התקנים מחובר לכל אחד
    original_i2c_devices = original_i2c.scan()
    solder_pins_i2c_devices = solder_pins_i2c.scan()
  
    # משתנים ששומרים תשובה בנכון או לא נכון לשאלה האם DS3231 ו/או BME280 מחוברים או לא מחוברים
    is_device_connected = device_bitname in original_i2c_devices or device_bitname in solder_pins_i2c_devices
    
    # אם מחובר DS3231, צריך לבדוק לאיפה
    if is_device_connected:
        # הגדרת כתובת I2C נכונה עבור SD3231 ושם היציאה שאליה מחובר
        device_exit, device_exit_name = (original_i2c, "יציאה חיצונית") if device_bitname in original_i2c_devices else (solder_pins_i2c, "פינים מולחמים")
        
    else:
        device_exit, device_exit_name = None, None
      
  
    return is_device_connected, device_exit, device_exit_name



# קריאה לפונקצייה שהוגדרה לעיל ובדיקה ראשונית בתחילת ריצת התוכנה האם BME280 מחובר ולאיפה
is_bme280_connected, bme280_exit, bme280_exit_name = check_i2c_device(bme280_bitname)

# אם מחובר jhhai BME280 אז מוגדר אובייקט BME280 לצורך מד הטמפרטורה ואם לא מחובר אז המשתנה מוגדר להיות False
bme = bme280.BME280(i2c=bme280_exit) if is_bme280_connected else False


############################################################################################

# במיקרופייתון אין פונקציית time.strftime ולכן מחליף כך
def format_time(time_tuple, with_seconds = True, with_date=False):
    """המרת tuple של זמן למחרוזת בסגנון HH:MM:SS,  או '%H:%M:%S %d/%m/%Y'"""
    t = time_tuple
    return f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d} {t[2]:02d}/{t[1]:02d}/{t[0]}" if with_date else f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d}" if with_seconds else f"{t[3]:02d}:{t[4]:02d}"

# פונקצייה להמרת זמן מ-שניות ל- סטרינג שעות דקות ושניות, או רק ל- סטרינג דקות ושניות שבניתי בסיוע רובי הבוט
def convert_seconds(seconds, to_hours=False):
    # המרה לערך מוחלט כדי לא להחזיר סימן מינוס
    seconds = abs(seconds)
    # חישוב מספר הדקות והשניות שיש בשעה אחת, והדפסתם בפורמט של דקות ושניות
    if to_hours:
        return f'{seconds // 3600 :02.0f}:{(seconds % 3600) // 60 :02.0f}:{seconds % 60 :02.0f}'
    else:
        return f'{seconds // 60 :02.0f}:{seconds % 60 :02.0f}'


def calculate_delta_t(year):
    """
    Calculate ΔT (seconds) for years 2000-2500 using the polynomial expressions.
    https://eclipse.gsfc.nasa.gov/SEhelp/deltatpoly2004.html
    """
    y = float(year)
    
    if 2000 <= y < 2005:
        t = y - 2000
        dt = 63.86 + 0.3345*t - 0.060374*t**2 + 0.0017275*t**3 + 0.000651814*t**4 + 0.00002373599*t**5
    elif 2005 <= y < 2050:
        t = y - 2000
        dt = 62.92 + 0.32217*t + 0.005589*t**2
    elif 2050 <= y < 2150:
        u = (y - 1820)/100
        dt = -20 + 32*u**2 - 0.5628*(2150 - y)
    else:  # y >= 2150
        u = (y - 1820)/100
        dt = -20 + 32*u**2

    # Small lunar correction (not needed for 1955-2005, but outside this range we apply)
    if y < 1955 or y > 2005:
        dt += -0.000012932 * (y - 1955)**2

    return dt


# פונקצייה שמקבלת זמן כחותמן זמן ומחזירה את משוואת הזמן בדקות ליום זה
# לפי Meeus, בקירוב מצוין לשנים 2000–2100
# נבנתה על ידי צאט גיפיטי
def get_equation_of_time_from_timestamp(timestamp_input):
    
    # פונקצייה לקבלת זמן באלפי שנים מאז J2000.0 וגם יום יוליאני לצורך חישובים אסטרונומיים
    def get_julian_centuries_since_J2000_and_jd(timestamp):
        JD = timestamp / 86400.0 + 2440587.5
        JC = (JD - 2451545.0) / 36525.0
        return JC, JD
    
    # קבלת זמן באלפי שנים מאז J2000.0 לצורך החישובים, באמצעות הפונקצייה הנל
    T, JD = get_julian_centuries_since_J2000_and_jd(timestamp_input)

    # ואז ממשיכים כמו קודם:
    L0 = radians((280.46646 + 36000.76983 * T) % 360)
    e = 0.016708634 - 0.000042037 * T
    M = radians((357.52911 + 35999.05029 * T) % 360)
    y = tan(radians(23.439291 - 0.0130042 * T) / 2)
    y *= y
    equation_of_time_minutes = 4 * degrees(
        y * sin(2 * L0)
        - 2 * e * sin(M)
        + 4 * e * y * sin(M) * cos(2 * L0)
        - 0.5 * y * y * sin(4 * L0)
        - 1.25 * e * e * sin(2 * M)
    )
    
    equation_of_time_seconds = equation_of_time_minutes * 60
    
    return equation_of_time_seconds


# פונקצייה לחישוב זמן מקומי (לפי חצות שנתי ממוצע שהוא בשעה 12), לפי קו האורך הגיאוגרפי האמיתי 
def LMT_LST_EOT(utc_timestamp, longitude_degrees, LST_EOT = True):
    offset_seconds = int(240 * longitude_degrees)  # 4 דקות לכל מעלה
    lmt_seconds = int(utc_timestamp) + offset_seconds # חייבים לעשות אינט למנוע שגיאות במיקרופייתון
    lmt_tuple = time.gmtime(int(lmt_seconds))   # לא מוסיף הטיה מקומית
    local_mean_time_string = format_time(lmt_tuple)
    ####################################################################
    if LST_EOT:
        equation_of_time_seconds = get_equation_of_time_from_timestamp(utc_timestamp)
        lst_seconds = lmt_seconds + int(equation_of_time_seconds) # חייבים לעשות אינט למנוע שגיאות במיקרופייתון
        lst_tuple = time.gmtime(int(lst_seconds))
        local_solar_time_string = format_time(lst_tuple)
        equation_of_time_string = f"{'+' if equation_of_time_seconds >0 else '-'}{convert_seconds(equation_of_time_seconds)}"
    else:
        local_solar_time_string, equation_of_time_string = "None","None"
    return local_mean_time_string, local_solar_time_string, equation_of_time_string

# פונקצייה לקבלת הפרש השעות המקומי מגריניץ בלי התחשבות בשעון קיץ
# יש אפשרות להגדיר טרו או פאלס האם זה שעון קיץ או לא. כברירת מחדל זה לא
# אפשר להגדיר האם רוצים את ההפרש בשעות או בשניות וברירת המחדל היא בשעות
def get_generic_utc_offset(longitude_degrees, dst=False, in_seconds = False):
    offset = abs(round(longitude_degrees/15)) % 24
    offset = -offset if longitude_degrees < 0 else offset
    offset = offset + 1 if dst else offset
    return offset * 3600 if in_seconds else offset
    
# פונקצייה להפיכת טקסט כדי שעברית תהיה משמאל לימין
def reverse(string):
    return "".join(reversed(string))

# מקבל מספר יום בשבוע לפי הנורמלי ומחזיר את מספר היום בשבוע לפי ההגדרות ב RTC
def get_rtc_weekday(weekday):
    rtc_weekday_dict = {1:6,2:0,3:1,4:2,5:3,6:4,7:5}
    return rtc_weekday_dict.get(weekday)

# מוציא את מספר היום בשבוע הנורמלי לפי סדר מתוך שעון המכשיר שמוגדר RTC
def get_normal_weekday(rtc_weekday):
    weekday_dict = {6:1,0:2,1:3,2:4,3:5,4:6,5:7}
    return weekday_dict.get(rtc_weekday)

# פונקצייה שמחזירה נכון או לא נכון האם כרגע נוהג שעון קיץ בישראל
# היא מתבססת על מה השעה והתאריך ברגע זה בשעון הפנימי של המיקרו בקר ולכן חייבים להגדיר אותו לפני שקוראים לפונקצייה זו
# שעון הקיץ מופעל בישראל בין יום שישי שלפני יום ראשון האחרון של חודש מרץ בשעה 02:00, לבין יום ראשון האחרון של חודש אוקטובר בשעה 02:00.
# השעה 2 בלילה של שינוי השעון הם בשעון ישראל ואילו שעון הבקר מוגדר לאיזור זמן גריניץ לכן הקדמתי בשעתיים לשעה 0 שעון גריניץ
def is_now_israel_DST():
    # קבלת השנה הנוכחית
    current_year = utime.localtime()[0]
    
    # חישוב יום ראשון האחרון של מרץ
    march_last_sunday = utime.mktime((current_year, 3, 31, 0, 0, 0, 0, 0, 0))
    while utime.localtime(march_last_sunday)[6] != get_rtc_weekday(1):
        march_last_sunday -= 86400  # מורידים יום
    
    # חישוב יום שישי שלפני יום ראשון האחרון של מרץ
    # אם יום ראשון האחרון הוא ה-31, אז יום שישי לפניו יהיה ה-29.
    last_friday_march = march_last_sunday - 2 * 86400  # מורידים 2 ימים (שישי)

    # חישוב יום ראשון האחרון של אוקטובר
    october_last_sunday = utime.mktime((current_year, 10, 31, 0, 0, 0, 0, 0, 0))
    while utime.localtime(october_last_sunday)[6] != get_rtc_weekday(1): 
        october_last_sunday -= 86400  # מורידים יום
    
    # השוואה בין הזמן הנוכחי לתאריכים של שעון קיץ
    current_time = utime.mktime(utime.localtime())
    
    # שעון קיץ פעיל בין יום שישי שלפני יום ראשון האחרון של מרץ ועד יום ראשון האחרון של אוקטובר
    if last_friday_march <= current_time < october_last_sunday:
        return True  # שעון קיץ פעיל
    else:
        return False  # לא פעיל


# פונקצייה לפריטת שעה בשבר עשרוני לשניות
# אחר כך אפשר להשתמש בפונקצייה הקודמת להמרת של השניות לשעות דקות ושניות בפורמט שעון
# פונקצייה זו יכולה להיות שימושים לצורך נתינת עלייה ישרה בפורמט של שעות דקות ושניות אך כרגע אין לה שימוש בקוד זה
def decimal_hours_to_seconds(decimal_hours):
    hours = int(decimal_hours)  # קבלת השעות השלמות
    minutes_decimal = (decimal_hours - hours) * 60  # המרת החלק השברי לדקות
    minutes = int(minutes_decimal)  # קבלת הדקות השלמות
    seconds = (minutes_decimal - minutes) * 60  # המרת החלק השברי של הדקות לשניות
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds

#################################################################################################

# חישוב מה מרכז המסך כדי למרכז את הטקסט במרכז המסך
# עדיין יש בעיות קטנות שאולי נגרמות מכך שיש אותיות צרות יותר מ MAX_WIDTH אבל אין מה לעשות כרגע
# בינתיים זה הכי טוב שהגעתי אליו
def center(text, font):
    # הגדרת הפיקסל שבמרכז המסך
    tft_pixel_center = 160 # tft.width() // 2
    # הגדרת הפיקסל שבמרכז הטקסט
    text_pixel_center = len(text) // 2 * font.MAX_WIDTH // 2 # כלומר הרוחב בפיקסלים של חצי מהטקסט
    return tft_pixel_center - text_pixel_center # זה אומר כמה ימינה ממרכז המסך צריך להתחיל את ההדפסה כדי שמרכז ההדפסה יהיה במרכז המסך


######################################################################################################3

# פונקצייה מאוד חשובה לקביעה כמה זמן לחצו על כפתור האם לחיצה ארוכה או קצרה
def handle_button_press(specific_button):
    start_time = time.ticks_ms()
    # הלולאה הזו מתבצעת אם לוחים ברציפות בלי לעזוב
    while specific_button.value() == 0:  # כל עוד הכפתור לחוץ
        if time.ticks_diff(time.ticks_ms(), start_time) > 2000:  # לחיצה ארוכה מעל 2 שניות
            return "long"
    # מכאן והלאה מתבצע רק אחרי שעוזבים את הכפתור ואז מודדים כמה זמן היה לחוץ
    if 100 < time.ticks_diff(time.ticks_ms(), start_time) < 1000: # לחיצה קצרה מתחת לשנייה אחת אבל מעל 100 מיקרו שניות כדי למנוע לחיצה כפולה
        return "short"
    return None  # במידה ולא זוהתה לחיצה


# פונקצייה נורא חשובה שעושה כמה פעולות קריטיות בלחיצה על כפתור ההפעלה/כיבוי
# 1: מפעילה או מכבה 2: מחזירה למיקום ברירת מחדל. 3: מאפסת את המשתנה של הזמן שלפיו נקבע מתי יכבה המסך מעצמו
def toggle_power(pin):
    
    button_14.irq(handler=None)  # השבתת ה-IRQ כדי למנוע הפעלה כפולה של פונקצייה זו
    
    # המשתנה הגלובלי ששולט על האם לכבות או להדליק
    global power_state
    
    # הפיכת המצב גורמת להדלקה או כיבוי שמתבצעת בפועל בפונקצייה הראשית מיין-מיין
    power_state = not power_state 
    #  תזכורת שפעם שלא הלכנו לשינה עמוקה עשיתי כאן import main וזה התחיל הכל מהתחלה

    # המתנה כדי למנוע לחיצה כפולה
    while button_14.value() == 0:  # ממתין שהכפתור ישתחרר
        time.sleep_ms(50)
    
    button_14.irq(trigger=Pin.IRQ_FALLING, handler=toggle_power)  # הפעלת ה-IRQ מחדש לאחר שסיימנו את הפעולה של הפונקצייה
            

# חיבור הכפתור לפונקציה הנל. לחיצה על הכפתור קוראת לפונקצייה שמעדכנת את משתנה הכוח
# כרגע מתבצע באמצעות כפתור בוט אבל אפשר גם באמצעות הכפתור השני
button_14.irq(trigger=Pin.IRQ_FALLING, handler=toggle_power)

######################################################################################################

def get_timestamp_from_screen():
    """מאפשר למשתמש להגדיר תאריך ושעה ידנית ולהחזיר חותמת זמן UTC או None במקרה של ביטול."""
    
    ###############################################################
    # השבתת הפעילות הרגילה של כפתור 14 כי כאן צריך אותו לשימוש אחר.
    button_14.irq(handler=None)
    ##############################################################
    
    # הניסיון הוא רק כדי שבסוף נוכל לעשות finally ולהחזיר את כפתור 14 לפעולתו הרגילה
    try: 
        rtc_system = machine.RTC()
        current = list(rtc_system.datetime())  # (year, month, day, weekday, hour, minute, second, subseconds)
        date_parts = ["יום", "חודש", "שנה", "שעה", "דקה", "שנייה", "הפרש שעות מגריניץ", "אישור/ביטול"]
        indices = [2, 1, 0, 4, 5, 6]
        position = 0

        MIN_YEAR = 2001
        MAX_YEAR = 2100
        local_offset = 3 if is_now_israel_DST() else 2
        utc_offset = local_offset

        pos_x_values = [10, 43, 76, 137, 170, 203, 240]  # X לשדה תאריך/שעה
        y_line = 5          # Y לשורה הראשונה

        ok_index = 0
        ok_str_options = [reverse("אישור"), reverse("ביטול")]
        
        # כדי לדעת מתי לצאת כשיש חוסר פעילות 
        last_activity = time.time()
        
        while True:
            
            # בדיקה אם עברו 20 שניות בלי פעילות
            if time.time() - last_activity > 20:
                tft.fill(0)
                tft.write(FontHeb25, reverse("יציאה עקב חוסר פעילות"), 10, 60)
                tft.show()
                time.sleep(2)
                return None# יציאה מהפונקציה לגמרי
            
            
            utc_hour = (current[4] - utc_offset) % 24
            ok_str = ok_str_options[ok_index]

            # בניית המחרוזות להצגה
            values_str = [
                f"{current[2]:02d}/", f"{current[1]:02d}/", f"{current[0]}",
                f"{current[4]:02d}:", f"{current[5]:02d}:", f"{current[6]:02d}",
                f"utc{utc_offset:+03d}"
            ]
            utc_time_str = f"utc: {utc_hour:02d}:{current[5]:02d}:{current[6]:02d}"

            # הצגת המסך
            tft.fill(0)

            # שורה ראשונה – תאריך ושעה
            for i, val in enumerate(values_str):
                bg_color = s3lcd.CYAN if i == position and position < 7 else s3lcd.BLACK
                fg_color = s3lcd.BLACK if i == position and position < 7 else s3lcd.GREEN
                tft.write(FontHeb25, val, pos_x_values[i], y_line, fg_color, bg_color)

            # שורה לשדה – אישור/ביטול
            bg_color_ok = s3lcd.CYAN if position == 7 else s3lcd.BLACK
            fg_color_ok = s3lcd.BLACK if position == 7 else s3lcd.GREEN
            tft.write(FontHeb25, ok_str, center(ok_str,FontHeb25), 55, fg_color_ok, bg_color_ok)

            # הצגת השעה בגריניץ והשדה הנוכחי
            tft.write(FontHeb20, utc_time_str, pos_x_values[3]-30, y_line+30, s3lcd.CYAN, s3lcd.BLACK)
            tft.write(FontHeb20, reverse(f"שלב נוכחי: {date_parts[position]}"), center(reverse(f"שלב נוכחי: {date_parts[position]}"),FontHeb20), 80, s3lcd.YELLOW, s3lcd.BLACK)

            # טיפים למשתמש
            tft.write(FontHeb20, reverse("לחיצה קצרה משנה ערך"), 50, 110)
            tft.write(FontHeb20, reverse("לחיצה ארוכה למעלה מקדמת שלב"), 20, 130)
            tft.write(FontHeb20, reverse("לחיצה ארוכה למטה מחזירה שלב"), 20, 150)
            tft.show()

            # קריאת כפתורים
            press_main = handle_button_press(boot_button)
            press_down = handle_button_press(button_14)
            
            # אם לא נלחץ שום כפתור - דלג על המשך הלולאה
            if not press_main and not press_down:
                continue
            
            # אם מגיעים לכאן אז בטוח שנלחץ כפתור כלשהו ולכן דוחים את זמן היציאה האוטומטית
            last_activity = time.time()

            # לחיצה קצרה
            if press_main == "short":
                if position < 6:
                    i = indices[position]
                    if position == 0:
                        current[i] = (current[i] % 31) + 1
                    elif position == 1:
                        current[i] = (current[i] % 12) + 1
                    elif position == 2:
                        current[i] = (current[i] + 1) if current[i] < MAX_YEAR else MIN_YEAR
                    elif position == 3:
                        current[i] = (current[i] + 1) % 24
                    elif position == 4:
                        current[i] = (current[i] + 1) % 60
                    elif position == 5:
                        current[i] = (current[i] + 1) % 60
                elif position == 6:
                    utc_offset += 1
                    if utc_offset > 12:
                        utc_offset = -12
                elif position == 7:
                    ok_index = 1 - ok_index  # החלפה בין אישור/ביטול

            elif press_down == "short":
                if position < 6:
                    i = indices[position]
                    if position == 0:
                        current[i] = 31 if current[i] == 1 else current[i] - 1
                    elif position == 1:
                        current[i] = 12 if current[i] == 1 else current[i] - 1
                    elif position == 2:
                        current[i] = current[i] - 1 if current[i] > MIN_YEAR else MAX_YEAR
                    elif position == 3:
                        current[i] = (current[i] - 1) % 24
                    elif position == 4:
                        current[i] = (current[i] - 1) % 60
                    elif position == 5:
                        current[i] = (current[i] - 1) % 60
                elif position == 6:
                    utc_offset -= 1
                    if utc_offset < -12:
                        utc_offset = 12
                elif position == 7:
                    ok_index = 1 - ok_index  # החלפה בין אישור/ביטול

            # לחיצה ארוכה
            elif press_main == "long":
                if position == 7:
                    if ok_index == 0:  # אישור
                        rtc_hour_utc = (current[4] - utc_offset) % 24
                        time_tuple = (current[0], current[1], current[2], rtc_hour_utc, current[5], current[6], 0, 0)  
                        return time.mktime(time_tuple)
                    else:  # ביטול
                        return None
                else:
                    position += 1
                    if position > 7:
                        position = 7

            elif press_down == "long":
                position -= 1
                if position < 0:
                    position = 0

            time.sleep(0.1)
            
    finally:
        # הפעלת ה־IRQ מחדש ללא קשר לדרך היציאה
        button_14.irq(trigger=Pin.IRQ_FALLING, handler=toggle_power)

##############################################################
        
# מונקצייה שמנסה להתחבר לווייפי ולקבל את הזמן הנוכחי בגריניץ כלומר ב UTC-0
# אם הצליחה היא מחזירה חותמת זמן. אם לא נמצאו רשתות פתוחות מחזירה False. ואם נמצאו אך לא הצליחה לקבל זמן מחזירה None
def get_ntp_timestamp():
    """עדכון השעה משרת NTP עם ניסיון לרשתות נוספות במקרה של כישלון, כולל כיבוי Wi-Fi בסוף."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False) # חייבים קודם לכבות ואחר כך להדליק
    wlan.active(True)  # הפעלת ה-WiFi

    # סריקת רשתות זמינות
    networks = wlan.scan() 
    # מסנן רק רשתות פתוחות כלומר שהן ללא סיסמה
    open_networks = [net for net in networks if net[4] == 0]
    
    # אם אין רשתות פתוחות מפסיקים את הניסיון ומחזירים פאלס
    if not open_networks:
        wlan.active(False)  # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו
        return False
    
    # מנסים להתחבר לכל אחת מהרשתות הפתוחות שנמצאו
    for net in open_networks:    
        ###########################
        # זה נועד למנוע שגיאת: [Errno 116] ETIMEDOUT
        # כיבוי והדלקה מחדש של הוויפי אחרת זה לא תמיד מתחבר והמתנה שתי שניות כדי שהחיבור יתייצב
       # wlan.active(False)
        #wlan.active(True)
        #time.sleep(2)
        ###########################
        ssid = net[0].decode()
        print(f"ניסיון חיבור ל- {ssid}...")
        #wlan.disconnect()  # ניתוק מכל רשת קודמת
        wlan.connect(ssid)
        time.sleep(2)

        # המתנה לחיבור עד 10 שניות
        for _ in range(10):
            if wlan.isconnected():
                print(f"חובר בהצלחה לרשת {ssid}!")
                print("כתובת IP:", wlan.ifconfig()[0])
                break
            time.sleep(1)
        
        # אם הצליחו להתחבר לאחת מהרשתות הפתוחות
        if wlan.isconnected():
            try:
                # ניסיון לקבלת זמן משרת NTP
                ntptime.host = "pool.ntp.org"
                ntptime.timeout = 1
                # קבלת הזמן מהשרת בפורמט של חותמת זמן. הזמן המתקבל הוא בשעון גריניץ כלומר UTC-0
                ntp_timestamp_utc = ntptime.time()
                # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו
                wlan.active(False)
                return ntp_timestamp_utc 
            
            except Exception as ntp_error:
                print(f"שגיאה בקבלת הזמן מהרשת {ssid}: {ntp_error}")
                wlan.disconnect()  # ניתוק בלבד, ננסה רשת אחרת
    
    wlan.active(False)  # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו
    # במקרה שהצליח להתחבר לרשתות אבל אף אחד מהם לא החזירה זמן ntp מחזירים None
    return None

#########################################################################################################

# משתנה ששומר מידע על המקור שממנו שאבנו את הזמן
time_source = None

# פונקצייה שמטפלת בכל הגדרת הזמן, ועדכונו אם צריך, גם בשעון הפנימי וגם בשעון החיצוני
# חשוב מאוד! הפונקצייה מגדירה בשעון החיצוני והפנימי את הזמן בשעון גריניץ כלומר איזור זמן UTC-0
def check_and_set_time(Force_update = False):
    
    global time_source
    # הגדרת השעון הפנימי של הבקר
    rtc_system = machine.RTC()
    ##########################################
    # דבר ראשון מעדכנים זמן שרירותי בשעון הפנימי כדי שמה שלא יקרה השעון הפנימי יהיה עדכני ולא יהיה מעודכן לאפוך שלו בשנת 2000 או 1970
    # מקור הזמן נשאר עדיין None ולכן יודפסו סימני קריאה לייד הזמן אם הוא לא יישתנה
    if rtc_system.datetime()[0] <= 2000:
        manual_time = (2001, 5, 20, get_rtc_weekday(6), 16, 39, 35, 20)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
        rtc_system.datetime(manual_time)
    ##########################################
    
    # בדיקה האם DS3231 מחובר ולאיפה מחובר באמצעות פונקצייה שהוגדרה לעיל
    is_ds3231_connected, ds3231_exit, ds3231_exit_name = check_i2c_device(ds3231_bitname)
    
    ##########################################
    # אם DS3231 מחובר, ולא הוגדר בתחילה שרוצים לכפות עדכון
    if is_ds3231_connected and not Force_update:
        
        # הגדרת DS3231
        rtc_ds3231 = DS3231(ds3231_exit)
        
        #  קריאת הזמן מ-DS3231
        ds3231_time = rtc_ds3231.datetime()
        
        # אם DS3231 מוגדר נכון ולא מאופס לשנת 2000 אז מעדכנים את הזמן שבו לתוך השעון הפנימי ויוצאים מהפונקצייה
        if ds3231_time[0] > 2000: 
            rtc_system.datetime(ds3231_time)
            print("הזמן עודכן מתוך DS3231: ", ds3231_time)
            time_source = "DS3231"
            return
    ####################################################
        
    # מכאן והלאה מעדכנים שעונים משרת NTP וזה דרוש בכל המקרים מלבד המקרה שכבר טופל לעיל שהשעון החיצוני מחובר ולא רוצים לעדכן 
    # הדפסה למסך
    tft.fill(0) # מחיקת המסך
    tft.write(FontHeb25,f'{reverse("ניסיון קבלת זמן מהרשת...")}',5,15)
    tft.show() # כדי להציג את הנתונים על המסך
                
    # ניסיון קבלת זמן ntp מהשרת באמצעות פונקצייה
    # אם הצליחה היא מחזירה חותמת זמן. אם לא נמצאו רשתות פתוחות מחזירה False. ואם נמצאו אך לא הצליחה לקבל זמן מחזירה None
    ntp_timestamp_utc = get_ntp_timestamp()
    
    # אם לא הצלחנו לקבל זמן רשת
    if not ntp_timestamp_utc:     
        if ntp_timestamp_utc == None:
            tft.write(FontHeb25,f'{reverse("הרשת לא מחזירה זמן")}',5,45)
        elif ntp_timestamp_utc == False:
            tft.write(FontHeb25,f'{reverse("לא נמצאה רשת פתוחה")}',5,45)
        #################################################################
        tft.write(FontHeb25,f'{reverse("יש להגדיר זמן ידנית")}',5,75)
        tft.show() # כדי להציג את הנתונים על המסך
        time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה        
        # מנסים לקבל זמן ידני מהמשתמש ולהציג לו את מסך בחירת הזמן
        target_timestamp_utc = get_timestamp_from_screen()
        # אם מחזיר ערך זה אומר שהמשתמש אישר את הזמן ממסך הגדרת הזמן
        if target_timestamp_utc:
            tft.fill(0) # מחיקת המסך 
            time_source = reverse("מסך")
        # בכל מקרה אחר המשתמש ביטל את הגדרת הזמן מהמסך אז מחזיר None ואין מה להמשיך הלאה
        else:
            return
        ##################################################################
    
    else:
        tft.write(FontHeb25,f'{reverse("הזמן התקבל בהצלחה מהרשת")}',5,45)
        target_timestamp_utc = ntp_timestamp_utc
        time_source = "NTP"
        
    # אם מוגדר חותמת זמן מהרשת או ממקור ידני
    if target_timestamp_utc:
        
        # המרת הזמן הנוכחי בגריניץ מחותמת זמן לפורמט של תאריך ושעה
        year, month, day, hour, minute, second, week_day, year_day = utime.localtime(target_timestamp_utc)
        
        # אם מחובר שעון חיצוני ds3231
        if is_ds3231_connected:
            
            # הגדרת DS3231
            rtc_ds3231 = DS3231(ds3231_exit)
            # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
            time_for_ds3231 = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
            # עדכון הזמן ב-DS3231
            rtc_ds3231.datetime(time_for_ds3231)
            #  קריאת הזמן המעודכן מ-DS3231
            ds3231_time = rtc_ds3231.datetime()
            # הגדרת הזמן המעודכן לתוך השעון הפנימי
            rtc_system.datetime(ds3231_time)
            print("ds3231_time עודכן", rtc_ds3231.datetime())
        else:
            # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
            time_for_rtc_system = (year, month, day, get_rtc_weekday(week_day), hour, minute, second, 0)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
            # עדכון רק של השעון הפנימי מזמן הרשת
            rtc_system.datetime(time_for_rtc_system)
            
    # הדפסה למסך
    tft.write(FontHeb25,f'{reverse("הזמן הוגדר בהצלחה מ")}: {time_source}',5,75)
    tft.show() # כדי להציג את הנתונים על המסך
    time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
        


# פעולה חשובה מאוד!!! בתחילת פעילות התוכנה: קריאה לפנקצייה שמטפלת בהגדרת ועדכון הזמן
# זה קורה רק פעם בהתחלה ולא כל שנייה מחדש
check_and_set_time()


# את השורה הזו צריך להגדיר רק אם רוצים להגדיר ידנית את השעון הפנימי של הבקר וזה בדרך כלל לא יישומי כאן
#machine.RTC().datetime((2025, 3, 26, get_rtc_weekday(4), 10, 59, 0, 0))  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)


#################################################################################################


# פונקצייה שמחשבת מה השעה הזמנית הנוכחית בהינתן הזמן הנוכחי וזמן הזריחה והשקיעה הקובעים
# כל הזמנים צריכים להינתן בפורמט חותמת זמן
# פונקצייה זו יכולה לפעול גם בכל פייתון רגיל היא לגמרי חישובית ולא תלוייה בכלום חוץ מהמשתנים שלה
def calculate_temporal_time(timestamp, sunrise_timestamp, sunset_timestamp):
    
        # בדיקה האם זה יום לפי בדיקה האם הזמן הנוכחי גדול משעת הזריחה וקטן משעת השקיעה
        is_day = timestamp >= sunrise_timestamp and timestamp < sunset_timestamp
        
        # חישוב מספר השקיעה מהזריחה לשקיעה אם זה יום או מהשקיעה לזריחה אם זה לילה
        day_or_night_length_seconds = sunset_timestamp - sunrise_timestamp if is_day else sunrise_timestamp - sunset_timestamp
        
        # חישוב מספר השניות בשעה זמנית אחת של היום לפי חלוקת אורך היום או הלילה ל 12
        seconds_per_temporal_hour_in_day_or_night = day_or_night_length_seconds / 12
        
        # חישוב כמה שניות עברו מאז הזריחה או השקיעה עד הזמן הנוכחי 
        time_since_last_sunrise_or_sunset = timestamp - (sunrise_timestamp if is_day else sunset_timestamp)
        
        # המרת השניות לפורמט שעות, דקות ושניות
        A = (time_since_last_sunrise_or_sunset / seconds_per_temporal_hour_in_day_or_night) + 0.0000001
        zmanit_hour = int(A)
        B = ((A - zmanit_hour) * 60) + 0.0000001
        zmanit_minute = int(B)
        C = ((B - zmanit_minute) * 60) + 0.0000001
        zmanit_second = int(C)

        # הדפסת השעה הזמנית המתאימה בפורמט שעות:דקות:שניות
        temporal_time = f'{zmanit_hour:02.0f}:{zmanit_minute:02.0f}:{zmanit_second:02.0f}'
        
        return temporal_time, seconds_per_temporal_hour_in_day_or_night


##############################################################################################################        
# הגדרת שמות עבור משתנים גלובליים ששומרים את כל הזמנים הדרושים לחישובים
sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
tset_hacochavim, misheiakir = [None] * 2
##############################################################################################################    

def get_sunrise_sunset_timestamps(current_timestamp, is_gra = True):
    
    # הצהרה על משתנים גלובליים ששומרים את הזמנים הדרושים
    global sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise
    
    #  חותמת זמן של רגע הזריחה והשקיעה היום
    # חוממת זמן של תחילת וסוף הדמדומים של מגן אברהם כרגע מוגדר לעיל מינוס 16
    sunrise_timestamp = sunrise if is_gra else mga_sunrise
    sunset_timestamp = sunset if is_gra else mga_sunset
           
    # בדיקה האם זה יום לפי בדיקה האם הזמן הנוכחי גדול משעת הזריחה וקטן משעת השקיעה
    is_day = current_timestamp >= sunrise_timestamp and current_timestamp < sunset_timestamp 
    
    #print("is_gra", is_gra)
    #print("is_day", is_day)
    
    if is_day:
        
        return sunrise_timestamp, sunset_timestamp
                
    else:
        # אם מדובר אחרי 12 בלילה ולפני הזריחה
        if current_timestamp < sunrise_timestamp:
            
            # הגדרת הזמן על אתמול וחישוב השקיעה של אתמול
            yesterday_sunset_timestamp = yesterday_sunset if is_gra else mga_yesterday_sunset
        
            return sunrise_timestamp, yesterday_sunset_timestamp
            
            
        # אם מדובר אחרי השקיעה ולפני השעה 12 בלילה
        elif (current_timestamp > sunrise_timestamp) and (current_timestamp >= sunset_timestamp):
            
            # הגדרת הזמן על מחר וחישוב הזריחה של מחר
            tomorrow_sunrise_timestamp = tomorrow_sunrise if is_gra else mga_tomorrow_sunrise
            
            return tomorrow_sunrise_timestamp, sunset_timestamp

################################################################################################################3

# כל המיקומים. כל מיקום מוגדר כמילון
# המיקום הראשון ברשימה יהיה ברירת המחדל אם לא מצליחים לקרוא מהקובץ שקובע מהו מיקום ברירת המחדל


locations = [
    
    {'heb_name': 'משווה-0-0', 'lat': 0.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'Equals 0-0'} , # קו המשווה בכוונה נמצא פעמיים כדי שבהעברת מיקומים תמיד יראו אותו ראשון
    {'heb_name': 'קו-המשווה', 'lat': 0.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'Equals 0-0'} ,
    {'heb_name': 'הקוטב-הצפוני', 'lat': 90.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'North Pole'} ,
    {'heb_name': 'ניו-יורק-ארהב', 'lat': 40.7143528, 'long': -74.0059731, 'altitude': 9.775694, 'utc_offset': '', 'name': 'New York US'} ,
    {'heb_name': 'אופקים', 'lat': 31.309, 'long': 34.61, 'altitude': 170.0, 'utc_offset': '', 'name': 'Ofakim IL'} ,
    {'heb_name': 'אילת', 'lat': 29.55, 'long': 34.95, 'altitude': 0.0, 'utc_offset': '', 'name': 'Eilat IL'} ,
    {'heb_name': 'אלעד', 'lat': 32.05, 'long': 34.95, 'altitude': 150.0, 'utc_offset': '', 'name': 'Elad IL'} ,
    {'heb_name': 'אריאל', 'lat': 32.10, 'long': 35.17, 'altitude': 521.0, 'utc_offset': '', 'name': 'Ariel IL'} ,
    {'heb_name': 'אשדוד', 'lat': 31.79, 'long': 34.641, 'altitude': 0.0, 'utc_offset': '', 'name': 'Ashdod IL'} ,
    {'heb_name': 'אשקלון', 'lat': 31.65, 'long': 34.56, 'altitude': 60.0, 'utc_offset': '', 'name': 'Ashkelon IL'} ,
    {'heb_name': 'באר-שבע', 'lat': 31.24, 'long': 34.79, 'altitude': 0.0, 'utc_offset': '', 'name': 'Beer Sheva IL'} ,
    {'heb_name': 'בית-שאן', 'lat': 32.5, 'long': 35.5, 'altitude': -120.0, 'utc_offset': '', 'name': 'Beit Shean IL'} ,
    {'heb_name': 'בית-שמש', 'lat': 31.74, 'long': 34.98, 'altitude': 300.0, 'utc_offset': '', 'name': 'Beit Shemesh IL'} ,
    {'heb_name': 'ביתר-עילית', 'lat': 31.69, 'long': 35.12, 'altitude': 800.0, 'utc_offset': '', 'name': 'Beitar Illit IL'} ,
    {'heb_name': 'בני-ברק', 'lat': 32.083156, 'long': 34.832722, 'altitude': 0.0, 'utc_offset': '', 'name': 'Bnei Brak IL'} ,
    {'heb_name': 'דימונה', 'lat': 31.07, 'long': 35.03, 'altitude': 570.0, 'utc_offset': '', 'name': 'Dimona IL'} ,
    {'heb_name': 'הר רומם', 'lat': 30.5100176, 'long': 34.6089109, 'altitude': 1000.0, 'utc_offset': '', 'name': 'Mount Romem IL'} ,
    {'heb_name': 'הרצליה', 'lat': 32.16, 'long': 34.84, 'altitude': 0.0, 'utc_offset': '', 'name': 'Herzliya IL'} ,
    {'heb_name': 'זכרון יעקב', 'lat': 32.57, 'long': 34.95, 'altitude': 170.0, 'utc_offset': '', 'name': 'Zichron Yaakov IL'} ,
    {'heb_name': 'חברון', 'lat': 31.53, 'long': 35.09, 'altitude': 950.0, 'utc_offset': '', 'name': 'Hebron IL'} ,
    {'heb_name': 'חדרה', 'lat': 32.43, 'long': 34.92, 'altitude': 53.0, 'utc_offset': '', 'name': 'Hadera IL'} ,
    {'heb_name': 'חיפה', 'lat': 32.8, 'long': 34.991, 'altitude': 300.0, 'utc_offset': '', 'name': 'Haifa IL'} ,
    {'heb_name': 'חרשה', 'lat': 31.944738, 'long': 35.1485598, 'altitude': 760.0, 'utc_offset': '', 'name': 'Harasha'} ,
    {'heb_name': 'טבריה', 'lat': 32.79, 'long': 35.531, 'altitude': 0.0, 'utc_offset': '', 'name': 'Tiberias IL'} ,
    {'heb_name': 'טלזסטון', 'lat': 31.78, 'long': 35.1, 'altitude': 720.0, 'utc_offset': '', 'name': 'Telzstone IL'} ,
    {'heb_name': 'ירוחם', 'lat': 30.99, 'long': 34.91, 'altitude': 0.0, 'utc_offset': '', 'name': 'Yeruham IL'} ,
    {'heb_name': 'ירושלים', 'lat': 31.776812, 'long': 35.235694, 'altitude': 750.0, 'utc_offset': '', 'name': 'Jerusalem IL'} ,
    {'heb_name': 'כוכב השחר', 'lat': 31.96, 'long': 35.34, 'altitude': 577.0, 'utc_offset': '', 'name': 'Cochav Hashachar IL'} ,
    {'heb_name': 'כרמיאל', 'lat': 32.915, 'long': 35.292, 'altitude': 315.0, 'utc_offset': '', 'name': 'Carmiel IL'} ,
    {'heb_name': 'לוד', 'lat': 31.95, 'long': 34.89, 'altitude': 0.0, 'utc_offset': '', 'name': 'Lod IL'} ,
    {'heb_name': 'מגדל-העמק', 'lat': 32.67, 'long': 35.23, 'altitude': 0.0, 'utc_offset': '', 'name': 'Migdal Haemek IL'} ,
    {'heb_name': 'מודיעין-עילית', 'lat': 31.940826, 'long': 35.037057, 'altitude': 320.0, 'utc_offset': '', 'name': "Modi'in Illit IL"} ,
    {'heb_name': 'מיצד', 'lat': 31.585503, 'long': 35.187587, 'altitude': 937.0, 'utc_offset': '', 'name': 'Meizad IL'} ,
    {'heb_name': 'מירון', 'lat': 32.98, 'long': 35.43, 'altitude': 700.0, 'utc_offset': '', 'name': 'Miron IL'} ,
    {'heb_name': 'מצפה רמון', 'lat': 30.6097894, 'long': 34.8120107, 'altitude': 855.0, 'utc_offset': '', 'name': 'Mitzpe Ramon IL'} ,
    {'heb_name': 'נהריה', 'lat': 33.01, 'long': 35.1, 'altitude': 25.0, 'utc_offset': '', 'name': 'Nahariya IL'} ,
    {'heb_name': 'נחליאל', 'lat': 31.9743, 'long': 35.14038, 'altitude': 575.0, 'utc_offset': '', 'name': 'Nahaliel'} ,
    {'heb_name': 'נצרת-עילית', 'lat': 32.7, 'long': 35.32, 'altitude': 0.0, 'utc_offset': '', 'name': 'Nazareth Illit IL'} ,
    {'heb_name': 'נתיבות', 'lat': 31.42, 'long': 34.59, 'altitude': 142.0, 'utc_offset': '', 'name': 'Netivot IL'} ,
    {'heb_name': 'נתניה', 'lat': 32.34, 'long': 34.86, 'altitude': 0.0, 'utc_offset': '', 'name': 'Netanya IL'} ,
    {'heb_name': 'עכו', 'lat': 32.93, 'long': 35.08, 'altitude': 0.0, 'utc_offset': '', 'name': 'Ako IL'} ,
    {'heb_name': 'עמנואל', 'lat': 32.16, 'long': 35.13, 'altitude': 406.0, 'utc_offset': '', 'name': 'Emmanuel IL'} ,
    {'heb_name': 'עפולה', 'lat': 32.6, 'long': 35.29, 'altitude': 60.0, 'utc_offset': '', 'name': 'Afula IL'} ,
    {'heb_name': 'ערד', 'lat': 31.26, 'long': 35.21, 'altitude': 640.0, 'utc_offset': '', 'name': 'Arad IL'} ,
    {'heb_name': 'פתח-תקווה', 'lat': 32.09, 'long': 34.88, 'altitude': 0.0, 'utc_offset': '', 'name': 'Petah Tikva IL'} ,
    {'heb_name': 'צפת', 'lat': 32.962, 'long': 35.496, 'altitude': 850.0, 'utc_offset': '', 'name': 'Zefat IL'} ,
    {'heb_name': 'קצרין', 'lat': 32.98, 'long': 35.69, 'altitude': 0.0, 'utc_offset': '', 'name': 'Katzrin IL'} ,
    {'heb_name': 'קרית-גת', 'lat': 31.61, 'long': 34.77, 'altitude': 159.0, 'utc_offset': '', 'name': 'Kiryat Gat IL'} ,
    {'heb_name': 'קרית-שמונה', 'lat': 33.2, 'long': 35.56, 'altitude': 0.0, 'utc_offset': '', 'name': 'Kiryat Shmona IL'} ,
    {'heb_name': 'ראש-העין', 'lat': 32.08, 'long': 34.95, 'altitude': 90.0, 'utc_offset': '', 'name': 'Rosh HaAyin IL'} ,
    {'heb_name': 'ראשון-לציון', 'lat': 31.96, 'long': 34.8, 'altitude': 0.0, 'utc_offset': '', 'name': 'Rishon Lezion IL'} ,
    {'heb_name': 'רחובות', 'lat': 31.89, 'long': 34.81, 'altitude': 76.0, 'utc_offset': '', 'name': 'Rechovot IL'} ,
    {'heb_name': 'רכסים', 'lat': 32.74, 'long': 35.08, 'altitude': 154.0, 'utc_offset': '', 'name': 'Rechasim IL'} ,
    {'heb_name': 'רמלה', 'lat': 31.92, 'long': 34.86, 'altitude': 0.0, 'utc_offset': '', 'name': 'Ramla IL'} ,  
    {'heb_name': 'רעננה', 'lat': 32.16, 'long': 34.85, 'altitude': 71.0, 'utc_offset': '', 'name': 'Raanana IL'} ,
    {'heb_name': 'שדרות', 'lat': 31.52, 'long': 34.59, 'altitude': 0.0, 'utc_offset': '', 'name': 'Sderot IL'} ,
    {'heb_name': 'שילה', 'lat': 32.05, 'long': 35.29, 'altitude': 719.0, 'utc_offset': '', 'name': 'Shilo IL'} ,
    {'heb_name': 'תל-אביב-חולון', 'lat': 32.01, 'long': 34.75, 'altitude': 0.0, 'utc_offset': '', 'name': 'Tel Aviv-Holon IL'} ,
    {'heb_name': 'תפרח', 'lat': 31.32, 'long': 34.67, 'altitude': 173.0, 'utc_offset': '', 'name': 'Tifrach IL'} ,
    
    {'heb_name': 'אומן-אוקראינה', 'lat': 48.74732, 'long': 30.23332, 'altitude': 211.0, 'utc_offset': '', 'name': 'Uman UA'} ,
    {'heb_name': 'אמסטרדם-הולנד', 'lat': 52.38108, 'long': 4.88845, 'altitude': 15.0, 'utc_offset': '', 'name': 'Amsterdam NL'} ,
    {'heb_name': 'וילנא-ליטא', 'lat': 54.672298, 'long': 25.2697, 'altitude': 112.0, 'utc_offset': '', 'name': 'Vilnius LT'} ,
    {'heb_name': "ז'שוב-פולין", 'lat': 50.0332, 'long': 21.985848, 'altitude': 209.0, 'utc_offset': '', 'name': 'Rzeszow PL'} ,
    {'heb_name': 'טרולהטן-שבדיה', 'lat': 58.28, 'long': 12.28, 'altitude': 28.0, 'utc_offset': '', 'name': 'Trollhattan SE'} ,  
    {'heb_name': 'לונדון-אנגליה', 'lat': 51.5001524, 'long': -0.1262362, 'altitude': 14.605533, 'utc_offset': '', 'name': 'London GB'} ,
    {'heb_name': 'לייקווד-ארהב', 'lat': 40.07611, 'long': -74.21993, 'altitude': 16.0, 'utc_offset': '', 'name': 'Lakewood US'} ,
    {'heb_name': 'מוסקווה-רוסיה', 'lat': 55.755786, 'long': 37.617633, 'altitude': 151.189835, 'utc_offset': '', 'name': 'Moscow RU'} ,
    {'heb_name': 'סטוקהולם-שבדיה', 'lat': 59.33, 'long': 18.06, 'altitude': 28.0, 'utc_offset': '', 'name': 'Stockholm SE'} ,
    {'heb_name': "פראג-צ'כיה", 'lat': 50.0878114, 'long': 14.4204598, 'altitude': 191.103485, 'utc_offset': '', 'name': 'Prague CZ'} ,
    {'heb_name': 'פריז-צרפת', 'lat': 48.8566667, 'long': 2.3509871, 'altitude': 0.0, 'utc_offset': '', 'name': 'Paris FR'} ,
    {'heb_name': 'פרנקפורט-גרמניה', 'lat': 50.1115118, 'long': 8.6805059, 'altitude': 106.258285, 'utc_offset': '', 'name': 'Frankfurt DE'} ,
    {'heb_name': 'קהיר-מצרים', 'lat': 30.00022, 'long': 31.231873, 'altitude': 23.0, 'utc_offset': '', 'name': 'Cairo EG'} ,
    {'heb_name': 'רומא-איטליה', 'lat': 41.8954656, 'long': 12.4823243, 'altitude': 19.704413, 'utc_offset': '', 'name': 'Rome IT'} ,
    {'heb_name': 'רמרוג-צרפת רת', 'lat': 48.518606, 'long': 4.3034152, 'altitude': 101.0, 'utc_offset': '', 'name': 'Ramerupt FR'} ,
        
    ]



#  ההסברים מורכבים משני חלקים כל אחד: הסבר וערך. ההסבר עובר בסוף רוורס ולכן אם יש בו מספרים חייבים לעשות להם רוורס כאן כדי שהרוורס הסופי יישר אותם 
hesberim = [
    
        [f"שעון ההלכה גרסה: {reverse(VERSION)}"],
        [" מאת: שמחה גרשון בורר - כוכבים וזמנים"],
        [f'{reverse("sgbmzm@gmail.com")}'],
        ["כל הזכויות שמורות - להלן הסברים"],
        ["בתקלה: יש ללחוץ על לחצן האיפוס"],
        ["אחוז הסוללה )בערך(: בשורת הכותרת"],
        ["כשמחובר לחשמל מופיע: %**"],
        ["אור אדום דולק בחור: הסוללה נטענת"],
        ["לחצן תחתון: הדלקה וכיבוי"],
        ["לחצן עליון: ביצוע פעולות כדלהלן"],
        ["לחיצה קצרה: שינוי מיקום"],
        ["לחיצה מתמשכת: תפריט הגדרות"],
        ["הדלקה בשני הלחצנים: עדכון תוכנה"],

        [f"כשהשעון מכוון: דיוק הזמנים {reverse('10')} שניות"],
        
        [" התאריך העברי מתחלף בשקיעה"],
        
        [" מתחת גרא/מגא:  דקות בשעה זמנית"],
        [" מתחת שמש/ירח:  אזימוט שמש/ירח"],
        ["אזימוט = מעלות מהצפון, וכדלהלן"],
        [f"צפון={reverse('0/360')}, מז={reverse('90')}, ד={reverse('180')}, מע={reverse('270')}"],
        ["  שלב הירח במסלולו החודשי - באחוזים"],
        [f"מולד={reverse('0/100')}, ניגוד={reverse('50')}, רבעים={reverse('25/75')}"],
    
        ["רשימת זמני היום בשעות זמניות"],
        ["זריחה ושקיעה: "+reverse('00:00')],
        ["סוף שמע ביום/רבע הלילה: "+reverse('03:00')],
        ["  סוף תפילה ביום/שליש הלילה: "+reverse('04:00')],
        [f"חצות יום ולילה: "+reverse('06:00')],
        ["מנחה: גדולה - "+reverse('06:30')+", קטנה - "+reverse('09:30')],
        ["פלג המנחה: "+reverse('10:45')],
        
        ["זמנים נוספים בשעות זמניות"],
        ["להימנע מסעודה בערב שבת: "+reverse('09:00')],
        ["סוף אכילת חמץ: "+reverse('04:00')+", שריפה: "+reverse('05:00')],
        
        ["   זמנים במעלות כשהשמש תחת האופק"],
        [f"זריחת ושקיעת מרכז השמש: {reverse('0.0°')}"],
        [f"  זריחה ושקיעה במישור: {reverse('-0.833°')}"],
        
        [f"זמני צאת הכוכבים {reverse('3/4')} מיל במעלות", ""],
        [f"לפי מיל של {reverse('18')} דקות: {reverse('-3.65°')}"],
        [f"לפי מיל של {reverse('22.5')} דקות: {reverse('-4.2°')}"],
        [f"לפי מיל של {reverse('24')} דקות: {reverse('-4.61°')}"],
        [f"צאת כוכבים קטנים רצופים: {reverse('-6.3°')}"],
        
        ["  עלות השחר/צאת כוכבים דרת: במעלות"],
        [f"לפי 4 מיל של {reverse('18')} דקות: {reverse('-16.02°')}"],
        [f"לפי 4 מיל של {reverse('22.5')} דקות: {reverse('-19.75°')}"],
        [f"לפי 5 מיל של {reverse('24')} דקות: {reverse('-25.8°')}"],
        
        ["משיכיר/תחילת ציצית ותפילין: {reverse('-10.5°')}"],

        
        ["להלן תנאי מינימום לראיית ירח ראשונה"],
        [f"שלב {reverse('3%')}; והפרש גובה שמש-ירח {reverse('8°')}"],
    
    ]  

    
# פונקצייה שמחזירה את השעה במיקום שבו נמצאים כרגע כחותמת זמן
def get_current_location_timestamp():
    # הגדרות מאוד חשובות על איזה זמן יתבצעו החישובים
    # בתחילת הקוד גרמנו שהשעון החיצוני וגם הפנימי מעודכנים בשעה בגריניץ כלומר באיזור זמן UTC-0 . כעת צריך להמיר לשעון מקומי במיקום הנוכחי
    rtc_system_timestamp =  time.time() # או: utime.mktime(utime.localtime())
    current_utc_timestamp =  rtc_system_timestamp # כי בתחילת הקוד גרמנו שהשעון החיצוני יעדכן את השעון הפנימי בשעה באיזור זמן UTC-0
    # בדיקה האם המיקום הנוכחי הוא משווה 00 או הקוטב הצפוני אפס כי שם אני לא רוצה שיהיה שעון קיץ
    is_location_mashve_or_kotev = location["long"] == 0.0 and location["lat"] == 0.0 or location["long"] == 0.0 and location["lat"] == 90.0
    is_location_dst = True if is_now_israel_DST() and not is_location_mashve_or_kotev else False # כרגע כל שעון הקיץ או לא שעון קיץ נקבע לפי החוק בישראל גם עבור מקומות אחרים
    location_offset_hours = get_generic_utc_offset(location["long"], dst=is_location_dst) # חישוב הפרש הזמן מגריניץ עבור המיקום הנוכחי בשעות
    location_offset_seconds = get_generic_utc_offset(location["long"], dst=is_location_dst, in_seconds = True) # חישוב הפרש הזמן בשניות
    current_location_timestamp = current_utc_timestamp + location_offset_seconds # חותמת הזמן המקומית היא UTC-0 בתוספת הפרש השניות המקומי
    # עכשיו הגענו לנתון הכי חשוב שהוא חותמת הזמן המקומית הנוכחית
    return current_utc_timestamp, current_location_timestamp, location_offset_hours, location_offset_seconds


#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

settings_dict = {
    "rise_set_deg": -0.833, #-0.833 # מה גובה השמש בשעת זריחה ושקיעה. קובע לשעון שעה זמנית גרא ולהדפסת הזמנים
    "mga_deg": -16, # מה גובה השמש בשעת עלות השחר וצאת הכוכבים דרת. קובע לשעון שעה זמנית מגא ולהדפסת הזמנים
    "hacochavim_deg": -4.61, # מה גובה השמש בשעת צאת הכוכבים לשיטת הגאונים. קובע להדפסת הזמנים
    "misheiacir_deg": -10.5, # מה גובה השמש בשעת משיכיר. קובע להדפסת הזמנים
    "hesberim_mode": "hesberim", # "hesberim" or "zmanim", or "clocks"
    "default_location_index": 26, # מה מיקום ברירת המחדל שמוגדר. כרגע 26 זה ירושלים.
}

# שם ונתיב לקובץ ההגדרות של שעון ההלכה. חשוב מאוד לכל הקוד
settings_file_path = "halacha_clock/hw_settings.json"

# פונקצייה מאוד חשובה לטעינת כל ההגדרות של שעון ההלכה מתוך קובץ ההגדרות
def load_sesings_dict_from_file():
    global settings_dict, settings_file_path
    try:
        with open(settings_file_path, "r") as f:
            loaded_settings = ujson.load(f)
            # עדכון ההגדרות הקיימות עם הערכים מהקובץ כך שלא מאבדים ערכים שלא נמצאים בקובץ
            settings_dict.update(loaded_settings)
            #settings_dict = loaded_settings
            print(settings_dict)
            print("הגדרות נטענו בהצלחה מתוך הקובץ")
    except Exception as e:
        print(f"שגיאה בטעינת הקובץ: {e}")

load_sesings_dict_from_file() # טעינת ההגרות פעם אחת בתחילת הקוד


#@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@


# פונקצייה לשמירת המיקום האינדקסי של המיקום הנוכחי לקובץ מיקום ברירת מחדל כדי שזה המיקום שייפתח בפעם הראשונה שנכנסים לתוכנה
def save_default_location(index):
    """ שומר את המיקום הנוכחי בקובץ """
    try:
            global settings_dict, settings_file_path
            # עדכון כל ההגדרות החדשות במשתנה המילון הכללי של ההגדרות 
            setting_location = {"default_location_index": index}
            settings_dict.update(setting_location)
            
            # כל ההגדרות המעודכנות לקובץ JSON
            with open(settings_file_path, "w") as f:
                ujson.dump(settings_dict, f)
            
            # הדפסה למסך שנבחר מיקום ברירת מחדל חדש
            tft.fill(0) # מחיקת המסך
            tft.write(FontHeb20,f'{reverse("מיקום ברירת מחדל הוגדר בהצלחה")}',20,75)
            tft.write(FontHeb25,f'{reverse(locations[location_index]["heb_name"])}',120,100)
            tft.show() # כדי להציג את הנתונים על המסך
            time.sleep(2) # השהייה 5 שניות כדי שיהיה זמן לראות את ההודעה לפני שהמסך ייתמלא שוב בחישובים
            
    except Exception as e:
        print("שגיאה בשמירת המיקום:", e)

# הגדרת משתנה גלובלי חשוב מאוד שקובע מה המיקום הנוכחי שעליו מתבצעים החישובים
# משתנה זה נקבע לפי המיקום האינדקסי ששמור בקובץ מיקום ברירת מחדל תוך בדיקה שהאינדקס לא חורג מגבולות הרשימה ואם כן חורג אז יוגדר המיקום האפס כברירת מחדל
# קריאת המיקום מתוך הרשימה בהתאם למספר שבקובץ
default_index = None
location = None 
# אינדקס המיקום הנוכחי משתנה גלובלי חשוב מאוד לצורך התקדמות ברשימת המיקומים
# הגדרה שלו על אפס גורמת שכל דפדוף ברשימת המיקומים יתחיל מהתחלה ולא ימשיך מהמיקום האינדקסי של מיקום ברירת המחדל
location_index = None

# פונקצייה שמחזירה את מיקום ברירת המחדל להיות המיקום הנוכחי
def go_to_default_location():
    # הצהרה על משתנים גלובליים
    global location, location_index
    # מחזיר את המיקום הנוכחי להיות מיקום ברירת מחדל
    default_index = settings_dict["default_location_index"]
    location = locations[default_index] if 0 <= default_index < len(locations) else locations[0]
    # מאפס את המיקום שאוחזים בו בדפדוף ברשימת המיקומים כך שהדפדוף הבא יתחיל מהתחלה ולא מהמיקום האינדקסי של מיקום ברירת המחדל
    location_index = 0
    
go_to_default_location() # קריאה פעם אחת בתחילת הקוד 

##############################################################################################


# משתנה לשליטה על איזה נתונים יוצגו בהסברים במסך של שעון ההלכה בכל שנייה
current_screen_hesberim = 0.0  #

# משתנה לשליטה אלו נתונים יוצגו בשורת הזמנים 
current_screen_zmanim = 0

# משתנים גלובליים
last_state_for_rise_set_calculation = None  # כאן נשמור את מצב כל הנתונים בפעם האחרונה. אם משהו כאן משתנה צריך לחשב מחדש זריחות ושקיעות
last_location_riset = None # עבור אובייקט שמחזיק את חישובי השמש הירח הזריחות והשקיעות

# הפונקצייה הראשית שבסוף גם מפעילה את הנתונים על המסך
def main_halach_clock():
                 
    # הצהרה על משתנים גלובליים ששומרים את הזמנים הדרושים
    global last_state_for_rise_set_calculation, last_location_riset
    global sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise
    global tset_hacochavim, misheiakir
     
    # קבלת הזמן המקומי למיקום המבוקש כחותמת זמן - באמצעות פונקצייה שהוגדרה לעיל    
    current_utc_timestamp, current_location_timestamp, location_offset_hours, location_offset_seconds = get_current_location_timestamp()
    current_timestamp = current_location_timestamp
    
    # הגדרת הזמן הנוכחי המקומי מחותמת זמן לזמן רגיל
    tm = time.gmtime(current_location_timestamp) # אסור להשתמש כאן ב time.localtime כי זה בפייתון רגיל מחזיר זמן מקומי של המחשב
    year, month, day, rtc_week_day, hour, minute, second, micro_second = (tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0)
    
    # הגדרת התאריך הנוכחי המקומי
    current_location_date = (year, month, day)
    
    # חישוב מה השעה הנוכחית בשבר עשרוני עבור חישובי גובה ואזימוט בהמשך הפונקצייה
    current_hour = (hour + (minute / 60) + (second / 3600)) - location_offset_hours
    
    # יצירת חתימה (state) של כל מה שחשוב לחישוב מחדש של זריחות ושקיעות
    current_state_for_rise_set_calculation = (
        location, # אם משתנה מיקום
        current_location_date, # אם משתנה תאריך
        location_offset_hours, # אם משתנה משעון קיץ לחורף או להיפך
        settings_dict["rise_set_deg"], # אם משתנה גובה המעלות שמגדיר את השיטה
        settings_dict["mga_deg"], # אם משתנה גובה המעלות שמגדיר את השיטה
        settings_dict["hacochavim_deg"], # אם משתנה גובה המעלות שמגדיר את השיטה
        settings_dict["misheiacir_deg"], # אם משתנה גובה המעלות שמגדיר את השיטה
    )
     
    # אם המצב השתנה — נחשב מחדש. בהפעלה הראשונה תמיד נכנס לכאן כי בתחילה הוגדר על None
    if current_state_for_rise_set_calculation != last_state_for_rise_set_calculation:
        print("שינוי בזיהוי — מחשב מחדש זריחות ושקיעות")
        # ריקון כל המשתנים כדי שלא ישתמשו בנתונים לא נכונים
        sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
        tset_hacochavim, misheiakir = [None] * 2
        
        # מגדירים את משתנה המחלקה tim לזמן הרצוי. אם לא מגדירים אז הזמן הוא לפי הזמן הפנימי של הבקר או המחשב
        RiSet.tim = round(current_location_timestamp)
          
        # tlight_deg קובע כמה מעלות תחת האופק ייחשב דמדומים ואם לא מוגדר אז לא מחושב
        # riset_deg קובע כמה מעלות תחת האופק ייחשב זריחה ושקיעה ואם לא מוגדר אז מחושב -0.833 
        # יצירת אובייקט RiSet # הקריאה הזו כבר מחשבת נתוני זריחות ושקיעות באותו יום אבל ממילא מוכרחים בסוף להגדיר riset.set_day(0) ואז יחושבו שוב
        riset = RiSet(lat=location["lat"], long=location["long"], lto=location_offset_hours, riset_deg=settings_dict["rise_set_deg"], tlight_deg= settings_dict["mga_deg"]) # lto=location_offset_hours ####
        
        # הגדרת התאריך על היום הקודם ושמירת המידע הדרוש 
        riset.set_day(-1)
        yesterday_sunset, mga_yesterday_sunset = riset.sunset(1), riset.tend(1)
        
        # הגדרת התאריך על היום הבא ושמירת המידע הדרוש
        riset.set_day(1)
        tomorrow_sunrise, mga_tomorrow_sunrise  = riset.sunrise(1), riset.tstart(1)
        
        # החזרת הגדרת התאריך ליום הנוכחי ושמירת המידע הדרוש
        # חייבים תמיד שהחזרה ליום הנוכחי תהיה האחרונה כדי שבסוף יישאר ריסט שמוגדר על התאריך הנוכחי
        riset.set_day(0)
        sunrise, sunset, mga_sunrise, mga_sunset = riset.sunrise(1), riset.sunset(1), riset.tstart(1), riset.tend(1)
            
        ##########################################################################
        # חישוב דמדומים נוספים עבור צאת הכוכבים או משיכיר את חבירו וכדומה באמצעות מופע מחלקה חדש
        # אני מנצל כאן את הגדרת גובה הזריחה והשקיעה וגובה הדמדומים ובמקום זה עושה את הגבהים המבוקשים עבורי
        # בכל מופע כזה אפשר לחשב 2 זמנים שלכל אחד מהם יש התחלה וסוף - וההתחלה זה זריחה והסוף זה שקיעה
        # אם השמש לא מגיעה לגובה המבוקש בתאריך ובמיקום המבוקש - זה מחזיר None
        # כאן לא צריך לחשב עבור היום הקודם אלא זה מידע ליממה הנוכחית. לכן לא צריך להגדיר riset1.set_day(0) כי זה קורה לבד
        riset1 = RiSet(lat=location["lat"], long=location["long"], lto=location_offset_hours, riset_deg=settings_dict["hacochavim_deg"], tlight_deg=settings_dict["misheiacir_deg"])
        tset_hacochavim, misheiakir = riset1.sunset(1), riset1.tstart(1)
        ########################################################################
        # עדכון המשתנים הגלובליים למיקום ולתאריך הנוכחי ולהפרש גריניץ הנוכחי ולריסט המוגדר על היום הנוכחי
        last_location_riset = riset
        last_state_for_rise_set_calculation = current_state_for_rise_set_calculation
        ##########################################
        
   
    # בכל מקרה ריסט הוא הקודם שההיה בשימוש כדי לחסוך בחישובים מיותרים
    # והריסט הקודם עודכן לעיל להיות עדכני אם השתנה המיקום או התאריך
    riset = last_location_riset
   
    ############# חישוב גובה ואזימוט של השמש והירח ברגע הנוכחי ###########
    ####### חובה לעשות את זה לאחר שריסט מוגדר על היום הנוכחי ######
    
    # חישוב גובה השמש והירח וגם אזימוט ועלייה ישרה (עלייה ישרה בשעות עשרוני) ברגע זה. כלומר בשעה הנוכחית בשבר עשרוני
    # לדעת את גובה השמש והירח אפשר גם במיקום שאין בו זריחות ושקיאות וזה לא מחזיר שגיאה אלא מחזיר None שזה כמו אפס
    s_alt, s_az, s_ra, s_dec = riset.alt_az_ra_dec(current_hour, sun=True)
    m_alt, m_az, m_ra, m_dec = riset.alt_az_ra_dec(current_hour, sun=False)
       
    # הדפסות לניסיון כשיש בעיות
    print_times = False
    if print_times:
        print("sunrise",format_time(time.gmtime(sunrise), with_date=True))
        print("sunset", format_time(time.gmtime(sunset), with_date=True))
        print("mga_sunrise",format_time(time.gmtime(mga_sunrise), with_date=True))
        print("mga_sunset", format_time(time.gmtime(mga_sunset), with_date=True))
        print("misheiakir",format_time(time.gmtime(misheiakir), with_date=True))
        print("tset_hacochavim", format_time(time.gmtime(tset_hacochavim), with_date=True))
        print("")
       
   ################## חישוב השעה הזמנית הנוכחית גרא ומגא  ##################
   
    # כל החישובים נעשים רק אם יש זריחה ושקיעה ביממה זו במיקום זה והזריחה היא לפני השקיעה. כי אולי במיקום הזה אין בכלל זריחה ושקיעה ביום זה
    if sunrise and sunset and sunrise < sunset:   
    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        sunrise_timestamp, sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = True)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        temporal_time, seconds_in_temporal_hour = calculate_temporal_time(current_timestamp, sunrise_timestamp, sunset_timestamp)
        minutes_in_temporal_hour = str(round(seconds_in_temporal_hour / 60,1)) # str(convert_seconds(seconds_in_temporal_hour))
             
    else:
        
        temporal_time = reverse("שגיאה  ")
        minutes_in_temporal_hour = "0.0"
        
    
    # כל החישובים נעשים רק אם יש זריחה ושקיעה של מגא ביממה זו במיקום זה והזריחה היא לפני השקיעה.
    # כי אולי במיקום הזה אין בכלל זריחה ושקיעה ביום זה כלומר שהשמש לא יורדת אל מתחת האופק בצורה מסודרת ביממה זו
    if mga_sunrise and mga_sunset and mga_sunrise < mga_sunset:

        # חישוב מחדש עבור שיטת מגן אברהם    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        mga_sunrise_timestamp, mga_sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = False)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        mga_temporal_time, seconds_in_mga_temporal_hour = calculate_temporal_time(current_timestamp, mga_sunrise_timestamp, mga_sunset_timestamp)
        minutes_in_mga_temporal_hour = str(round(seconds_in_mga_temporal_hour / 60,1)) # str(convert_seconds(seconds_in_mga_temporal_hour))
    else:
        
        mga_temporal_time = reverse("שגיאה  ")
        minutes_in_mga_temporal_hour = "0.0"


    ##################### חישוב שלב הירח הנוכחי ##########################
    
    MoonPhase.tim = round(current_timestamp) ############### אם לא מגדירים את זה אז הזמן הוא לפי הזמן הפנימי של הבקר
    mp = MoonPhase(lto=location_offset_hours)  # כולל הגדרת ההפרש מגריניץ במיקום הנוכחי
    phase = mp.phase()
    phase_percent = round(phase * 100,1)
                      
    ##################################################################################################################3
    # משתנה שמחזיר טרו אם הזמן הוא כרגע אחרי השקיעה ולפני 12 בלילה ולכן התאריך העברי הנכון הוא התאריך הלועזי הבא
    heb_date_is_next_greg_date = sunset and current_timestamp > sunset and current_timestamp > sunrise # current_timestamp > sunrise אומר שמדובר לפני 12 בלילה
    
    # אם התאריך העברי מקביל לתאריך הלועזי של מחר כי מדובר אחרי השקיעה ולפני 12 בלילה מחשבים את הנתונים על מחר
    if heb_date_is_next_greg_date:    
        # חישוב התאריך הלועזי של מחר כלומר בדיוק עוד 24 שעות. זה נדרש כי התאריך העברי מהשקיעה עד 12 בלילה שווה לתאריך הלועזי של מחר
        tomorrow_tm = utime.localtime(current_timestamp+86400) # יש 86400 שניות ביממה
        g_year, g_month, g_day, g_rtc_week_day = (tomorrow_tm[0], tomorrow_tm[1], tomorrow_tm[2], tomorrow_tm[6])
    
    # בכל מקרה אחר התאריך העברי מקביל לתאריך הלועזי הנוכחי
    else:
        g_year, g_month, g_day, g_rtc_week_day = year, month, day, rtc_week_day
    
    
    # חישוב תאריך עברי נוכחי באמצעות ספרייה ייעודית. כמו כן מחושב האם מדובר בחג
    heb_date_string, tuple_heb_date, holiday_name, lite_holiday_name, is_rosh_chodesh = mpy_heb_date.get_heb_date_and_holiday_from_greg_date(g_year, g_month, g_day)
    # חישוב היום בשבוע המתאים לתאריך העברי הנכון לרגע זה
    heb_weekday = get_normal_weekday(g_rtc_week_day)
    # שם בעברית של היום העברי המתאים לתאריך העברי הנוכחי המוגדר משקיעה מישורית לשקיעה מישורית
    heb_weekday_string = mpy_heb_date.heb_weekday_names(heb_weekday)

    ##############################################################################
    # איזור שאחראי להגדיר ששעון ההלכה לא ייכנס אוטומטית למצב שינה בשבת ובחג. אך לא מחושב יום טוב שני
    
    # חישוב האם שבת. שבת מוגדרת מהשקיעה של סוף יום שישי עד השקיעה של סוף שבת
    is_shabat = heb_weekday == 7

    # פונקציית עזר פנימית לבדיקה האם נמצאים מהשקיעה ועד מוצאי היום העברי
    # כברירת מחדל מוצאי היום העברי זה כשהשמש מינוס 4.6 מעלות תחת האופק
    # מוצאי שבת בלוחות הרגילים זה כשהשמש מינוס 8.5 מעלות תחת האופק
    def is_sunset_until_motsaei(degrees_for_motsaei = -4.6):
        return sunset and current_timestamp > sunset and s_alt > degrees_for_motsaei
    
    # חישוב תוספות לשבת כלומר מיום שישי חצי שעה לפני השקיעה עד השקיעה וכן בשבת מהשקיעה ועד צאת שבת שבלוחות
    normal_weekday = get_normal_weekday(rtc_week_day) # חישוב היום בשבוע של התאריך הלועזי בדווקא
    half_hour_before_sunset_until_sunset =  sunset and current_timestamp >= (sunset - 1800) and current_timestamp < sunset # 1800 שניות זה חצי שעה לפני השקיעה
    is_tosafot_leshabat = (normal_weekday == 6 and half_hour_before_sunset_until_sunset) or (normal_weekday == 7 and is_sunset_until_motsaei(degrees_for_motsaei = -8.5))
    shabat_before_motsaei_6 = (normal_weekday == 7 and is_sunset_until_motsaei(degrees_for_motsaei= -6))
    
    
    # הגדרת ביטול כיבוי אוטומטי בשבת וחג. וכן מחצי שעה לפני השקיעה בשבת ועד מוצאי שבת שבלוחות
    global automatic_deepsleep
    automatic_deepsleep = False if is_shabat or is_tosafot_leshabat or holiday_name else True
    ##############################################################################
    
    # חישוב שעונים נוספים ומידע נוסף
    #####################
    
    #1. שעון שעות מהשקיעה שנקרא שעון המגרב
    # השקיעה האחרונה שהייתה היא בדרך כלל השקיעה של אתמול. אבל בין השקיעה לשעה 12 בלילה השקיעה האחרונה היא השקיעה של היום
    last_sunset_timestamp = yesterday_sunset if (sunset and current_timestamp < sunset) else sunset
    # חישוב כמה שניות עברו מאז הזריחה או השקיעה עד הזמן הנוכחי #time_since_last_sunset = current_timestamp - last_sunset_timestamp
    magrab_time_string = convert_seconds((current_timestamp - last_sunset_timestamp), to_hours=True) if last_sunset_timestamp else reverse("שגיאה  ") # רק אם יש שקיעה אחרונה אפשר לחשב
    
    ########### 2. שעון מקומי ממוצע, שעון מקומי שמשי אמיתי שחצות תמיד ב 12:00, ומשוואת הזמן
     
    local_mean_time_string, local_solar_time_string, equation_of_time_string = LMT_LST_EOT(current_utc_timestamp, location["long"]) # חייב לקבל זמן utc ולא מקומי
    
    ######## 3. השעה הנוכחית בגריניץ
    gm_time_now = time.gmtime(current_utc_timestamp)
    gm_time_now_string = format_time(gm_time_now)
    
    ######### 4. דלטא_טי
    delta_t = calculate_delta_t(year)

    
    ############################################################################
    # איזור הדפסת זמנים בשעון רגיל
    
    #חישוב מספר השניות מהזריחה לשקיעה
    seconds_day_gra = (sunset - sunrise) / 12 if sunrise and sunset else None
    seconds_day_mga = (mga_sunset - mga_sunrise) / 12 if mga_sunrise and mga_sunset else None
    
        ###################################################
    def hhh(start_time, seconsd_per_hour, hour, round_minute = True):
        # כשאין זריחה או שקיעה אי אפשר לחשב שעות זמניות
        if start_time == None:
            return "שגיאה"
        AAA = start_time + (seconsd_per_hour * hour)      
        # עיגול לדקה הקרובה אם רוצים
        total_seconds = int(AAA + 30) // 60 * 60 if round_minute else AAA
        time_value = time.gmtime(total_seconds)
        return format_time(time_value, with_seconds=False if round_minute else True)
        ##################################################
    
    zmanim = [
        ["זמנים בשעון רגיל - עיגול לדקה קרובה"],
        [f"עלות השחר: {reverse(hhh(mga_sunrise, 0, 0))} | משיכיר: {reverse(hhh(misheiakir, 0, 0))}"], 
        [f"זריחה גרא: {reverse(hhh(sunrise, seconds_day_gra, hour=0))}"],
        [f"סוף שמע: מגא - {reverse(hhh(mga_sunrise, seconds_day_mga, hour=3))}, גרא - {reverse(hhh(sunrise, seconds_day_gra, hour=3))}"], 
        [f"סוף תפילה: מגא - {reverse(hhh(mga_sunrise, seconds_day_mga, hour=4))}, גרא - {reverse(hhh(sunrise, seconds_day_gra, hour=4))}"],
        [f"חצות היום - וכנגדו בלילה: {reverse(hhh(sunrise, seconds_day_gra, hour=6))}"],
        [f"מנחה: גדולה - {reverse(hhh(sunrise, seconds_day_gra, hour=6.5))}, קטנה - {reverse(hhh(sunrise, seconds_day_gra, hour=9.5))}"],
        [f"פלג המנחה - {reverse(hhh(sunrise, seconds_day_gra, hour=10.75))}"],
        [f"שקיעה גרא: {reverse(hhh(sunrise, seconds_day_gra, hour=12))}"],
        [f"כוכבים: גאונים - {reverse(hhh(tset_hacochavim, 0, 0))}, רת - {reverse(hhh(mga_sunrise, seconds_day_mga, hour=12))}"],
    ]
    
    ### הכנה לשורת שעונים. הרווחים הם בכוונה לצורך מירכוז בשעון ההלכה הפיזי
    clocks_string = f"           {magrab_time_string}  {local_mean_time_string}  {local_solar_time_string}  {gm_time_now_string}"
    
    # משתנה ששומר מערך זמנים שבו אחרי כל שורת זמן יש שורת שעונים וכך הזמנים והשעונים מוצגים לסירוגין
    zmanim_with_clocks = [item for zman_line in zmanim for item in (zman_line, [reverse(clocks_string)])]
 
    #############################################################################
    
    
    # מכאן והלאה ההדפסות למסך
    
    # חישוב אחוזי הסוללה שנותרו או האם מחובר לחשמל
    global last_battery_percentage, last_is_charging
    voltage_string = f"**%" if last_is_charging else f"{last_battery_percentage}%"
    
    greg_date_string = f'{day:02d}/{month:02d}/{year:04d}{"!" if time_source in [3,4] else ""}' 
    time_string = f'{hour:02d}:{minute:02d}:{second:02d}{"!" if time_source in [3,4] else ""}'
    
    # מהשקיעה עד 12 בלילה מוסיפים את המילה ליל כי היום בשבוע והתאריך העברי מקבלים לתאריך הלועזי של מחר
    leil_string = reverse("ליל:") if heb_date_is_next_greg_date else ""
    # אם אין שעון והוגדר זמן שרירותי או שהשעה נלקחה מהשעון הפנימי שכנראה אינו מדוייק מוסיפים סימני קריאה אחרי התאריך העברי
    heb_date_to_print = f'   {"!!" if not time_source else ""}{reverse(heb_date_string)} ,{reverse(heb_weekday_string)} {leil_string}'
    utc_offset_string = 'utc+00' if location_offset_hours == 0 else f'utc+{location_offset_hours:02}' if location_offset_hours >0 else f'utc-{abs(location_offset_hours):02}'
    coteret = f'  {voltage_string} - {reverse(location["heb_name"])} - {reverse("שעון ההלכה")}'
    
    tft.fill(0) # מחיקת המסך

    # איזור כותרת
    tft.write(FontHeb20,f'{coteret}',center(coteret,FontHeb20),0, s3lcd.GREEN, s3lcd.BLACK) #fg=s3lcd.WHITE, bg=s3lcd.BLACK בכוונה מוגדר אחרי השורה הקודמת בגלל הרקע הצהוב
    
    # איזור תאריך עברי כולל צבע מתאים לימי חול ולשבתות וחגים
    # צבע הטקסט והרקע של התאריך העברי: ביום חול לבן על שחור ובשבת וחג שחור על צהוב, ובחגים דרבנן כולל תעניות שחור על ציאן
    HEB_DATE_FG, HEB_DATE_BG  = (s3lcd.BLACK, s3lcd.YELLOW) if is_shabat or holiday_name or shabat_before_motsaei_6 else (s3lcd.BLACK, s3lcd.CYAN) if lite_holiday_name or is_rosh_chodesh else (s3lcd.WHITE, s3lcd.BLACK)
    tft.write(FontHeb25,f'{heb_date_to_print}',center(heb_date_to_print,FontHeb25),20, HEB_DATE_FG, HEB_DATE_BG)
   
    # איזור שעה זמנית
    mga_string = "מגא!" if settings_dict["mga_deg"] != -16 else "מגא"
    gra_string = "גרא!" if settings_dict["rise_set_deg"] != -0.833 else "גרא "
    tft.write(FontHeb20,f'{reverse(mga_string)}',100,46)
    tft.write(FontHeb20,f'{reverse(gra_string)}',280,46)
    tft.write(FontHeb40,f'{temporal_time}', 140, 45, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{minutes_in_temporal_hour}',283,62, s3lcd.CYAN, s3lcd.BLACK) # אם עושים דקות ושניות אז המיקום 277 ולא 283 אבל אין מקום
    tft.write(FontHeb25,f' {mga_temporal_time}', 0, 50, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{minutes_in_mga_temporal_hour}',102,62, s3lcd.CYAN, s3lcd.BLACK) # אם עושים דקות ושניות אז המיקום 96 ולא 102
  
    # איזור גובה אזימוט שמש וירח ושלב ירח
    tft.write(FontHeb20,f'                 {reverse("ירח")}                         {reverse("שמש")}',0,82)
    tft.write(FontHeb20,f'{"  " if m_az < 10 else " " if m_az < 100 else ""}{round(m_az)}°', 98,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{"  " if s_az < 10 else " " if s_az < 100 else ""}{round(s_az)}°', 281,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb25,f' {" " if m_alt > 0 else ""}{" " if abs(m_alt) <10 else ""}{m_alt:.3f}°',0,80, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'    {phase_percent:.1f}%',0,101, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb40,f"{" " if s_alt > 0 else ""}{" " if abs(s_alt) <10 else ""}{round(s_alt,3):.3f}°", 140, 81, s3lcd.GREEN, s3lcd.BLACK)
    
    # הכנה לשורת הסברים מתחלפת
    global current_screen_hesberim
    hesberim_string = reverse(hesberim[int(current_screen_hesberim)][0])  # רוורס של הטקסט העברי
    current_screen_hesberim = (current_screen_hesberim + 0.3) % len(hesberim)  # זה גורם מחזור של שניות לאיזה נתונים יוצגו במסך
    
    # הכנה לשורת זמנים מתחלפת
    global current_screen_zmanim
    zmanim_string = reverse(zmanim[int(current_screen_zmanim)][0])
    zmanim_with_clocks_string = reverse(zmanim_with_clocks[int(current_screen_zmanim)][0]) 
    current_screen_zmanim = (current_screen_zmanim + 0.15) % len(zmanim)
    
    # קביעה מה יודפס בשורת ההסברים: האם שעונים זמנים או הסברים. ולאחר מכן הדפסה למסך של מה שנבחר   
    hesberim_zmanim_clocks = settings_dict["hesberim_mode"]
    hesberim_zmanim_clocks_options_dict = {"zmanim": zmanim_string,"clocks": clocks_string,"zmanim_with_clocks": zmanim_with_clocks_string}
    print_in_hesberim_line = hesberim_zmanim_clocks_options_dict.get(hesberim_zmanim_clocks, hesberim_string) # ערך ברירת המחדל הוא הסברים 
    tft.write(FontHeb20, f"{print_in_hesberim_line}" ,center(print_in_hesberim_line, FontHeb20) , 123)  # כתיבה למסך
    
    # איזור תאריך לועזי ושעה רגילה והפרש מגריניץ
    tft.write(FontHeb25,f' {greg_date_string}                 {utc_offset_string}',0,147)
    tft.write(FontHeb30,f'{time_string}', 133, 145, s3lcd.GREEN, s3lcd.BLACK)
    # הכנה לאם רוצים להדפיס במקום הפרש מגריניץ את השעון המקומי השמשי האמיתי או את שעון המגרב
    # מיקומי ההדפסה בתוך השורה הם החשובים והם השונים כאן כאשר לא מדפיסים את utc_offset_string
    #tft.write(FontHeb25,f'{greg_date_string}                {local_solar_time_string}',0,147)
    #tft.write(FontHeb30,f'{time_string}', 125, 145, s3lcd.GREEN, s3lcd.BLACK)


    # איזור קווי הפרדה. חייב להיות אחרי הכל כדי שיעלה מעל הכל
    tft.line(0, 45, 320, 45, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 80, 320, 80, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 120, 320, 120, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 145, 320, 145, s3lcd.YELLOW) # קו הפרדה

    tft.show() # כדי להציג את הנתונים על המסך


############################################################################################################################################################
#################################################################   איזור הטיפול במד טמפרטורה לחות ולחץ ברומטרי  ###########################################
############################################################################################################################################################

# פונקצייה לקבלת הזמן המשמש בכל החלק בקוד שמטפל במזג האוויר
# מדובר בזמן מקומי במיקום ברירת המחדל המוגדר
def get_location_localtime():
    # מקבל את השעה המקומית במיקום ברירת המחדל כחותמת זמן
    current_utc_timestamp, current_location_timestamp, location_offset_hours, location_offset_seconds = get_current_location_timestamp()
    # מחזיר את הזמן המקומי כפורמט זמן רגיל
    return utime.localtime(current_location_timestamp)


# Variables for minimum and maximum tracking
min_temp = float('inf')
max_temp = float('-inf')
min_humidity = float('inf')
max_humidity = float('-inf')
min_pressure = float('inf')
max_pressure = float('-inf')

min_time_temp = get_location_localtime()
max_time_temp = get_location_localtime()
min_time_humidity = get_location_localtime()
max_time_humidity = get_location_localtime()
min_time_pressure = get_location_localtime()
max_time_pressure = get_location_localtime()

# Variable for current day tracking
current_date = get_location_localtime()[0:3]

# משתנה לשליטה על איזה נתונים יוצגו במין/מקס במסך של מד הטמפרטורה בכל שנייה
current_screen_bme280 = 0.0  # 0: Temperature, 1: Humidity, 2: Pressure


def get_bme_280_data():
    """Reads temperature, humidity, and pressure from BME280 sensor."""
    temp = float(bme.temperature[:-1])
    humidity = float(bme.humidity[:-1])
    pressure = float(bme.pressure[:-3])
    return temp, humidity, pressure

def update_min_max(temp, humidity, pressure):
    """Updates minimum and maximum values for temperature, humidity, and pressure."""
    global min_temp, max_temp, min_humidity, max_humidity, min_pressure, max_pressure
    global min_time_temp, max_time_temp, min_time_humidity, max_time_humidity, min_time_pressure, max_time_pressure

    if temp < min_temp:
        min_temp = temp
        min_time_temp = get_location_localtime()
    if temp > max_temp:
        max_temp = temp
        max_time_temp = get_location_localtime()

    if humidity < min_humidity:
        min_humidity = humidity
        min_time_humidity = get_location_localtime()
    if humidity > max_humidity:
        max_humidity = humidity
        max_time_humidity = get_location_localtime()

    if pressure < min_pressure:
        min_pressure = pressure
        min_time_pressure = get_location_localtime()
    if pressure > max_pressure:
        max_pressure = pressure
        max_time_pressure = get_location_localtime()

def reset_min_max_if_new_day():
    """Resets minimum and maximum values if the day changes."""
    global min_temp, max_temp, min_humidity, max_humidity, min_pressure, max_pressure
    global min_time_temp, max_time_temp, min_time_humidity, max_time_humidity, min_time_pressure, max_time_pressure
    global current_date

    today = get_location_localtime()[0:3]
    if today != current_date:
        current_date = today
        min_temp = float('inf')
        max_temp = float('-inf')
        min_humidity = float('inf')
        max_humidity = float('-inf')
        min_pressure = float('inf')
        max_pressure = float('-inf')
        min_time_temp = get_location_localtime()
        max_time_temp = get_location_localtime()
        min_time_humidity = get_location_localtime()
        max_time_humidity = get_location_localtime()
        min_time_pressure = get_location_localtime()
        max_time_pressure = get_location_localtime()

def format_time_bme(time_tuple):
    """Formats time tuple to HH:MM."""
    return '{:02}:{:02}'.format(time_tuple[3], time_tuple[4])

def main_bme280():
    """Displays sensor readings and additional information on OLED."""
    global current_screen_bme280

    temp, humidity, pressure = get_bme_280_data()
    # ייתכן שההורדה בשלושים נכונה רק עבור הגובה של מודיעין עילית ואילו במקומות אחרים יצטרכו להוריד ביחס זהה בהתאמה לגובה. צריך לבדוק
    pressure -= 30 # הורדת הלחץ ב-30 זה תיקון הכרחי כי החיישן לא מודד טוב אלא נותן 30 יותר ממה שבאמת ולא יודע למה זה
    # גובה התחנה
    altitude = 320
    # תיקון חישוב הלחץ לגובה פני הים 
    delta_p = 12 * (altitude/100) # כלל האצבע: לחץ האוויר יורד בכ-12 hPa לכל 100 מטרים בגובה
    pressure_at_sea_level = pressure + delta_p
    update_min_max(temp, humidity, pressure_at_sea_level)
    reset_min_max_if_new_day()
    
    # Calculate dew point
    dew_point = temp - ((100 - humidity) / 5)
    
    # חישוב אחוזי הסוללה שנותרו או האם מחובר לחשמל
    global last_battery_percentage, last_is_charging
    voltage_string = f"**%" if last_is_charging else f"{last_battery_percentage}%"
    
    tft.fill(0)

    t = get_location_localtime()
    time_string = "{:02d}/{:02d}/{:04d} {:02d}:{:02d}:{:02d}".format(t[2], t[1], t[0], t[3], t[4], t[5]) # להוסיף יום בשבוע
    tft.write(FontHeb25,f'    {time_string}     {voltage_string}', 0, 0)
    tft.write(FontHeb20,f'                    {reverse("לחות")}                   {reverse("טמפ.")}',0,30)
    tft.write(FontHeb40,f'{temp:.1f}c', 180, 20, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb40,f' {humidity:.1f}%', 0, 20, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb25,f'              {dew_point:.1f} c :{reverse("נקודת טל")}', 0, 54)
    
    tft.write(FontHeb25,f'{pressure:.1f} hPa  {reverse("לחץ בגובה")}', 50, 77)
    tft.write(FontHeb25,f'{pressure_at_sea_level:.1f} hPa  {reverse("לחץ מתוקן")}', 50, 100)
    
    screen = int(current_screen_bme280)

    if screen == 0:  # Temperature
        tft.write(FontHeb25,f'{format_time_bme(min_time_temp)} {reverse("בשעה")} {min_temp:.1f}c {reverse("מינ טמפ")}', 20, 125)
        tft.write(FontHeb25,f'{format_time_bme(max_time_temp)} {reverse("בשעה")} {max_temp:.1f}c    {reverse("מקס")}', 20, 145)

    elif screen == 1:  # Humidity
        tft.write(FontHeb25,f'{format_time_bme(min_time_humidity)} {reverse("בשעה")} {min_humidity:.1f}% {reverse("מינ לחות")}', 10, 125)
        tft.write(FontHeb25,f'{format_time_bme(max_time_humidity)} {reverse("בשעה")} {max_humidity:.1f}%    {reverse("מקס")}', 10, 145)
    
    elif screen == 2:  # Pressure
        tft.write(FontHeb25,f'{format_time_bme(min_time_pressure)} {reverse("בשעה")} {min_pressure:.1f}hPa {reverse("מינ לחץ")}', 0, 125)
        tft.write(FontHeb25,f'{format_time_bme(max_time_pressure)} {reverse("בשעה")} {max_pressure:.1f}hPa    {reverse("מקס")}', 0, 145)
    
    # קידום בצעד אחד קדימה
    current_screen_bme280 = (current_screen_bme280 + 0.1) % 3  # Cycle through screens (0, 1, 2)
        
    tft.show()



#############################################################################################################################################################
###########################################################  סוף קוד המטפל במד טמפרטורה לחות ולחץ ברומטרי  #############################################
#############################################################################################################################################################


# משתנים חשובים מאוד לשמירת הזמן בתחילה כדי להשוות אליהם בהמשך ולדעת האם לעדכן דברים או לכבות את המסך וכדומה
t_time = time.time()
start_time_for_check_and_set_time = t_time
start_time_for_automatic_deepsleep = t_time

#########################################################################################################

# הפעלה של התפריט
def menu_settings_loop(only_key=None):

    # כל האפשרויות – לא צריך לטעון מהפעם הקודמת
    menu_items = [
        {"title": "בחר שיטת זריחה ושקיעה", "key": "rise_set_deg", "options": [0, -0.833], "suffix": "°"},
        {"title": "בחר שיטת מגא ועלות", "key": "mga_deg", "options": [-16, -19.75], "suffix": "°"},
        {"title": "בחר שיטת כוכבים", "key": "hacochavim_deg", "options": [-4.61, -3.61, -6, -8.5], "suffix": "°"},
        {"title": "בחר שיטת משיכיר", "key": "misheiacir_deg", "options": [-10.5, -10], "suffix": "°"},
        #{"title": "בחר בהירות מסך", "key": "screen_brightness", "options": [100, 250, 500, 1000], "suffix": ""},
        {"title": "בחר מה להציג בשורה", "key": "hesberim_mode", "options": ["hesberim", "zmanim", "clocks", "zmanim_with_clocks"], "suffix": ""},
    ]
    
    modes_hebrew = {
        "hesberim": reverse("הסברים ומידע"),
        "zmanim": reverse("זמנים"),
        "clocks": reverse("שעונים"),
        "zmanim_with_clocks": reverse("זמנים עם שעונים"),
        "screen_brightness": reverse("בהירות מסך"),
    }
    
    if only_key is not None:
        menu_items = [item for item in menu_items if item["key"] == only_key]
        if not menu_items:
            print(f"שגיאה: לא נמצא פריט עם המפתח {only_key}")
            return
    
    
    # אתחול אינדקסים תמיד מהאפשרות הראשונה
    for item in menu_items:
        item["index"] = 0

    # מילון לשמירה בסוף
    settings = {}

    total = len(menu_items)
    for stage, item in enumerate(menu_items, start=1):
        last_activity = time.time()  # זמן התחלה של המעקב
        while True:
            
            # בדיקה אם עברו 20 שניות בלי פעילות
            if time.time() - last_activity > 20:
                tft.fill(0)
                tft.write(FontHeb25, reverse("יציאה עקב חוסר פעילות"), 10, 60)
                tft.show()
                time.sleep(2)
                return  # יציאה מהפונקציה לגמרי
            
            tft.fill(0)
            tft.write(FontHeb20, reverse(f"לחיצה קצרה לשינוי, וארוכה לבחירה"), 20, 2, s3lcd.GREEN, s3lcd.BLACK)
            tft.write(FontHeb20, reverse(f"שלב {stage} מתוך {total}"), 20, 25, s3lcd.YELLOW, s3lcd.BLACK)
            tft.write(FontHeb20, reverse(item["title"]), 20, 50, s3lcd.GREEN, s3lcd.BLACK)

            index = item["index"]
            options = item["options"]
            value = options[index % len(options)]
            display_val = f"{reverse(str(modes_hebrew.get(value, value)))}{item['suffix']}"
            tft.write(FontHeb25, reverse(display_val), 100, 100)
            tft.show()

            duration = handle_button_press(boot_button)
            
            # זה גורם שאם אין שום לחיצה מדלגים על המשך הסיבוב הנוכחי בלולאה
            if not duration:
                continue
            
            # עדכון זמן התחלה של המעקב לאחר לחיצה.
            # אם הגענו לכאן חייב להיות שהייתה לחיצה
            last_activity = time.time()
            
            if duration == "short":
                item["index"] = (index + 1) % len(options)
            elif duration == "long":
                # שמירה של הבחירה במילון
                settings[item["key"]] = value
                tft.fill(0)
                tft.write(FontHeb25, reverse(f"נבחר: {display_val}"), 40, 80)
                tft.show()
                time.sleep(2)
                break
    
    # עדכון כל ההגדרות החדשות במשתנה המילון הכללי של ההגדרות 
    global settings_dict, settings_file_path
    settings_dict.update(settings)
    
    # כל ההגדרות המעודכנות לקובץ JSON
    with open(settings_file_path, "w") as f:
        ujson.dump(settings_dict, f)

    # הודעת סיום
    tft.fill(0)
    tft.write(FontHeb25, reverse("ההגדרות נשמרו!"), 40, 80)
    tft.show()
    time.sleep(1)
    # איפוס משתנים כדי שיתחילו ההסברים והזמנים מהתחלה אם נבחרו
    global current_screen_hesberim, current_screen_zmanim
    current_screen_hesberim = 0.0
    current_screen_zmanim = 0
    load_sesings_dict_from_file() # טעינת ההגדרות החדשות
    
# פונקצייה להצגת מידע על התוכנה    
def show_about():
    last_activity = time.time()
    tft.fill(0)
    tft.write(FontHeb25, reverse("אודות שעון ההלכה"), center(reverse("אודות שעון ההלכה"), FontHeb25), 5, s3lcd.GREEN, s3lcd.BLACK)
    #tft.write(FontHeb20, reverse("לחצו לחיצה ארוכה ליציאה"), center(reverse("לחצו לחיצה ארוכה ליציאה"), FontHeb20), 25)
    tft.write(FontHeb20, reverse(f"גרסה"), center(reverse(f"גרסה"), FontHeb20), 40)
    tft.write(FontHeb20, reverse(f"{reverse(VERSION)}"), center(reverse(f"{reverse(VERSION)}"), FontHeb20), 56, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20, reverse("שמחה גרשון בורר - כוכבים וזמנים"), center(reverse("שמחה גרשון בורר - כוכבים וזמנים"), FontHeb20), 90)
    tft.write(FontHeb20, reverse(f'{reverse("sgbmzm@gmail.com")}'), center(reverse(f'{reverse("sgbmzm@gmail.com")}'), FontHeb20), 110)
    tft.write(FontHeb20, reverse(f'כל הזכויות שמורות'), center(reverse(f'כל הזכויות שמורות'), FontHeb20), 150)
    tft.show()
    # המתנה ללחיצה ארוכה או שיעברו 10 שניות כדי לצאת מהפונקצייה
    while True:
        if handle_button_press(boot_button) == "long" or time.time() - last_activity > 20:
            return

# === פונקצייה להצגת ההגדרות הנוכחיות ===
def show_current_settings():
    last_activity = time.time()  # זמן התחלה של המעקב
    tft.fill(0)
    tft.write(FontHeb25, reverse("הגדרות נוכחיות:"), 70, 5, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20, reverse("לחצו לחיצה ארוכה ליציאה"), 50, 30, s3lcd.GREEN, s3lcd.BLACK)
    y_pos = 50
    
    names_hebrew = {
        "rise_set_deg": "זריחה ושקיעה",
        "mga_deg": "מגא עלות השחר ורבינו תם",
        "hacochavim_deg": "צאת הכוכבים גאונים",
        "misheiacir_deg": "משיכיר",
        "hesberim_mode": "מצב תצוגה",
        "default_location_index": "מיקום ברירת מחדל",
        "screen_brightness": reverse("בהירות מסך"),
    }

    modes_hebrew = {
        "hesberim": "הסברים",
        "zmanim": "זמנים",
        "clocks": "שעונים",
        "zmanim_with_clocks": "זמנים עם שעונים",
    }


    # מעבר על כל מפתח במילון והצגתו
    for key, value in settings_dict.items():
        if key == "default_location_index":
            value = reverse(locations[value]["heb_name"])
        elif key == "hesberim_mode":
            value = reverse(modes_hebrew.get(value, value))
        line = f"{reverse(names_hebrew.get(key, key))}:  {value}°"
        tft.write(FontHeb20, line, 20, y_pos)
        y_pos += 20

    tft.show()

    # המתנה ללחיצה ארוכה או שתעבור דקה כדי לצאת מהפונקצייה
    while True:
        if handle_button_press(boot_button) == "long" or time.time() - last_activity > 20:
            return


def main_menu():
    # אפשרויות התפריט הראשי
    main_menu = [
        {"title": "הגדרת מיקום נוכחי כברירת מחדל", "action": "update_location"},
        {"title": "עדכון הזמן", "action": "update_time"},
        {"title": "הצגת הגדרות נוכחיות", "action": "show_settings"},
        {"title": "הגדרת שורת ההסברים", "action": "update_hesberim_mode"},
        {"title": "בחירת והגדרת כל ההגדרות", "action": "update_settings"}, 
        {"title": "אודות", "action": "show_about"},
        {"title": "יציאה", "action": "return"},
    ]

    index = 0
    choice_made = False

    # פונקצייה להצגת התפריט
    def show_menu():
        tft.fill(0)
        tft.write(FontHeb25, reverse("בחר אפשרות בלחיצה ארוכה:"), 20, 2,  s3lcd.GREEN, s3lcd.BLACK)
        y_pos = 30
        for i, item in enumerate(main_menu):
            prefix = "<" if i == index else " "  # סימן בחירה
            # כל שורה תוצג בגובה אחיד
            text_line = reverse(f"{prefix} {item['title']}")
            tft.write(FontHeb20, text_line, 20, y_pos)
            y_pos += 20
        tft.show()

    show_menu()

    # לולאת הבחירה
    while not choice_made:
        duration = handle_button_press(boot_button)
        if duration == "short":
            index = (index + 1) % len(main_menu)
            show_menu()

        elif duration == "long":
            choice_made = True
            selected = main_menu[index]

            # הפעלת פעולה מתאימה
            if selected["action"] == "update_location":
                save_default_location(location_index)
            if selected["action"] == "update_time":
                check_and_set_time(Force_update = True)
            elif selected["action"] == "update_settings":
                menu_settings_loop()
            elif selected["action"] == "update_hesberim_mode":
                menu_settings_loop("hesberim_mode")
            elif selected["action"] == "show_settings":
                show_current_settings()
            elif selected["action"] == "show_about":
                show_about()
            elif selected["action"] == "return":
                return

#######################################################################################################

def toggle_boot_button(pin):
    """ מטפל בלחיצה על הכפתור של שינוי וטיפול במיקומים ומבדיל בין לחיצה קצרה ללחיצה ארוכה """
    
    #######################################################
    # אין לפונקצייה הזו משמעות אם מוצג מד טמפרטורה ולחות
    if is_bme280_connected:
        return
    #######################################################
    
    # הכרזה על משתנים גלובליים שיטופלו בלחיצה על הכפתור
    global location_index
    global location
    # המשתנה הגלובלי ששולט על הזמן שממנו סופרים מספר שניות או דקות עד שהמסך ייכבה מעצמו
    global start_time_for_automatic_deepsleep
    
    # מגדיר מחדש את הזמן שממנו סופרים שניות או דקות עד שהמסך ייכבה מעצמו
    # זה מאוד חשוב כדי שהמכשיר לא ייכבה במהלך דפדוף ברשימת המיקומים בגלל שעברו מספר השניות הקבוע לכיבוי אוטומטי
    # כלומר כל לחיצה תעכב את הכיבוי האוטומטי ותספור אותה משעת הלחיצה והלאה
    start_time_for_automatic_deepsleep = time.time()
    
    # חישוב משך הלחיצה
    duration = handle_button_press(boot_button)
  
    if duration == "short":
        # לחיצה קצרה: מעבר למיקום הבא
        location_index = (location_index +1) % len(locations)
        location = locations[location_index]  # שליפת המילון של המיקום הנוכחי
             
    elif duration == "long":
        boot_button.irq(handler=None) # מבטל את הקריאה של הכפתור לפונקצייה זו
        main_menu() # נכנסים לתפריט הראשי
        boot_button.irq(trigger=Pin.IRQ_FALLING, handler=toggle_boot_button) # אחרי חזרה מהתפריט - נחזיר את ה־IRQ

# חיבור הכפתור לפונקציה
boot_button.irq(trigger=Pin.IRQ_FALLING, handler=toggle_boot_button)



##############################################################################################################################3
def entering_sleep_mode():

    # פונקצייה נורא נורא נורא חשובה לכיבוי כל הפינים לפני שנכנסים למצב שינה עמוקה
    # קריטי במיוחד השורה הראשונה שזה הפינים של המסך שאם לא מכבים אותם יש מריחות על המסך אחרי מצב שינה
    # הפין היחיד שבכוונה לא מכבים אותו הוא פין 14 ששולט על ההדלקה מחדש כלומר יציאה מהשינה העמוקה
    def set_pins_off():    
        #  רשימת הפינים לכיבוי
        pins = [
            38, 39, 40, 41, 42, 45, 46, 47, 48,  # פיני ה-LCD
            15,  # פין הפעלת מתח
            5, 6, 7, 8, 9  # פינים נוספים של ה-LCD
        ]
        
        pin_objects = [Pin(p, Pin.OUT) for p in pins]  # יצירת אובייקטים לכל פין
        for pin in pin_objects:
            pin.value(0)  # כיבוי כל הפינים
        print("all_pins_off")


    # הדפסה למסך
    tft.fill(0) # מחיקת המסך
    tft.write(FontHeb25,f'{reverse("כניסה למצב שינה...")}',30,20) # דווקא בגובה של שורת התאריך כדי שאם יהיו מריחות הם יסתירו רק את שורה זו
    tft.show() # כדי להציג את הנתונים על המסך
    time.sleep(0.5) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
    tft.fill(0) # מחיקת המסך
    tft.show() # כדי להציג את הנתונים על המסך
    time.sleep(0.1) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
    
    # התנתקות מהגדרת המסך שבוצעה בתחילת הקוד
    # זה גם מכבה את שלושת הפינים של המסך שהם התאורה האחורית הכוח וה RD כאשר מוגדר טרו
    tft_config.deinit(tft, display_off=True)
    
    # ב S3 ליליגו עובד רק על כפתור 14 ולא על כפתור בוט שהוא אפס
    wake1 = Pin(14, Pin.IN, Pin.PULL_UP)
    
    # הגדרת כפתור ההשכמה מהשינה העמוקה
    esp32.wake_on_ext0(pin = wake1, level = esp32.WAKEUP_ALL_LOW)

    # קריאה לפונקצייה החשובה מאוד שהגדרתי לעיל
    set_pins_off() # חשוב ביותר כיבוי כל הפינים למעט פין 14 של כפתור ההתעוררות לפני הכניסה למצב שינה כדי למנוע בעיות מסך ובזבוז בטרייה
    
    # מצב שינה. היציאה ממצב שינה מתבצעת באמצעות לחיצה על הכפתור שמעיר את המכשיר וקורא שוב לקובץ מיין שקורא שוב לקובץ מיין שמש
    machine.deepsleep() # לא מתעורר כל עוד שלא לוחצים על כפתור 14
#############################################################################    


##################################################################################################################
#################################################################################################33

# הפונקצייה הראשית שמפעילה את כל החלקים יחד
def main_main():
    
    # הצהרה על משתנים גלובליים שצריך להגדיר אותם מחדש בתוך פונקצייה זו
    global power_state, start_time_for_automatic_deepsleep, start_time_for_check_and_set_time, is_bme280_connected, bme
    global last_voltage, last_battery_percentage, last_is_charging

    # קריאת המתח של החשמל ולפי זה קביעת רמת התאורה האחורית של המסך כדי לחסוך בצריכת חשמל וכן הדלקת רכיבים נוספים שקשורים למסך ולכוח
    current_voltage = read_battery_voltage()   
    current_battery_percentage = get_battery_percentage(current_voltage)
    current_is_charging = is_charging_function(current_voltage)
    
    # קורא את הזמן העדכני בכל שנייה מחדש
    current_time = time.time()
    
    # תיקון כדי שניתוק BME280 לאחר דקות ממהדלקה לא יכניס מייד למצב שינה
    if is_bme280_connected:
        # עדכון זמן הקריאה האחרונה
        start_time_for_automatic_deepsleep = current_time
            
    # תיקון כדי שניתוק מהחשמל ייתן ארכה של כמה שניות לפני כיבוי    
    ####if last_voltage > max_battery_v and current_voltage < max_battery_v and abs(last_voltage - current_voltage) > 0.5:
    if not current_is_charging and last_is_charging:
        start_time_for_automatic_deepsleep = current_time
    
    # אם מוגדר שינה אוטומטית והמתח מראה שמחובר לסוללה ולא לחשמל ועברו ... דקות מאז הפעלת התוכנה אז מגדירים את המשתנה power_state לכבות את המכשיר
    # המשתנה automatic_deepsleep מוגדר בפונקציית main_halach_clock שבשבת וחג לא מכבים את המסך או נכנסים למצב שינה
    # בתחילה מגדירים משתנה מאוד חשוב שקובע אחרי כמה זמן ניכנס למצב שינה או למסך כבוי באופן אוטומטי
    # כרגע מוגדר ל 200 שניות כי אחרת לא יוכלו לראות את כל ההסברים אם ייכבה קודם
    seconsd_to_start_auto_deepsleep = 200 
    if automatic_deepsleep and not current_is_charging and (current_time - start_time_for_automatic_deepsleep) >= seconsd_to_start_auto_deepsleep:
        power_state = False
    
    ##############################################
    # חייבים לאפס את זה כל שנייה מחדש כדי שנוכל להשוות את השנייה הקודמת לשנייה הנוכחית
    # אחרי שקראנו ושמרנו את המתח הקודם, כעת מעדכנים את המשתנה הגלובלי במתח הנוכחי וזה משמש גם עבור דברים אחרים בתוכנה
    last_voltage = current_voltage
    # מעדכנים אחוזים רק אם זו הפעם הראשונה או במצב שהאחוזים השתנו מהקריאה הקודמת ביותר מ X אחוז
    if not last_battery_percentage or abs(current_battery_percentage - last_battery_percentage) >= 2:
        last_battery_percentage = current_battery_percentage
    last_is_charging = current_is_charging
    ##############################################
                 
    # אם כפתור הפעלת החישובים פועל אז מפעילים את המסך ואת הכוח ואת החישובים וחוזרים עליהם שוב ושוב
    if power_state:
         
        # כל יממה צריך לקרוא מחדש את השעה כי השעון הפנימי של הבקר עצמו לא מדוייק מספיק
        # אבל הוא כן מדוייק מספיק אם הוא פועל ברצף (בלי מצב שינה עמוקה) אפילו יותר מכמה יממות
        # לכן פשרה טובה היא לעדכן פעם ביממה
        # בדיקה אם עברה יממה (3600 שניות בכל שעה)
        if current_time - start_time_for_check_and_set_time >= 86400:
            check_and_set_time()
            # עדכון זמן הקריאה האחרונה
            start_time_for_check_and_set_time = current_time
            
        # בהירות המסך היא חצי מהבהירות המקסימלית אם מחובר לחשמל ורבע אם מחובר לסוללה
        duty_for_backligth = 500 if current_is_charging else 255
        # הפעלת בהירות המסך המתאימה
        BACKLIGHT.duty(duty_for_backligth)
        
        ####################################################################################################
        # זה גורם שאם מחברים את BME280 באמצע פעולת שעון ההלכה התוכנה תהפוך למד טמפרטורה
        # בכל מקרה ניתן לשקול לבטל את הקטע הזה אם מעמיס בבדיקות מיותרות או פוגע במשהו
        if not is_bme280_connected:
            try:
                # אני מניח ש BME280 מחובר ל original_i2c כדי לחסוך בבדיקות, אבל אפשר לבדוק עם check_i2c_device(bme280_bitname) כמו בתחילת הקוד
                bme = bme280.BME280(i2c=original_i2c) 
                is_bme280_connected = True
                ################################################################################
                # החזרת מיקום ברירת המחדל להיות המיקום הנוכחי
                # אם לא עושים את זה הזמן יהיה במיקום שמוגדר בשעון ההלכה ברגע חיבור חיישן הטמפרטורה
                go_to_default_location()
                #################################################################################
            except:
                bme = False
                is_bme280_connected = False    
        #####################################################################################################  
        
        # אם נמצא בהפעלת המכשיר ש BME280 מחובר אז התוכנה מתפקדת כמד טמפרטורה
        # אבל זה חייב להיות בניסיון כי ייתכן שהיה מחובר וכעת מנותק ואז נקבל שגיאה
        # בכל מקרה אם מתקבלת שגיאה סימן שמנותק ולכן מגדירים את המשתנה לומר שמנותק ואז בשנייה הבאה יוצג שעון ההלכה
        if is_bme280_connected:
            try:
                main_bme280()
                time.sleep(1) # עדכון כל שניה
                gc.collect() # ניקוי הזיכרון חשוב נורא כדי למנוע קריסות
            except Exception as e:
                print("שגיאת BME280", e) # Errno 19] ENODEV זו שגיאה שאומרת שהחיישן לא מחובר
                is_bme280_connected = False
        
        # אם BME280 לא מחובר אז התוכנה מתפקדת כשעון ההלכה
        else:
            # הפעלת הפונקצייה הראשית והשהייה קטנה לפני שחוזרים עליה שוב
            main_halach_clock()
            time.sleep(0.825)  # רענון כל שנייה אבל צריך לכוון את זה לפי כמה כבד הקוד עד שהתצוגה בפועל תתעדכן כל שנייה ולא יותר ולא בפחות
            gc.collect() # ניקוי הזיכרון חשוב נורא כדי למנוע קריסות
            
    # אם הכוח לא פועל אז יש לכבות הכל
    else:
        # כניסה למצב שינה
        entering_sleep_mode()



# לולאת רענון חשובה ביותר שחוזרת על עצמה כל הזמן והיא זו שמפעילה את הפונקצייה הראשית כל שנייה מחדש
while True:
    main_main()







####################################################
    # גיבוי קודים לא נדרשים - שאולי יהיו שימושיים בעתיד
####################################################
'''
# חישוב זמן חצות היום באמצעות נוסחה אסטרונומית
# הערה: אפשר לחשב זאת בערך גם באמצעות שעה זמנית 6 בשעות זמניות מהנץ לשקיעה במקום וביום שיש הנץ ושקיעה
def calculate_local_noon():
    EoT_sec = get_equation_of_time_from_timestamp(current_utc_timestamp) # משוואת הזמן בשניות
    noon_utc_sec = (12*3600 - (location["long"]/360.0)*86400 - EoT_sec) # חצות ב-UTC (שניות מ-00:00 UTC)
    now_days = (current_utc_timestamp - current_utc_timestamp % 86400) # מספר היום בשניות מהאפוך עד חצות הלילה האחרון
    noon_utc_timestamp = noon_utc_sec + now_days
    # חצות מקומי
    noon_local_timestamp = noon_utc_timestamp + location_offset_seconds
    return noon_local_timestamp

noon_local_timestamp = calculate_local_noon()    
#print("noon_local",format_time(time.gmtime(noon_local_timestamp)))
'''
'''
# פונקצייה שמחשבת את ההפרש בין שעון מקומי אמיתי לשעון מקומי ממוצע.
# ההפרש הזה מורכב ממשוואת הזמן יחד עם דלטא טי
def calculate_lmt_lst_different():
    if sunrise and sunset:
        # שלב ראשון חישוב חצות בשעון רגיל.
        # בינתיים חישבתי חצות בדרך לא הכי מדוייקת באמצעות שעה זמנית 6 כלומר חצי הזמן בין הזריחה המישורית לשקיעה המישורית
        # הכי מדוייק זה שמש באזימוט 180 או אם אי אפשר אז לפחות אמצע בין זריחה ושקיעה גיאומטריים של 0 מעלות
        seconds_day_gra = (sunset - sunrise) / 12 if sunrise and sunset else None
        chatsot_seconsds = sunrise + (seconds_day_gra * 6)
        
        # המרת החצות לשעה בגריניץ באותו זמן
        chatsot_seconsds_gm = chatsot_seconsds-location_offset_seconds
           
        # שלב שני חישוב שעת חצות בשעון מקומי ממוצע ובדיקה כמה סוטה מהשעה 12:00 וכך מוצאים את הפרש הזמן
        # בדיקת שעת חצות בשעון מקומי ממוצע
        chatsot_lmt = localmeantime(chatsot_seconsds_gm, location["long"])
        chatsot_lmt_string = format_time(chatsot_lmt)
        
        # בונים את הזמן של 12:00 באותו היום 
        noon_timestamp = time.mktime(chatsot_lmt[:3] + (12, 0, 0) + chatsot_lmt[6:])
        chatsot_lmt_timestamp = time.mktime(chatsot_lmt)
                
        # מחשבים את ההפרש בין השעה 12:00 לבין שעת חצות בשעון מקומי ממוצע. זה ההפרש lmt_lst
        lmt_lst_different = noon_timestamp - chatsot_lmt_timestamp # כך צריך להיות כיוון המשוואה - כפי הסדר המקובל EoT=LST−LMT
    
    else:
        lmt_lst_different = None
        
    return lmt_lst_different
    '''

'''
# קריאת נתונים מתוך קובץ CSV והמרתם לרשימה של מילונים
locations = []

try:

    with open("locations_esp.csv", "r") as file:
        lines = file.readlines()  # קריאת כל השורות בקובץ
        header = lines[0]  # כותרת העמודות (השורה הראשונה)
        data_lines = lines[1:]  # שורות הנתונים (כל השורות חוץ מהראשונה)
        
        for line in data_lines:
            row = line.strip().split(",")  # הסרת רווחים בתחילת וסוף השורה ופיצול לפי פסיק
            # יצירת מילון לכל מיקום
            location = {
                "heb_name": row[0],        # שם בעברית
                "lat": float(row[1]) if float(row[1]) != 90.0 else 89.99,  # קו רוחב # באג בספריית החישובים לא מאפשר לחשב ל 90 מעלות
                "long": float(row[2]), # קו אורך
                "altitude": float(row[3]),# גובה במטרים
                "utc_offset": 3 if is_now_israel_DST() else 2, # row[4],# הפרש מיוטיסי # או int אם זה מספר
                "name": row[5]            # שם באנגלית
            }
            locations.append(location)
            
except Exception as e:
    print(e)
    locations.append({"name": "modiin-illit", "heb_name": "מודיעין עילית", "lat": 31.940826, "long": 35.037057, "utc_offset": 3 if is_now_israel_DST() else 2})

'''

'''
# פונקצייה שאינה בשימוש כלל כרגע וגם לא עדכנית אבל נשארת כאן לתזכורת איך עושים זאת
# היא מיועדת למקרים שבהם רוצים לעדכן את השעה ב DS3231 מהמחשב או באופן ידני במקום מהרשת והיא לא מומלצת כלל כי עדיף לעדכן מהרשת
# בכל מקרה אסור לקרוא לה אם לא מחוברים למחשב או אם השעה במחשב לא מכוונת
# שימו לב!!! בעדכון באמצעות פונקצייה זו צריך להקפיד שאיזור הזמן יהיה איזור הזמן של גריניץ אחרת יהיו שגיאות בחישובי הזמן בתוכנה
# זה מסתמך על הגדרות משתנים גלובליים: rtc_system וגם rtc_ds3231
def update_ds3231_from_computer_or_manually(from_computer=False, manually=False):
    
    rtc_ds3231 = DS3231(ds3231_exit)

    
    if from_computer:
            
        # קריאת זמן המערכת של הבקר שזה הזמן המדוייק של המחשב רק כאשר הבקר מחובר למחשב
        year, month, day, week_day, hour, minute, second, micro_second = rtc_system.datetime()
        # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
        new_time = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
        
        print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())

        # עדכון הזמן ב-RTC
        rtc_ds3231.datetime(new_time)

        print("זמן המחשב עודכן בשעון החיצוני בהצלחה. השעה לאחר העדכון היא", rtc_ds3231.datetime())
        
    elif manually:
                
        # כאן אפשר לבחור לבד איזה נתונים לכוון לשעון החיצוני
        year, month, day, hour, minute, second, weekday = 1988, 2, 24, 18, 45, 56, 1 # 1 = sunday                
        new_time = (year, month, day, hour, minute, second, weekday)


        print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
        
        # עדכון הזמן ב-RTC
        rtc_ds3231.datetime(new_time)

        print("זמן ידני עודכן בשעון החיצוני בהצלחה. השעה לאחר העדכון היא", rtc_ds3231.datetime())
'''

'''
# פונקצייה מאוד חשובה לקביעה כמה זמן לחצו על כפתור האם לחיצה ארוכה או קצרה
# כולל אופצייה ללחיצה ארוכה מאוד, ארוכה או קצרה
# כרגע יצאה משימוש אבל נשארת כאן לשמירת
def handle_button_press(specific_button):
    
    start_time = time.ticks_ms()

    # הלולאה הזו מתבצעת אם לוחים ברציפות בלי לעזוב
    while specific_button.value() == 0:  # כל עוד הכפתור לחוץ
        elapsed_time = time.ticks_diff(time.ticks_ms(), start_time)

        if elapsed_time > 6000:  # לחיצה מאוד ארוכה מעל 6 שניות
            return "very_long"
    # מכאן והלאה מתבצע רק אחרי שעוזבים את הכפתור ואז מודדים כמה זמן היה לחוץ    
    elapsed_time = time.ticks_diff(time.ticks_ms(), start_time)
    
    if elapsed_time > 3000:  # לחיצה ארוכה בין 3 ל-6 שניות
            return "long"

    elif 100 < elapsed_time < 1000:  # לחיצה קצרה בין 100ms ל-1s
        return "short"
    
    return None  # במידה ולא זוהתה לחיצה
    '''



