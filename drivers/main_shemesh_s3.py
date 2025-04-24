# ========================================================
# License: Personal Use Only  
# This file (`main_shemesh_s3.py`) is licensed for **personal use only**.  
# You may **not** modify, edit, or alter this file in any way.  
# Commercial use is strictly prohibited.  
# If you wish to use this file for business or organizational purposes,  
# please contact the author.  
# ========================================================

# משתנה גלובלי שמציין את גרסת התוכנה למעקב אחרי עדכונים
VERSION = "24/4/2025"

######################################################################################################################

# סיכום קצר על התוצאות המעשיות של הכפתורים בקוד הזה
# לחיצה על שתי הכפתורים בו זמנית כאשר מדליקים את המכשיר: עדכון תוכנת המכשיר
# אם כפתור המיקומים לחוץ בשעת הכניסה לתוכנה: עדכון השעון מהרשת 

# הבסיס של החישובים הגיע מכאן
# https://github.com/peterhinch/micropython-samples/tree/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy
# לגבי בעיות עם המסך שבס"ד נפתרו ראו כאן
# https://github.com/Xinyuan-LilyGO/T-Display-S3/issues/300
# ובורא עולם תכנן שהפין שבחרתי להלחים עבור השעון החיצוני שזה פין 17 נשאר פעיל גם במהלך שינה עמוקה. זה טוב מאוד כי השעון החיצוני צריך למדוד טמפרטורה בשביל להיות מדוייק

import time, math, machine, utime, esp32, network, ntptime, os
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


# משתנה גלובלי חשוב מאוד ששומר את השאלה האם לעדכן את השעון החיצוני מהרשת
# ברירת המחדל היא שלא
ntp_update = False
# אבל אם בשעת הדלקת המכשיר שזו שעת תחילת ריצת הקוד כפתור בוט לחוץ אז כן לעדכן
if boot_button.value() == 0:  # בודק אם הכפתור לחוץ בשעת הדלקת המכשיר
    ntp_update = True 
    
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

# פונקציה למדידת מתח סוללה
def read_battery_voltage():
    raw_value = adc.read()  # קריאת הערך האנלוגי
    voltage = (raw_value / 4095) * 3.6  # ממירים את הערך האנלוגי למתח (בטווח של 0-3.6V)
    battery_voltage = voltage * 2  # מכפילים ב-2 בגלל מחלק המתח
    return battery_voltage

##############################################3

# לאחר מכן להפעיל PWM כדי לשלוט במידת התאורה האחורית של המסך
BACKLIGHT = PWM(Pin(38, Pin.OUT), freq=2000) # ה: פרק, חשוב מאוד לגבי התדר וקובע גם את סוג הצפצופים שנשמעים בעיקר כשמחובר לחשמל
PWM_MAX = 1023 # תאורה הכי גבוהה
PWM_MIN = 0 # התאורה כבוייה

# משתנה חשוב שמגדיר מה המתח המירבי שיכול להיות לסוללה ומעל זה זה מראה שמחובר לחשמל ולא לסוללה
max_battery_v = 4.65

# משתנה מאוד חשוב ששומר את המתח בשנייה הקודמת כדי להשוות אליו ולבדוק האם חובר חשמל או נותק
# זה מתעדכן כל שנייה מחדש בפונקציית מיין-מיין
voltage = read_battery_voltage()

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


# פונקצייה להמרת זמן מ-שניות ל- סטרינג שעות דקות ושניות, או רק ל- סטרינג דקות ושניות שבניתי בסיוע רובי הבוט
def convert_seconds(seconds, to_hours=False):        
    # חישוב מספר הדקות והשניות שיש בשעה אחת, והדפסתם בפורמט של דקות ושניות
    if to_hours:
        return f'{seconds // 3600 :02.0f}:{(seconds % 3600) // 60 :02.0f}:{seconds % 60 :02.0f}'
    else:
        return f'{seconds // 60 :02.0f}:{seconds % 60 :02.0f}'


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


##########################################################################################
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
######################################################################################################3

# מונקצייה שמנסה להתחבר לווייפי ולקבל את הזמן הנוכחי בגריניץ כלומר ב UTC-0
def get_ntp_time():
    """עדכון השעה משרת NTP עם ניסיון לרשתות נוספות במקרה של כישלון, כולל כיבוי Wi-Fi בסוף."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False) # חייבים קודם לכבות ואחר כך להדליק
    wlan.active(True)  # הפעלת ה-WiFi

    try:
        networks = wlan.scan()  # סריקת רשתות זמינות
        
        open_networks = [net for net in networks if net[4] == 0]  # מסנן רק רשתות פתוחות כלומר שהן ללא סיסמה
        
        # אם אין רשתות פתוחות מפסיקים את הניסיון
        if not open_networks:
            return "לא נמצאו רשתות פתוחות!"
        
        for net in open_networks:
            
            ###########################
            # זה נועד למנוע שגיאת: [Errno 116] ETIMEDOUT
            # כיבוי והדלקה מחדש של הוויפי אחרת זה לא תמיד מתחבר והמתנה שתי שניות כדי שהחיבור יתייצב
            wlan.active(False)
            wlan.active(True)
            time.sleep(2)
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

            if wlan.isconnected():
                try:
                    # ניסיון לקבלת זמן משרת NTP
                    ntptime.host = "pool.ntp.org"
                    ntptime.timeout = 1
                    # קבלת הזמן מהשרת בפורמט של חותמת זמן. הזמן המתקבל הוא בשעון גריניץ כלומר UTC-0
                    ntp_timestamp_utc = ntptime.time()
                    # המרת הזמן הנוכחי בגריניץ מחותמת זמן לפורמט של תאריך ושעה
                    ntp_localtime = utime.localtime(ntp_timestamp_utc)
                    
                    print("השעה (בגריניץ) התקבלה בהצלחה!", ntp_localtime)
                    return ntp_localtime  # מחזיר את הזמן ומכבה את ה-WiFi (נכבה תמיד ב-finally)
                
                except Exception as ntp_error:
                    print(f"שגיאה בקבלת הזמן מהרשת {ssid}: {ntp_error}")
                    wlan.disconnect()  # ניתוק בלבד, ננסה רשת אחרת

        raise Exception("כשלון בקבלת הזמן משרת בכל רשת")

    except Exception as error:
        return f"{str(error)}"

    finally:
        wlan.active(False)  # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו


#######################################################################################3

time_source_dic = {1: "שעה משעון חיצוני DS3231", 2: "שעה משרת NTP", 3: "שעה משעון פנימי שכנראה לא מדוייק", 4: "זמן שרירותי"}

# משתנה גלובלי חשוב מאוד ששומר מידע איזה סוג זמן משמש בפועל בתוכנה
# ראו פירוט במשתנה: time_type_dic
time_source = None

# פונקצייה שמטפלת בכל הגדרת הזמן, ועדכונו אם צריך, גם בשעון הפנימי וגם בשעון החיצוני
# היא באה במקום הפונקצייה שהייתה קיימת פעם ונקראה בשם: sync_rtc_with_ds3231()
# חשוב מאוד! הפונקצייה מגדירה בשעון החיצוני והפנימי את הזמן בשעון גריניץ כלומר איזור זמן UTC-0
def check_and_set_time():
    
    # הצהרה על משתנה גלובלי שקובע האם יש לעדכן את הזמן מהרשת
    global ntp_update
    
    # הצהרה על משתנה גלובלי ששומר מידע איזה סוג סמן משמש בפועל
    # ראו פירוט במשתנה: time_type_dic
    global time_source

    # קריאת הזמן מהשעון הפנימי של הבקר
    rtc_system = machine.RTC()
    
    # בדיקה האם DS3231 מחובר ולאיפה מחובר באמצעות פונקצייה שהוגדרה לעיל
    is_ds3231_connected, ds3231_exit, ds3231_exit_name = check_i2c_device(ds3231_bitname)
    
    # אם DS3231 מחובר, ולא הוגדר בתחילה שרוצים לעדכן שעון מהרשת
    if is_ds3231_connected and not ntp_update:
        
        # הגדרת DS3231
        rtc_ds3231 = DS3231(ds3231_exit)
        
        #  קריאת הזמן מ-DS3231
        ds3231_time = rtc_ds3231.datetime()
        
        # אם DS3231 מוגדר נכון ולא מאופס לשנת 2000 אז מעדכנים את הזמן שבו לתוך השעון הפנימי ויוצאים מהפונקצייה
        if ds3231_time[0] > 2022: 
            rtc_system.datetime(ds3231_time)
            print("הזמן עודכן מתוך DS3231: ", ds3231_time)
            time_source = 1
            return
        
    # מכאן והלאה מעדכנים שעונים משרת NTP וזה דרוש בכל המקרים מלבד המקרה שכבר טופל לעיל שהשעון החיצוני מחובר ולא רוצים לעדכן 
    # הדפסה למסך
    tft.fill(0) # מחיקת המסך
    #tft.write(FontHeb20,f'{reverse("השעון אינו מכוון")}',0,35)
    tft.write(FontHeb25,f'{reverse("בתהליך עדכון הזמן מהרשת...")}',5,45)
    tft.write(FontHeb25,f'{reverse("מחפש בקרבתך רשת ללא סיסמה")}',2,75)
    tft.show() # כדי להציג את הנתונים על המסך
    time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
                
    # קבלת זמן ntp מהשרת ואם יש שגיאה המשתנה הזה יכיל את השגיאה
    ntp_time = get_ntp_time() # אם אין שגיאה זה מחזיר את הזמן הנוכחי בשעון ישראל
    
    
    # אם DS3231 מחובר אז על הדרך מעדכנים גם בו את השעה שהתקבלה מהרשת
    if is_ds3231_connected:
        try:
            # הגדרת DS3231
            rtc_ds3231 = DS3231(ds3231_exit)
            year, month, day, hour, minute, second, week_day, year_day = ntp_time # זה מחזיר את הזמן הנוכחי בשעון ישראל
            # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
            time_for_ds3231 = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
            print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
            # עדכון הזמן ב-DS3231
            rtc_ds3231.datetime(time_for_ds3231)
            print("DS3231 עודכן בהצלחה מהרשת. השעה לאחר העדכון היא:", rtc_ds3231.datetime())
            tft.fill(0) # מחיקת המסך
            tft.write(FontHeb25,f'{reverse("עודכן בהצלחה מהרשת")} DS3231',10,50)
            tft.show()
            time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
        except Exception as error:
            tft.fill(0) # מחיקת המסך
            tft.write(FontHeb25,f'{reverse("כשלון בעדכון מהרשת")} DS3231',10,50)
            print(error)
            tft.write(FontHeb20,f'{error}',0,70)
            tft.show()
            time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
        
           
    #ניסיון לעדכן את השעון הפנימי מתוך שרת NTP
    try:   
        # קריאת זמן המערכת של הבקר שזה הזמן המדוייק של המחשב רק כאשר הבקר מחובר למחשב
        year, month, day, hour, minute, second, week_day, year_day = ntp_time # זה מחזיר את הזמן הנוכחי בשעון ישראל
        time_for_rtc_system = (year, month, day, get_rtc_weekday(week_day), hour, minute, second, 0)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
        rtc_system.datetime(time_for_rtc_system) # זה מעדכן את השעון הפנימי בזמן הנוכחי בשעון ישראל
        time_source = 2       
        print("זמן שרת עודכן בהצלחה. השעה לאחר העדכון היא", rtc_system.datetime())
        tft.fill(0) # מחיקת המסך
        tft.write(FontHeb25,f'{reverse("הזמן עודכן בהצלחה מהרשת")}',10,70)
        tft.show()
        time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
    
    # במקרה של שגיאה בעדכון הזמן מהשרת
    except Exception as error:
        
        tft.fill(0) # מחיקת המסך
        tft.write(FontHeb25,f'{reverse("שגיאה בעדכון הזמן מהרשת")}',10,20)
        tft.write(FontHeb20,f'{str(error)}',0,50)
        tft.write(FontHeb20,f'{reverse(ntp_time)}',20,70)
        tft.show()
        time.sleep(5) # כדי שהמשתמש יוכל לראות מה יש במסך לפני שהכיתוב נעלם
        print(f"שגיאה בעדכון שעון חיצוני מהשרת: {str(error)} פונקציית אנטיפי מחזירה {ntp_time}")
        
        # אם יש שגיאה בעדכון מהשרת וגם ds3231 לא מחובר או לא עדכני בעליל אז מוכרחים להגדיר זמן שרירותי ידני כדי שהתוכנה תעבוד
        # במקרה כזה הוספתי להדפסת השעה סימני קריאה כדי שידעו שהשעה הזו לא נכונה
        
        # אם כרגע בשעון הפנימי מעודכן זמן שבטוח לא טוב כי הוא מלפני שנת 2025 אז מעדכנים זמן שרירותי
        if rtc_system.datetime()[0] < 2025:
            print("אין שעון מחובר, או שהשעון לא עדכני כלל, וגם אין רשת ולכן מעדכנים זמן ידני שרירותי")
            tft.fill(0) # מחיקת המסך
            if is_ds3231_connected:
                tft.write(FontHeb25,f'{reverse("השעון לא עדכני, ואין רשת")}',5,20)
            else:
                tft.write(FontHeb25,f'{reverse("אין שעון מחובר, וגם אין רשת")}',5,20)
            tft.write(FontHeb25,f'{reverse("לכן מגדירים זמן שרירותי שגוי!")}',5,50)
            tft.show()
            time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
            manual_time = (2020, 5, 20, get_rtc_weekday(6), 16, 39, 35, 20)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
            rtc_system.datetime(manual_time)
            time_source = 3
        else:
            print("אין שעון מחובר או שהוא לא עדכני בעליל וגם אין רשת אבל זמן המערכת אולי מדוייק ולכן לא משנים אותו אבל זה כנראה לא מדוייק")
            tft.fill(0) # מחיקת המסך
            if is_ds3231_connected:
                tft.write(FontHeb25,f'{reverse("השעון לא עדכני, ואין רשת")}',5,20)
            else:
                tft.write(FontHeb25,f'{reverse("אין שעון מחובר, וגם אין רשת")}',5,20)
            tft.write(FontHeb25,f'{reverse("הזמן נלקח מהשעון הפנימי")}',5,50)
            tft.write(FontHeb25,f'{reverse("ייתכן שהזמן אינו נכון!")}',5,80)
            tft.show()
            time.sleep(2) # השהייה כדי לראות את ההודעה לפני שהמסך ייכבה
            time_source = 4 



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


# פונקצייה לחישוב שעון המגרב או שעון ארץ ישראל כלומר כמה זמן עבר מהשקיעה האחרונה עד הרגע הנוכחי
# כל הזמנים צריכים להינתן בפורמט חותמת זמן
# פונקצייה זו יכולה לפעול גם בכל פייתון רגיל היא לגמרי חישובית ולא תלוייה בכלום חוץ מהמשתנים שלה
# חייבים לתת לה את זמן השקיעה המתאים כלומר השקיעה של היום או לאחר חצות הלילה השקיעה של אתמול הלועזי
# כרגע פונקצייה זו לא פעילה ויש בה בעיות שונות
def calculate_magrab_time(current_timestamp, last_sunset_timestamp):
        
        # חישוב כמה שניות עברו מאז הזריחה או השקיעה עד הזמן הנוכחי 
        time_since_last_sunset = current_timestamp - last_sunset_timestamp
        
        # הדפסת השעה הזמנית המתאימה בפורמט שעות:דקות:שניות
        magrab_time = str(convert_seconds(time_since_last_sunset, to_hours=True))
        
        return magrab_time


##############################################################################################################        
# הגדרת שמות עבור משתנים גלובליים ששומרים את כל הזמנים הדרושים לחישובים
sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
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
    
    {'heb_name': 'אמסטרדם-הולנד', 'lat': 52.38108, 'long': 4.88845, 'altitude': 15.0, 'utc_offset': '', 'name': 'Amsterdam NL'} ,
    {'heb_name': 'רמרוג-צרפת רת', 'lat': 48.518606, 'long': 4.3034152, 'altitude': 101.0, 'utc_offset': '', 'name': 'Ramerupt FR'} ,
    {'heb_name': 'רומא-איטליה', 'lat': 41.8954656, 'long': 12.4823243, 'altitude': 19.704413, 'utc_offset': '', 'name': 'Rome IT'} ,
    {'heb_name': 'פרנקפורט-גרמניה', 'lat': 50.1115118, 'long': 8.6805059, 'altitude': 106.258285, 'utc_offset': '', 'name': 'Frankfurt DE'} ,
    {'heb_name': 'לונדון-אנגליה', 'lat': 51.5001524, 'long': -0.1262362, 'altitude': 14.605533, 'utc_offset': '', 'name': 'London GB'} ,
    {'heb_name': 'לייקווד-ארהב', 'lat': 40.07611, 'long': -74.21993, 'altitude': 16.0, 'utc_offset': '', 'name': 'Lakewood US'} ,
    {'heb_name': 'קהיר-מצרים', 'lat': 30.00022, 'long': 31.231873, 'altitude': 23.0, 'utc_offset': '', 'name': 'Cairo EG'} ,
    {'heb_name': 'וילנא-ליטא', 'lat': 54.672298, 'long': 25.2697, 'altitude': 112.0, 'utc_offset': '', 'name': 'Vilnius LT'} ,
    {'heb_name': "ז'שוב-פולין", 'lat': 50.0332, 'long': 21.985848, 'altitude': 209.0, 'utc_offset': '', 'name': 'Rzeszow PL'} ,
    {'heb_name': 'סטוקהולם-שבדיה', 'lat': 59.33, 'long': 18.06, 'altitude': 28.0, 'utc_offset': '', 'name': 'Stockholm SE'} ,
    {'heb_name': "פראג-צ'כיה", 'lat': 50.0878114, 'long': 14.4204598, 'altitude': 191.103485, 'utc_offset': '', 'name': 'Prague CZ'} ,
    {'heb_name': 'פריז-צרפת', 'lat': 48.8566667, 'long': 2.3509871, 'altitude': 0.0, 'utc_offset': '', 'name': 'Paris FR'} ,
    {'heb_name': 'מוסקווה-רוסיה', 'lat': 55.755786, 'long': 37.617633, 'altitude': 151.189835, 'utc_offset': '', 'name': 'Moscow RU'} ,
        
    ]


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

def get_battery_percentage(voltage, min_voltage=3.6, max_voltage=4.4):
    """ מחשב אחוז סוללה על פי המתח הנמדד ומונע ערכים מחוץ לטווח 0%-100% """
    percentage = ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100
    return round(max(0, min(100, percentage)))


# חישוב מה מרכז המסך כדי למרכז את הטקסט במרכז המסך
# עדיין יש בעיות קטנות שאולי נגרמות מכך שיש אותיות צרות יותר מ MAX_WIDTH אבל אין מה לעשות כרגע
# בינתיים זה הכי טוב שהגעתי אליו
def center(text, font):
    # הגדרת הפיקסל שבמרכז המסך
    tft_pixel_center = 160 # tft.width() // 2
    # הגדרת הפיקסל שבמרכז הטקסט
    text_pixel_center = len(text) // 2 * font.MAX_WIDTH // 2 # כלומר הרוחב בפיקסלים של חצי מהטקסט
    return tft_pixel_center - text_pixel_center # זה אומר כמה ימינה ממרכז המסך צריך להתחיל את ההדפסה כדי שמרכז ההדפסה יהיה במרכז המסך


#  ההסברים מורכבים משני חלקים כל אחד: הסבר וערך. ההסבר עובר בסוף רוורס ולכן אם יש בו מספרים חייבים לעשות להם רוורס כאן כדי שהרוורס הסופי יישר אותם 
esberim = [
    
        ["שעון ההלכה גרסה",f"{VERSION}"],
        [" מאת: שמחה גרשון בורר - כוכבים וזמנים",""],
        [reverse("052-7661249 - sgbmzm@gmail.com  "), ""],
        ["כל הזכויות שמורות - להלן הסברים", ""],
        ["בתקלה: יש ללחוץ על לחצן האיפוס", ""],
        ["אחוז הסוללה )בערך(: בשורת הכותרת", ""],
        ["כשמחובר לחשמל מופיע: %**", ""],
        ["אור אדום דולק בחור: הסוללה נטענת", ""],
        ["לחצן תחתון: הדלקה וכיבוי", ""],
        ["לחצן עליון: ביצוע פעולות כדלהלן", ""],
        ["לחיצה קצרה: שינוי מיקום", ""],
        ["לחיצה מתמשכת: הגדרת מיקום קבוע", ""],
        ["התחלה כשהלחצן לחוץ: עדכון שעון", ""],
        ["הדלקה בשני הלחצנים: עדכון תוכנה", ""],
        [" עדכונים דורשים רשת ללא סיסמה", ""],
        [f"כשהשעון מכוון: דיוק הזמנים {reverse('10')} שניות", ""],
        ["אבל: דיוק גובה הירח סוטה בכדקה", ""],
        
        [" התאריך העברי מתחלף בשקיעה", ""],
        
        [" מתחת גרא/מגא:  דקות בשעה זמנית", ""],
        [" מתחת שמש/ירח:  אזימוט שמש/ירח", ""],
        ["אזימוט = מעלות מהצפון, וכדלהלן", ""],
        [f"צפון={reverse('0/360')}, מז={reverse('90')}, ד={reverse('180')}, מע={reverse('270')}", ""],
        ["  שלב הירח במסלולו החודשי - באחוזים", ""],
        [f"מולד={reverse('0/100')}, ניגוד={reverse('50')}, רבעים={reverse('25/75')}", ""],
    
        ["רשימת זמני היום בשעות זמניות", ""],
        ["זריחה ושקיעה במישור", "00:00"],
        ["סוף שמע ביום/רבע הלילה", "03:00"],
        ["  סוף תפילה ביום/שליש הלילה", "04:00"],
        ["חצות יום ולילה", "06:00"],
        ["מנחה גדולה", "06:30"],
        ["מנחה קטנה", "09:30"],
        ["פלג המנחה", "10:45"],
        [f"מגא מחושב לפי {reverse('-16°')} בבוקר ובערב", ""],
        
        ["   זמנים במעלות כשהשמש תחת האופק", ""],
        ["זריחת ושקיעת מרכז השמש", "0.0°"],
        ["  זריחה ושקיעה במישור", "-0.833°"],
        
        [f"זמני צאת הכוכבים {reverse('3/4')} מיל במעלות", ""],
        [f"לפי מיל של {reverse('18')} דקות", "-3.65°"],
        [f"לפי מיל של {reverse('22.5')} דקות", "-4.2°"],
        [f"לפי מיל של {reverse('24')} דקות", "-4.61°"],
        ["צאת כוכבים קטנים רצופים", "-6.3°"],
        
        ["  מעלות: עלות השחר/צאת כוכבים דרת", ""],
        [f"לפי 4 מיל של {reverse('18')} דקות", "-16.02°"],
        [f"לפי 4 מיל של {reverse('22.5')} דקות", "-19.75°"],
        [f"לפי 5 מיל של {reverse('24')} דקות", "-25.8°"],
        ["משיכיר/תחילת ציצית ותפילין", "-10.5°"],
        
        
        ["זמנים נוספים", ""],
        ["להימנע מסעודה בערב שבת", "09:00"],
        ["סוף אכילת חמץ", "04:00"],
        ["סוף שריפת חמץ", "05:00"],

        
        ["להלן תנאי מינימום לראיית ירח ראשונה", ""],
        [f"שלב {reverse('4%')}; והפרש גובה שמש-ירח {reverse('8°')}", ""],
    
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
    return current_location_timestamp, location_offset_hours, location_offset_seconds



########################################################################################3
# פונקציה לקרוא את מספר המיקום ברירת מחדל מתוך הקובץ
def read_default_location():
    try:
        with open("halacha_clock/default_location.txt", "r") as f:
            return int(f.read().strip())  # קורא וממיר למספר שלם
    except:
        return 0  # אם יש שגיאה, ברירת מחדל תהיה 0

# הגדרת משתנה גלובלי חשוב מאוד שקובע מה המיקום הנוכחי שעליו מתבצעים החישובים
# משתנה זה נקבע לפי המיקום האינדקסי ששמור בקובץ מיקום ברירת מחדל תוך בדיקה שהאינדקס לא חורג מגבולות הרשימה ואם כן חורג אז יוגדר המיקום האפס כברירת מחדל
# קריאת המיקום מתוך הרשימה בהתאם למספר שבקובץ
default_index = read_default_location()
location = locations[default_index] if 0 <= default_index < len(locations) else locations[0] 
# אינדקס המיקום הנוכחי משתנה גלובלי חשוב מאוד לצורך התקדמות ברשימת המיקומים
# הגדרה שלו על אפס גורמת שכל דפדוף ברשימת המיקומים יתחיל מהתחלה ולא ימשיך מהמיקום האינדקסי של מיקום ברירת המחדל
location_index = 0

##############################################################################################


# משתנה לשליטה על איזה נתונים יוצגו בהסברים במסך של שעון ההלכה בכל שנייה
current_screen_halach_clock = 0.0  # 


# הפונקצייה הראשית שבסוף גם מפעילה את הנתונים על המסך
def main_halach_clock():
       
    # קבלת הזמן המקומי למיקום המבוקש כחותמת זמן - באמצעות פונקצייה שהוגדרה לעיל    
    current_location_timestamp, location_offset_hours, location_offset_seconds = get_current_location_timestamp()
    current_timestamp = current_location_timestamp
            
    # משתנה ששולט על חישוב גובה השמש במעלות לשיטת המג"א ונועד במקור לחישוב דמדומים
    # אם כותבים 16 זה אומר מינוס 16
    # אם רוצים פלוס אז אולי צריך לעשות +16 אבל לא יודע אם זה יעבוד
    # אם עושים None או False או 0 זה לא מחושב כלל (ולכן אם במקרה רוצים כאן זריחה גיאומטרית חייבים להגדיר 0.00001)
    MGA_deg = 16 
    
    # הצהרה על משתנים גלובליים ששומרים את הזמנים הדרושים
    global sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise
    
    # ריקון כל המשתנים כדי שלא ישתמשו בנתונים לא נכונים
    sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
    
        
    # יצירת אובייקט RiSet
    RiSet.tim = round(current_timestamp) ############### אם לא מגדירים את זה אז הזמן הוא לפי הזמן הפנימי של הבקר
    #RiSet.sinho_sun_riset = 0.0 # אם רוצים שזריחה ושקיעה של השמש יהיו לפי זריחה ושקיעה גיאומטריים ולא לפי מינוס 0.833. אם לא מגדירים אז כברירת מחדל יהיה 0.833 מינוס
    riset = RiSet(lat=location["lat"], long=location["long"], lto=location_offset_hours, tl=MGA_deg) # lto=location_offset_hours
      
    # שמירת כל הנתונים על היום הנוכחי כי כולם נוצרים ביחד בעת הגדרת "riset" או בעת שמשנים לו יום
    sunrise, sunset, mga_sunrise, mga_sunset = riset.sunrise(1), riset.sunset(1), riset.tstart(1), riset.tend(1)
       
    # הגדרת הזמן הנוכחי המקומי מחותמת זמן לזמן רגיל
    tm = utime.localtime(current_timestamp)
    year, month, day, rtc_week_day, hour, minute, second, micro_second = (tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0)
        
    # חישוב מה השעה הנוכחית בשבר עשרוני
    current_hour = (hour + (minute / 60) + (second / 3600)) - location_offset_hours
    
    # חישוב גובה השמש והירח וגם אזימוט ועלייה ישרה (עלייה ישרה בשעות עשרוני) ברגע זה. כלומר בשעה הנוכחית בשבר עשרוני
    # לדעת את גובה השמש והירח אפשר גם במיקום שאין בו זריחות ושקיאות וזה לא מחזיר שגיאה אלא מחזיר None שזה כמו אפס
    s_alt, s_az, s_ra, s_dec = riset.alt_az_ra_dec(current_hour, sun=True)
    m_alt, m_az, m_ra, m_dec = riset.alt_az_ra_dec(current_hour, sun=False)
    
    # תיקון גובה הירח כדי שיתאים למה שיש בכוכבים וזמנים. נדרש כנראה בגלל באג בספריית חישובי השמש והירח. למעקב
    # אולי במקור היה צריך להיות פחות 0.833 אבל למעשה יותר מדוייק 0.808
    m_alt = m_alt - 0.45
    
      
    # כל החישובים נעשים רק אם יש זריחה ושקיעה כי אולי במיקום הזה אין בכלל זריחה ושקיעה ביום זה
    if sunrise and sunset:

        # אם מדובר אחרי 12 בלילה ולפני הזריחה לפי אחת משתי השיטות ההלכתיות (ויודעים את זה לפי ששעת הזריחה מאוחרת מהרגע הנוכחי) השעה הזמנית מתחילה בשקיעה של אתמול
        # מגדרים את יום האתמול ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום האתמול    
    
        if (current_timestamp < sunrise) or (mga_sunrise and current_timestamp < mga_sunrise):
            riset.set_day(-1)
            yesterday_sunset, mga_yesterday_sunset = riset.sunset(1), riset.tend(1) if mga_sunrise else None
            tomorrow_sunrise, mga_tomorrow_sunrise = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
            
        # אם מדובר אחרי השקיעה לפי אחת השיטות ולפני השעה 12 בלילה השעה הזמנית מסתיימת בזריחה של מחר
        # מגדירים את יום המחר ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום המחר
        elif (current_timestamp > sunrise and current_timestamp >= sunset) or (mga_sunrise and mga_sunset and current_timestamp > mga_sunrise and current_timestamp >= mga_sunset):
            riset.set_day(1)
            tomorrow_sunrise, mga_tomorrow_sunrise  = riset.sunrise(1), riset.tstart(1) if mga_sunrise else None 
            yesterday_sunset, mga_yesterday_sunset = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
        
    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        sunrise_timestamp, sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = True)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        temporal_time, seconds_in_temporal_hour = calculate_temporal_time(current_timestamp, sunrise_timestamp, sunset_timestamp)
        minutes_in_temporal_hour = str(round(seconds_in_temporal_hour / 60,1)) # str(convert_seconds(seconds_in_temporal_hour))
             
    else:
        
        temporal_time = reverse("שגיאה  ")
        minutes_in_temporal_hour = ""
        
    
    
    # רק אם השמש מגיעה לגובה זה כי אולי במיקום הזה היא לא מגיעה כרגע לגובה זה
    if mga_sunrise and mga_sunset:

        # חישוב מחדש עבור שיטת מגן אברהם    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        mga_sunrise_timestamp, mga_sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = False)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        mga_temporal_time, seconds_in_mga_temporal_hour = calculate_temporal_time(current_timestamp, mga_sunrise_timestamp, mga_sunset_timestamp)
        minutes_in_mga_temporal_hour = str(round(seconds_in_mga_temporal_hour / 60,1)) # str(convert_seconds(seconds_in_mga_temporal_hour))
    else:
        
        mga_temporal_time = reverse("שגיאה  ")
        minutes_in_mga_temporal_hour = ""


    ###########################################################
    # חישוב שלב הירח הנוכחי
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
    
    # חישוב תוספות לשבת כלומר מיום שישי חצי שעה לפני השקיעה עד השקיעה וכן בשבת מהשקיעה ועד צאת שבת שבלוחות
    normal_weekday = get_normal_weekday(rtc_week_day) # חישוב היום בשבוע של התאריך הלועזי בדווקא
    half_hour_before_sunset_until_sunset =  sunset and current_timestamp >= (sunset - 1800) and current_timestamp < sunset # 1800 שניות זה חצי שעה לפני השקיעה
    sunset_until_motsaei_shabat_luchot = sunset and current_timestamp > sunset and s_alt > -8.5
    is_tosafot_leshabat = (normal_weekday == 6 and half_hour_before_sunset_until_sunset) or (normal_weekday == 7 and sunset_until_motsaei_shabat_luchot)
    
    
    # הגדרת ביטול כיבוי אוטומטי בשבת וחג. וכן מחצי שעה לפני השקיעה בשבת ועד מוצאי שבת שבלוחות
    global automatic_deepsleep
    automatic_deepsleep = False if is_shabat or is_tosafot_leshabat or holiday_name else True
    ##############################################################################
      
    # מכאן והלאה ההדפסות למסך
    
    # חישוב אחוזי הסוללה שנותרו או האם מחובר לחשמל
    global voltage
    #voltage_string = f"{round(voltage,1)}v"
    voltage_string = f"{get_battery_percentage(voltage)}%" if voltage < max_battery_v else f"**%"
    
    greg_date_string = f'{day:02d}/{month:02d}/{year:04d}{"!" if time_source in [3,4] else ""}' 
    time_string = f'{hour:02d}:{minute:02d}:{second:02d}{"!" if time_source in [3,4] else ""}'
    
    # מהשקיעה עד 12 בלילה מוסיפים את המילה ליל כי היום בשבוע והתאריך העברי מקבלים לתאריך הלועזי של מחר
    leil_string = reverse("ליל: ") if heb_date_is_next_greg_date else ""
    # אם אין שעון והוגדר זמן שרירותי או שהשעה נלקחה מהשעון הפנימי שכנראה אינו מדוייק מוסיפים סימני קריאה אחרי התאריך העברי
    heb_date_to_print = f'{"!!" if time_source in [3,4] else ""}{reverse(heb_date_string)} ,{reverse(heb_weekday_string)}{leil_string}'
    #magrab_time = calculate_magrab_time(current_timestamp, sunset_timestamp) if sunrise else reverse("שגיאה  ") # רק אם יש זריחה ושקיעה אפשר לחשב
    utc_offset_string = 'utc+0' if location_offset_hours == 0 else f'utc+{location_offset_hours}' if location_offset_hours >0 else "utc"+str(location_offset_hours)
    #coteret = f'{reverse(location["heb_name"])} - {reverse("השעון ההלכתי")}'
    coteret = f'  {voltage_string} - {reverse(location["heb_name"])} - {reverse("שעון ההלכה")}'
    
    tft.fill(0) # מחיקת המסך

    # איזור כותרת
    tft.write(FontHeb20,f'{coteret}',center(coteret,FontHeb20),0, s3lcd.GREEN, s3lcd.BLACK) #fg=s3lcd.WHITE, bg=s3lcd.BLACK בכוונה מוגדר אחרי השורה הקודמת בגלל הרקע הצהוב
    
    # איזור תאריך עברי כולל צבע מתאים לימי חול ולשבתות וחגים
    # צבע הטקסט והרקע של התאריך העברי: ביום חול לבן על שחור ובשבת וחג שחור על צהוב, ובחגים דרבנן כולל תעניות שחור על ציאן
    HEB_DATE_FG, HEB_DATE_BG  = (s3lcd.BLACK, s3lcd.YELLOW) if is_shabat or holiday_name else (s3lcd.BLACK, s3lcd.CYAN) if lite_holiday_name or is_rosh_chodesh else (s3lcd.WHITE, s3lcd.BLACK)
    tft.write(FontHeb25,f'{heb_date_to_print}',center(heb_date_to_print,FontHeb25),20, HEB_DATE_FG, HEB_DATE_BG)
   
    # איזור שעה זמנית
    tft.write(FontHeb20,f'                 {reverse("מגא")}                         {reverse("גרא")}',0,46)
    tft.write(FontHeb40,f'{temporal_time}', 140, 45, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{minutes_in_temporal_hour}',283,62, s3lcd.CYAN, s3lcd.BLACK)
    if MGA_deg:
        tft.write(FontHeb25,f' {mga_temporal_time}', 0, 50, s3lcd.GREEN, s3lcd.BLACK)
        tft.write(FontHeb20,f'{minutes_in_mga_temporal_hour}',102,62, s3lcd.CYAN, s3lcd.BLACK)
  
    # איזור גובה אזימוט שמש וירח ושלב ירח
    tft.write(FontHeb20,f'                 {reverse("ירח")}                         {reverse("שמש")}',0,82)
    tft.write(FontHeb20,f'{"  " if m_az < 10 else " " if m_az < 100 else ""}{round(m_az)}°', 98,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{"  " if s_az < 10 else " " if s_az < 100 else ""}{round(s_az)}°', 281,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb25,f' {" " if m_alt > 0 else ""}{" " if abs(m_alt) <10 else ""}{m_alt:.3f}°',0,80, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'    {phase_percent:.1f}%',0,101, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb40,f"{" " if s_alt > 0 else ""}{" " if abs(s_alt) <10 else ""}{round(s_alt,3):.3f}°", 140, 81, s3lcd.GREEN, s3lcd.BLACK)
    
    # איזור שורת הסברים מתחלפת
    #tft.write(FontHeb20,f'                 :{reverse("שעון מהשקיעה )אי/מגרב(")}',0,123) #    {riset.sunset(2)} :{reverse("שקיעה")}    
    #tft.write(FontHeb25,f' {magrab_time}',0,120, s3lcd.GREEN, s3lcd.BLACK) #
    text = reverse(esberim[int(current_screen_halach_clock)][0])  # רוורס של הטקסט העברי
    time_value = esberim[int(current_screen_halach_clock)][1]  # הערך להצגה
    CCC = f"{time_value}  :{text}" if time_value != "" else f"{text}"
    tft.write(FontHeb20, f"{CCC}" ,center(CCC, FontHeb20) , 123)  # כתיבה למסך 

    # איזור תאריך לועזי ושעה רגילה והפרש מגריניץ
    #tft.write(FontHeb25,f' {greg_date_string}                  {utc_offset_string}',0,147)
    #tft.write(FontHeb30,f'{time_string}', 133, 145, s3lcd.GREEN, s3lcd.BLACK)
    
    # איזור תאריך לועזי ושעה רגילה והפרש מגריניץ
    tft.write(FontHeb25,f' {greg_date_string}                  {utc_offset_string}',0,147)
    tft.write(FontHeb30,f'{time_string}', 133, 145, s3lcd.GREEN, s3lcd.BLACK)

    # איזור קווי הפרדה. חייב להיות אחרי הכל כדי שיעלה מעל הכל
    tft.line(0, 45, 320, 45, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 80, 320, 80, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 120, 320, 120, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 145, 320, 145, s3lcd.YELLOW) # קו הפרדה

    tft.show() # כדי להציג את הנתונים על המסך
    
    
################################################################################


# פונקצייה לשמירת המיקום האינדקסי של המיקום הנוכחי לקובץ מיקום ברירת מחדל כדי שזה המיקום שייפתח בפעם הראשונה שנכנסים לתוכנה
def save_default_location(index):
    """ שומר את המיקום הנוכחי בקובץ """
    try:
        with open("halacha_clock/default_location.txt", "w") as f:
            f.write(str(index))
    except Exception as e:
        print("שגיאה בשמירת המיקום:", e)


# פונקצייה שמחזירה את מיקום ברירת המחדל להיות המיקום הנוכחי
def go_to_default_location():
    # הצהרה על משתנים גלובליים
    global location, location_index
    # מחזיר את המיקום הנוכחי להיות מיקום ברירת מחדל
    default_index = read_default_location()
    location = locations[default_index] if 0 <= default_index < len(locations) else locations[0]
    # מאפס את המיקום שאוחזים בו בדפדוף ברשימת המיקומים כך שהדפדוף הבא יתחיל מהתחלה ולא מהמיקום האינדקסי של מיקום ברירת המחדל
    location_index = 0

############################################################################################################################################################
#################################################################   איזור הטיפול במד טמפרטורה לחות ולחץ ברומטרי  ###########################################
############################################################################################################################################################

# פונקצייה לקבלת הזמן המשמש בכל החלק בקוד שמטפל במזג האוויר
# מדובר בזמן מקומי במיקום ברירת המחדל המוגדר
def get_location_localtime():
    # מקבל את השעה המקומית במיקום ברירת המחדל כחותמת זמן
    current_location_timestamp, location_offset_hours, location_offset_seconds = get_current_location_timestamp()
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

def format_time(time_tuple):
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
    global voltage
    #voltage_string = f"{round(voltage,1)}v"
    voltage_string = f"{get_battery_percentage(voltage)}%" if voltage < max_battery_v else f"**%"
    
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
        tft.write(FontHeb25,f'{format_time(min_time_temp)} {reverse("בשעה")} {min_temp:.1f}c {reverse("מינ טמפ")}', 20, 125)
        tft.write(FontHeb25,f'{format_time(max_time_temp)} {reverse("בשעה")} {max_temp:.1f}c    {reverse("מקס")}', 20, 145)

    elif screen == 1:  # Humidity
        tft.write(FontHeb25,f'{format_time(min_time_humidity)} {reverse("בשעה")} {min_humidity:.1f}% {reverse("מינ לחות")}', 10, 125)
        tft.write(FontHeb25,f'{format_time(max_time_humidity)} {reverse("בשעה")} {max_humidity:.1f}%    {reverse("מקס")}', 10, 145)
    
    elif screen == 2:  # Pressure
        tft.write(FontHeb25,f'{format_time(min_time_pressure)} {reverse("בשעה")} {min_pressure:.1f}hPa {reverse("מינ לחץ")}', 0, 125)
        tft.write(FontHeb25,f'{format_time(max_time_pressure)} {reverse("בשעה")} {max_pressure:.1f}hPa    {reverse("מקס")}', 0, 145)
        
    tft.show()



#############################################################################################################################################################
###########################################################  סוף קוד המטפל במד טמפרטורה לחות ולחץ ברומטרי  #############################################
#############################################################################################################################################################


# משתנים חשובים מאוד לשמירת הזמן בתחילה כדי להשוות אליהם בהמשך ולדעת האם לעדכן דברים או לכבות את המסך וכדומה
t_time = time.time()
start_time_for_check_and_set_time = t_time
start_time_for_automatic_deepsleep = t_time

#########################################################################################################

# פונקצייה מאוד חשובה לקביעה כמה זמן לחצו על כפתור האם לחיצה ארוכה או קצרה
def handle_button_press(specific_button):
    start_time = time.ticks_ms()
    # הלולאה הזו מתבצעת אם לוחים ברציפות בלי לעזוב
    while specific_button.value() == 0:  # כל עוד הכפתור לחוץ
        if time.ticks_diff(time.ticks_ms(), start_time) > 3000:  # לחיצה ארוכה מעל 3 שניות
            return "long"
    # מכאן והלאה מתבצע רק אחרי שעוזבים את הכפתור ואז מודדים כמה זמן היה לחוץ
    if 100 < time.ticks_diff(time.ticks_ms(), start_time) < 1000: # לחיצה קצרה מתחת לשנייה אחת אבל מעל 100 מיקרו שניות כדי למנוע לחיצה כפולה
        return "short"
    return None  # במידה ולא זוהתה לחיצה
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
######################################################################################################33

def toggle_location(pin):
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
        # לחיצה ארוכה: שמירת המיקום כברירת מחדל
        save_default_location(location_index)
        
        # הדפסה למסך שנבחר מיקום ברירת מחדל חדש
        tft.fill(0) # מחיקת המסך
        tft.write(FontHeb20,f'{reverse("מיקום ברירת מחדל הוגדר בהצלחה")}',20,75)
        tft.write(FontHeb25,f'{reverse(locations[location_index]["heb_name"])}',120,100)
        tft.show() # כדי להציג את הנתונים על המסך
        time.sleep(5) # השהייה 5 שניות כדי שיהיה זמן לראות את ההודעה לפני שהמסך ייתמלא שוב בחישובים
        

# חיבור הכפתור לפונקציה
boot_button.irq(trigger=Pin.IRQ_FALLING, handler=toggle_location)


##############################################################################################################################3
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


##################################################################################################################
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
#################################################################################################33

# הפונקצייה הראשית שמפעילה את כל החלקים יחד
def main_main():
    
    # הצהרה על משתנים גלובליים שצריך להגדיר אותם מחדש בתוך פונקצייה זו
    global power_state, voltage, start_time_for_automatic_deepsleep, start_time_for_check_and_set_time, is_bme280_connected, bme
    global current_screen_halach_clock, current_screen_bme280

    # קריאת המתח של החשמל ולפי זה קביעת רמת התאורה האחורית של המסך כדי לחסוך בצריכת חשמל וכן הדלקת רכיבים נוספים שקשורים למסך ולכוח
    current_voltage = read_battery_voltage()
    # שווה לערך של המשתנה הכללי ששומר את המתח מהשנייה הקודמת
    last_voltage = voltage   
    # חייבים לאפס את זה כל שנייה מחדש כדי שנוכל להשוות את השנייה הקודמת לשנייה הנוכחית
    # אחרי שקראנו ושמרנו את המתח הקודם, כעת מעדכנים את המשתנה הגלובלי במתח הנוכחי וזה משמש גם עבור דברים אחרים בתוכנה
    voltage = current_voltage
    
    # קורא את הזמן העדכני בכל שנייה מחדש
    current_time = time.time()
    
    # תיקון כדי שניתוק BME280 לאחר דקות ממהדלקה לא יכניס מייד למצב שינה
    if is_bme280_connected:
        # עדכון זמן הקריאה האחרונה
        start_time_for_automatic_deepsleep = current_time
            
    # תיקון כדי שניתוק מהחשמל ייתן ארכה של כמה שניות לפני כיבוי    
    if last_voltage > max_battery_v and current_voltage < max_battery_v and abs(last_voltage - current_voltage) > 0.5:
        start_time_for_automatic_deepsleep = current_time
    
    # אם מוגדר שינה אוטומטית והמתח מראה שמחובר לסוללה ולא לחשמל ועברו ... דקות מאז הפעלת התוכנה אז מגדירים את המשתנה power_state לכבות את המכשיר
    # המשתנה automatic_deepsleep מוגדר בפונקציית main_halach_clock שבשבת וחג לא מכבים את המסך או נכנסים למצב שינה
    # בתחילה מגדירים משתנה מאוד חשוב שקובע אחרי כמה זמן ניכנס למצב שינה או למסך כבוי באופן אוטומטי
    # כרגע מוגדר ל 150 שניות כי אחרת לא יוכלו לראות את כל ההסברים אם ייכבה קודם
    seconsd_to_start_auto_deepsleep = 150 
    if automatic_deepsleep and current_voltage < max_battery_v and (current_time - start_time_for_automatic_deepsleep) >= seconsd_to_start_auto_deepsleep:
        power_state = False
                 
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
        duty_for_backligth = 500 if current_voltage > max_battery_v else 255
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
                current_screen_bme280 = (current_screen_bme280 + 0.1) % 3  # Cycle through screens (0, 1, 2)
                time.sleep(1) # עדכון כל שניה
                gc.collect() # ניקוי הזיכרון חשוב נורא כדי למנוע קריסות
            except:
                is_bme280_connected = False
        
        # אם BME280 לא מחובר אז התוכנה מתפקדת כשעון ההלכה
        else:
            # הפעלת הפונקצייה הראשית והשהייה קטנה לפני שחוזרים עליה שוב
            main_halach_clock()
            current_screen_halach_clock = (current_screen_halach_clock + 0.39) % len(esberim)  # זה גורם מחזור של שניות לאיזה נתונים יוצגו במסך
            time.sleep(0.825)  # רענון כל שנייה אבל צריך לכוון את זה לפי כמה כבד הקוד עד שהתצוגה בפועל תתעדכן כל שנייה ולא יותר ולא בפחות
            gc.collect() # ניקוי הזיכרון חשוב נורא כדי למנוע קריסות
            
    # אם הכוח לא פועל אז יש לכבות הכל
    else:
      
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
        '''
        # אפשרויות נוספות שכרגע לא פעילות ורשומות רק לזיכרון שהן קיימות
        # machine.lightsleep() # אולי שומר את השעון הפנימי טוב יותר משינה עמוקה
        # machine.lightsleep(120 * 1000) # שינה עמוקה לשתי דקות ואז מתעורר 
        '''


# לולאת רענון חשובה ביותר שחוזרת על עצמה כל הזמן והיא זו שמפעילה את הפונקצייה הראשית כל שנייה מחדש
while True:
    main_main()
