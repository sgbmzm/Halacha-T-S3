# ========================================================
# License: Personal Use Only  
# This file (`main_shemesh_s3.py`) is licensed for **personal use only**.  
# You may **not** modify, edit, or alter this file in any way.  
# Commercial use is strictly prohibited.  
# If you wish to use this file for business or organizational purposes,  
# please contact the author.  
# ========================================================

# משתנה גלובלי שמציין את גרסת התוכנה למעקב אחרי עדכונים
VERSION = 1

# סיכום קצר על התוצאות המעשיות של הכפתורים בקוד הזה
# לחיצה על שתי הכפתורים בו זמנית כאשר המכשיר כבוי: עדכון תוכנת המכשיר
# לחיצה על כפתור 14 כאשר המכשיר כבוי ותוך כדי כך לחיצה על כפתור ההפעלה: עדכון השעון החיצוני מהרשת 
# הפעלת המכשיר בלחיצה קצרה על כפתור ההפעלה: בהירות מסך רגילה
# הפעלת המכשיר בלחיצה ארוכה על כפתור ההפעלה: בהירות מסך הכי גבוהה אם המכשיר מחובר לחשמל במתח 5 וולט ומעלה




# קוד נורא חשוב לחישובי שמש וירח במיקרופייתון

# https://github.com/peterhinch/micropython-samples/issues/42
# https://github.com/peterhinch/micropython-samples/tree/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy
# https://github.com/peterhinch/micropython-samples/blob/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy/sun_moon.py
# https://github.com/peterhinch/micropython-samples/blob/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy/moonphase.py



# צריך לחשוב איך לגרום שהשעון יהיה מוגדר אוטומטית לשעון קיץ בתאריכים המתאימים.


import time, math, machine, utime, esp32, network, ntptime
from machine import I2C, Pin, ADC, PWM
import gc # חשוב נורא לניקוי הזיכרון
#import datetime as dt
#from halacha_clock.sun_moon import RiSet  # ספריית חישובי שמש
from halacha_clock.ds3231 import DS3231 # שעון חיצוני
#from halacha_clock import gematria_pyluach

import bme280
from time import sleep, localtime

# פונטים
import halacha_clock.miriam40 as FontHeb40
import halacha_clock.miriam20 as FontHeb20
import halacha_clock.miriam25 as FontHeb25
import halacha_clock.miriam30 as FontHeb30

# למסך
import halacha_clock.tft_config as tft_config
import s3lcd

# הגדרת המסך
tft = tft_config.config(rotation=3) # כיוון סיבוב התצוגה שאני רוצה
tft.init() # כך חייבים לעשות



# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח



################################


# Initialize I2C for both OLED and BME280
i2c_BME280 = machine.SoftI2C(scl=Pin(10), sda=Pin(11))
original_i2c = machine.I2C(scl=Pin(44), sda=Pin(43))


# משתנה גלובלי חשוב מאוד ששומר את השאלה האם לעדכן את השעון החיצוני מהרשת
# ברירת המחדל היא שלא
is_original_i2c = True
# אבל אם בשעת הדלקת המכשיר שזו שעת תחילת ריצת הקוד כפתור בוט לחוץ אז כן לעדכן
#if boot_button.value() == 0:  # בודק אם הכפתור לחוץ בשעת הדלקת המכשיר
#    is_original_i2c = False 



# Initialize BME280 sensor
#bme = bme280.BME280(i2c=i2c_BME280)
bme = bme280.BME280(i2c=original_i2c if is_original_i2c else i2c_BME280)


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
###########################################################################################################

####################################################################################################3

# משתנה גלובלי חשוב מאוד ששומר את השאלה האם לעדכן את השעון החיצוני מהרשת
# ברירת המחדל היא שלא
ntp_update = False
# אבל אם בשעת הדלקת המכשיר שזו שעת תחילת ריצת הקוד כפתור בוט לחוץ אז כן לעדכן
if boot_button.value() == 0:  # בודק אם הכפתור לחוץ בשעת הדלקת המכשיר
    ntp_update = True 


# משתנה גלובלי חשוב שקובע האם המשתמש רוצה בהירות מסך הכי גבוהה
# זה יהיה בסוף הכי בהיר רק אם המכשיר מחובר לחשמל מעל 5 וולט מתח
# ברירת המחדל היא שבהירות המסך נמוכה יותר ולא הכי גבוהה כי זה מסנוור
# אבל אם מדליקים את המכשיר בלחיצה ארוכה על כפתור ההדלקה אז הבהירות תהיה הכי גבוהה שיש
# זה חייב להיקבע כאן מתחילת ריצת הקוד כדי שלא יתנגש בדברים אחרים שהכפתור עושה
behirut_max = False
if button_14.value() == 0:  # בודק אם הכפתור לחוץ בשעת הדלקת המכשיר
    behirut_max = True

###############################################################3

# משתנה למעקב אחר מצב הכוח כלומר האם המכשיר כעת במצב שהפינים שנותנים כוח למסך מופעלים או כבויים
# המשמעות של זה מגיעה לידי ביטוי בפונקצייה הראשית: main
# זה משתנה חשוב נורא!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
power_state = True  

# פונקציה שמופעלת בלחיצה
def toggle_power(pin):
    global power_state
    time.sleep_ms(50)  # debounce
    if button_14.value() == 0:  # בודק אם הכפתור עדיין לחוץ
        power_state = not power_state  # הפיכת המצב
        while button_14.value() == 0:  # ממתין שהכפתור ישתחרר
            time.sleep_ms(50)

# חיבור הכפתור לפונקציה לחיצה על הכפתור קוראת לפונקצייה שמעדכנת את משתנה הכוח
# כרגע מתבצע באמצעות כפתור בוט אבל אפשר גם באמצעות הכפתור השני
button_14.irq(trigger=Pin.IRQ_FALLING, handler=toggle_power)

############################################################################################

# זה כרגע לא רלוונטי לקוד. אולי בעתיד
# פונקצייה שמגדירה את השעון הפנימי של הבקר לזמן ספציפי שנותנים לה בפורמט חותמת זמן
def set_mashine_time(timestamp):
    tm = utime.localtime(timestamp)
    # הגדרת ה-RTC
    rtc_system = machine.RTC()
    rtc_system.datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))  # tm[6] הוא היום בשבוע

#########################################

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
def is_now_israel_DST():
    # קבלת השנה הנוכחית
    current_year = utime.localtime()[0]
    
    # חישוב יום ראשון האחרון של מרץ
    march_last_sunday = utime.mktime((current_year, 3, 31, 2, 0, 0, 0, 0, 0))
    while utime.localtime(march_last_sunday)[6] != get_rtc_weekday(1):
        march_last_sunday -= 86400  # מורידים יום
    
    # חישוב יום שישי שלפני יום ראשון האחרון של מרץ
    # אם יום ראשון האחרון הוא ה-31, אז יום שישי לפניו יהיה ה-29.
    last_friday_march = march_last_sunday - 2 * 86400  # מורידים 2 ימים (שישי)

    # חישוב יום ראשון האחרון של אוקטובר
    october_last_sunday = utime.mktime((current_year, 10, 31, 2, 0, 0, 0, 0, 0))
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
    
    
    

#######################################################################################3

# מונקצייה שמנסה להתחבר לווייפי ולקבל את הזמן הנוכחי ב UTC-0
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
                    # המרת הזמן לשעון בישראל
                    israel_offset_seconds = get_generic_utc_offset(35, dst=is_now_israel_DST(), in_seconds = True) # ישראל זה קו אורך 35
                    current_israel_timestamp = ntp_timestamp_utc + israel_offset_seconds # כי ישראל היא אחרי יוטיסי
                    # המרת הזמן הנוכחי בישראל מחותמת זמן לפורמט של תאריך ושעה
                    ntp_localtime = utime.localtime(current_israel_timestamp)
                    
                    print("השעה התקבלה בהצלחה!", ntp_localtime)
                    return ntp_localtime  # מחזיר את הזמן ומכבה את ה-WiFi (נכבה תמיד ב-finally)
                
                except Exception as ntp_error:
                    print(f"שגיאה בקבלת הזמן מהרשת {ssid}: {ntp_error}")
                    wlan.disconnect()  # ניתוק בלבד, ננסה רשת אחרת

        raise Exception("כשלון בקבלת הזמן משרת בכל רשת")

    except Exception as error:
        return f"{str(error)}"

    finally:
        wlan.active(False)  # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו



#################################################################################################


    
# פונקציה לקרוא את הזמן מ-DS3231 ולעדכן את ה-machine.RTC()
def sync_rtc_with_ds3231():
         
    try:
        
        # נתינת חשמל חיובי לפין המתאים של ds3231
        ds3231_plus = machine.Pin(17, machine.Pin.OUT)
        ds3231_plus.value(1)

        # יצירת אובייקט I2C (בהנחה שהשימוש בפינים 21 ו-22)
        # בפין 12 חובה להשתמש דווקא ב softI2C
        ds3231_i2c = machine.SoftI2C(scl=machine.Pin(16), sda=machine.Pin(21))
        
        # יצירת אובייקט RTC במערכת (machine RTC)
        rtc_system = machine.RTC()

        # יצירת אובייקט DS3231
        rtc_ds3231 = DS3231(ds3231_i2c)
        
        # קריאת הזמן מ-DS3231
        ds3231_time = rtc_ds3231.datetime()
       
        
        ################################################################################################
        # כל החלק הזה קשור לאופצייה של עדכון השעון הפנימי שבדרך כלל לא מתבצעת
        
        # ברירת המחדל היא לא לעדכן את השעון החיצוני
        # ואם הבקר לא מחובר למחשב אסור לעדכן את השעון החיצוני לפי השעון הפנימי
        # רק אם הבקר מחובר למחשב אפשר לעדכן את השעון החיצוני לפי שעון המחשב אם רוצים
        # גם זה לא מומלץ כי יתן שעון קיץ בקיץ וכדאי לשמור את השעון החיצוני על שעון חורף
        update_ds3231_manually = False # False or True  
        update_ds3231_from_computer = False # False or True
        
        # זה חשוב מאוד לפעם הראשונה שבה השעון החיצוני עדיין לא עודכן ולכן השנה בו היא 2000 וזה גם גורם לשגיאות בתאריך העברי
        if ds3231_time[0] < 2016:
            update_ds3231_from_ntp = True

        # הקביעה האם מעדכנים את השעון החיצוני מהשרת הולכת לפי המשתנה הגלובלי שנקבע בתחילת הקוד לפי האם הכפתור היה לחוץ
        global ntp_update
        update_ds3231_from_ntp = ntp_update
        
        ##################################################################################3
        # הבעיה היא שאם מפעילים את זה כאן זה יקרה רק אם יכבו את המכשיר וידליקו אותו
        # לכן צריך לשים את זה בוויל טרו למטה שירוז כל הזמן ויבדוק מה התאריך ואז יקרא לפונקצייה הזו עם טרו על אפדייט פרום ארטיסי
        #if time.localtime()[2] in [1,15]: # בכל ראשון ו 15 לחודש לועזי. אבל זה יקרה בכל הדלקה מחדש ביום זה
        #if (time.time() // 86400) % 30 in [0,15]: # פעם ב 15 ימים לעדכן את השעון החיצוני. 86400 זה מספר השניות ביממה
        #    update_ds3231_from_ntp = True
            
        ############################################################################################333
            
        
        if update_ds3231_manually or update_ds3231_from_computer or update_ds3231_from_ntp:
            
            if update_ds3231_from_computer:
            
                # קריאת זמן המערכת של הבקר שזה הזמן המדוייק של המחשב רק כאשר הבקר מחובר למחשב
                year, month, day, week_day, hour, minute, second, micro_second = rtc_system.datetime()
                # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
                new_time = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
                
                print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
            
                # עדכון הזמן ב-RTC
                rtc_ds3231.datetime(new_time)

                print("זמן המחשב עודכן בשעון החיצוני בהצלחה. השעה לאחר העדכון היא", rtc_ds3231.datetime())

                
            elif update_ds3231_from_ntp:
                
                
                # הדפסה למסך
                tft.fill(0) # מחיקת המסך
                tft.write(FontHeb25,f'{reverse("בתהליך עדכון השעון...")}',0,55)
                tft.write(FontHeb20,f'{reverse("מחפש רשת ללא סיסמה...")}',0,75)
                tft.show() # כדי להציג את הנתונים על המסך
                
                        
                # קבלת זמן ntp מהשרת ואם יש שגיאה המשתנה הזה יכיל את השגיאה
                ntp_time = get_ntp_time()
                
                try:
                    
                        
                    # קריאת זמן המערכת של הבקר שזה הזמן המדוייק של המחשב רק כאשר הבקר מחובר למחשב
                    year, month, day, hour, minute, second, week_day, year_day = ntp_time
                    # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
                    new_time = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
                    
                    
                    print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
                
                    # עדכון הזמן ב-RTC
                    rtc_ds3231.datetime(new_time)
                    
                    #tft.fill(0) # מחיקת המסך
                    tft.write(FontHeb25,f'{reverse("עודכן בהצלחה השעון")}',30,95)
                    tft.show() # כדי להציג את הנתונים על המסך
                    time.sleep(5) # כדי שהמשתמש יוכל לראות מה יש במסך לפני שהכיתוב נעלם

                    print("זמן שרת עודכן בשעון החיצוני בהצלחה. השעה לאחר העדכון היא", rtc_ds3231.datetime())
                    # קריאה חוזרת לפונקצייה זו כדי שהשעון הפנימי יהיה מעודכן בזמן החדש
                    return sync_rtc_with_ds3231(update_ds3231_from_ntp = False)
                    
                except Exception as error:
                    tft.write(FontHeb25,f'{reverse("שגיאה בעדכון השעון")}',30,95)
                    tft.write(FontHeb20,f'{str(error)}',0,115)
                    tft.write(FontHeb20,f'{reverse(ntp_time)}',0,140)
                    tft.show() # כדי להציג את הנתונים על המסך
                    time.sleep(5) # כדי שהמשתמש יוכל לראות מה יש במסך לפני שהכיתוב נעלם
                    print(f"שגיאה בעדכון שעון חיצוני מהשרת: {str(error)} פונקציית אנטיפי מחזירה {ntp_time}")
                    # אם השעון החיצוני לא עודכן מעולם ולכן הוא בשנת 2000 אז צריך לקרוא שוב ושוב לפונקציית העדכון עד שהשעון החיצוני יעודכן
                    if ds3231_time[0] < 2016:
                        return sync_rtc_with_ds3231(update_ds3231_from_ntp = True)

            
            elif update_ds3231_manually:
                
                # כאן אפשר לבחור לבד איזה נתונים לכוון לשעון החיצוני
                year, month, day, hour, minute, second, weekday = 1988, 2, 24, 18, 45, 56, 1 # 1 = sunday                
                new_time = (year, month, day, hour, minute, second, weekday)


                print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
                
                # עדכון הזמן ב-RTC
                rtc_ds3231.datetime(new_time)

                print("זמן ידני עודכן בשעון החיצוני בהצלחה. השעה לאחר העדכון היא", rtc_ds3231.datetime())

        ###################################################################################################################          
            
        # עדכון ה-machine RTC עם הזמן שנקרא מ-DS3231
        rtc_system.datetime(ds3231_time)
        print("Time synced with DS3231: ", ds3231_time)
        
        # כיבוי החשמל החיובי שהולך לשעון החיצוני כי כבר לא צריך אותו
        # זה לא חובה
        ds3231_plus.value(0)

    except Exception as e:
        print("Error reading from DS3231: ", e)
        #במקרה של שגיאה, נגדיר זמן ידני ב-machine.RTC()
        manual_time = (2020, 12, 20, get_rtc_weekday(6), 16, 39, 0, 0)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
        rtc_system.datetime(manual_time)
        print("Time set manually in machine.RTC: ", manual_time)
        


###########################################################




# הגדרת הזמן
rtc = machine.RTC()
#rtc.datetime((2024, 12, 12, 3, 18, 5, 0, 0))  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
sync_rtc_with_ds3231()


# Variables for minimum and maximum tracking
min_temp = float('inf')
max_temp = float('-inf')
min_humidity = float('inf')
max_humidity = float('-inf')
min_pressure = float('inf')
max_pressure = float('-inf')

min_time_temp = localtime()
max_time_temp = localtime()
min_time_humidity = localtime()
max_time_humidity = localtime()
min_time_pressure = localtime()
max_time_pressure = localtime()

# Variable for current day tracking
current_date = localtime()[0:3]

# State for display toggling
current_screen = 0.0  # 0: Temperature, 1: Humidity, 2: Pressure


def get_sea_level_pressure_hpa(P_hpa, T_celsius, h_meters, M=0.0289644, g=9.80665, R=8.3144598):
    """
    Computes the sea level atmospheric pressure given the pressure at a specific height.

    Parameters:
        P_hpa (float): Pressure at the given height (hPa).
        T_celsius (float): Temperature at the given height (°C).
        h_meters (float): Height above sea level (meters).
        M (float): Molar mass of Earth's air (kg/mol). Default is 0.0289644.
        g (float): Gravitational acceleration (m/s^2). Default is 9.80665.
        R (float): Universal gas constant (J/(mol·K)). Default is 8.3144598.

    Returns:
        float: Atmospheric pressure at sea level (hPa).
    """
    # Convert inputs
    P = P_hpa * 100  # Convert hPa to Pa
    T = T_celsius + 273.15  # Convert Celsius to Kelvin

    # Reverse barometric formula to calculate sea-level pressure
    P0 = P * math.exp(M * g * h_meters / (R * T))

    # Convert back to hPa
    return P0 / 100
    

def get_data():
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
        min_time_temp = localtime()
    if temp > max_temp:
        max_temp = temp
        max_time_temp = localtime()

    if humidity < min_humidity:
        min_humidity = humidity
        min_time_humidity = localtime()
    if humidity > max_humidity:
        max_humidity = humidity
        max_time_humidity = localtime()

    if pressure < min_pressure:
        min_pressure = pressure
        min_time_pressure = localtime()
    if pressure > max_pressure:
        max_pressure = pressure
        max_time_pressure = localtime()

def reset_min_max_if_new_day():
    """Resets minimum and maximum values if the day changes."""
    global min_temp, max_temp, min_humidity, max_humidity, min_pressure, max_pressure
    global min_time_temp, max_time_temp, min_time_humidity, max_time_humidity, min_time_pressure, max_time_pressure
    global current_date

    today = localtime()[0:3]
    if today != current_date:
        current_date = today
        min_temp = float('inf')
        max_temp = float('-inf')
        min_humidity = float('inf')
        max_humidity = float('-inf')
        min_pressure = float('inf')
        max_pressure = float('-inf')
        min_time_temp = localtime()
        max_time_temp = localtime()
        min_time_humidity = localtime()
        max_time_humidity = localtime()
        min_time_pressure = localtime()
        max_time_pressure = localtime()

def format_time(time_tuple):
    """Formats time tuple to HH:MM."""
    return '{:02}:{:02}'.format(time_tuple[3], time_tuple[4])

def display_data():
    """Displays sensor readings and additional information on OLED."""
    global current_screen

    temp, humidity, pressure = get_data()
    # גובה התחנה
    altitude = 320
    # תיקון חישוב הלחץ לגובה פני הים 
    delta_p = 10 * (altitude/100) # כלל האצבע: לחץ האוויר יורד בכ-12 hPa לכל 100 מטרים בגובה
    pressure_at_sea_level = pressure + delta_p
    #pressure_at_sea_level = get_sea_level_pressure_hpa(pressure, temp, altitude)

    update_min_max(temp, humidity, pressure_at_sea_level)
    reset_min_max_if_new_day()
    
    # Calculate dew point
    dew_point = temp - ((100 - humidity) / 5)

    tft.fill(0)

    t = localtime()
    time_string = "{:02d}/{:02d}/{:04d} {:02d}:{:02d}:{:02d}".format(t[2], t[1], t[0], t[3], t[4], t[5]) # להוסיף יום בשבוע
    tft.write(FontHeb25,f'         {time_string}', 0, 0)
    tft.write(FontHeb20,f'                    {reverse("לחות")}                   {reverse("טמפ.")}',0,30)
    tft.write(FontHeb40,f'{temp:.1f}c', 180, 20, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb40,f' {humidity:.1f}%', 0, 20, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb25,f'              {dew_point:.1f} c :{reverse("נקודת טל")}', 0, 54)
    
    tft.write(FontHeb25,f'{pressure:.1f} hPa  {reverse("לחץ בגובה")}', 50, 77)
    tft.write(FontHeb25,f'{pressure_at_sea_level:.1f} hPa  {reverse("לחץ מתוקן")}', 50, 100)
    
    screen = int(current_screen)

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





# משתנה לזמן הקריאה האחרונה
last_read_time = time.time()


# הגדרת הפינים שצריך לכבות כדי שהמסך ייכבה והמכשיר יהיה בצריכת חשמל נמוכה
LCD_POWER = Pin(15, Pin.OUT)
RD = Pin(9, Pin.OUT)
# לאחר מכן להפעיל PWM כדי לשלוט במידת התאורה האחורית של המסך
BACKLIGHT = PWM(Pin(38, Pin.OUT), freq=1000)
PWM_MAX = 1023 # תאורה הכי גבוהה
PWM_MIN = 0 # התאורה כבוייה

 # קריאת המתח של החשמל ולפי זה קביעת רמת התאורה האחורית של המסך כדי לחסוך בצריכת חשמל וכן הדלקת רכיבים נוספים שקשורים למסך ולכוח
#voltage = read_battery_voltage()
# אם המתח מעל 4.6 וולט והמשתמש רוצה בהירות מקס כפי שהוגדר בתחילת הקוד אז הבהירות הכי גבוהה
# אם המשתמש לא הגדיר בתחילת הקוד בהירות הכי גבוהה אז הבהירות תהיה בינונית אם המתח גדול מ 4.6 כלומר שלא מחובר רק לסוללה הפנימית
# בכל מקרה אחר מחובר רק לסוללה הפנימית או גם אם לחיצונית אבל היא חלשה הכוח הוא 255 שזה רבע בהירות, כדי לחסוך בחשמל
#duty_for_backligth = PWM_MAX if (voltage >= 4.6 and behirut_max) else 450 if voltage > 4.6 else 255
#BACKLIGHT.duty(duty_for_backligth)
BACKLIGHT.duty(255)
#RD.value(1)
#LCD_POWER.value(1)


# Main loop to continuously update data
while True:
    display_data()
    current_screen = (current_screen + 0.1) % 3  # Cycle through screens (0, 1, 2)
    sleep(1) # עדכון כל 10 שניות



