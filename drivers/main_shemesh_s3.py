# ========================================================
# License: Personal Use Only  
# This file (`main_shemesh_s3.py`) is licensed for **personal use only**.  
# You may **not** modify, edit, or alter this file in any way.  
# Commercial use is strictly prohibited.  
# If you wish to use this file for business or organizational purposes,  
# please contact the author.  
# ========================================================

# משתנה גלובלי שמציין את גרסת התוכנה למעקב אחרי עדכונים
VERSION = "26/02/2025"

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
from halacha_clock.sun_moon_sgb import RiSet  # ספריית חישובי שמש
from halacha_clock.moonphase import MoonPhase  # ספריית חישובי שלב הירח
from halacha_clock.ds3231 import DS3231 # שעון חיצוני
from halacha_clock import gematria_pyluach

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

# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח

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
# כרגע פונקצייה זו לא פעילה.
def calculate_magrab_time(timestamp, sunset_timestamp):
        
        # חישוב כמה שניות עברו מאז הזריחה או השקיעה עד הזמן הנוכחי 
        time_since_last_sunset = timestamp - sunset_timestamp
        
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


#################################################################################################################################################################
#############################################################3#####פונקציות לחישוב לוח עברי######################################################################
################################################################################################################################################################

# מילון לשמות החודשים בעברית
def heb_month_names(number, is_leep=False):
    d={
        1:"תשרי",
        2:"מרחשוון",
        3:"כסלו",
        4:"טבת",
        5:"שבט",
        6:"אדר" if not is_leep else "אדר-א",
        7:"ניסן" if not is_leep else "אדר-ב",
        8:"אייר" if not is_leep else "ניסן",
        9:"סיוון" if not is_leep else "אייר",
        10:"תמוז" if not is_leep else "סיוון",
        11:"אב" if not is_leep else "תמוז",
        12:"אלול" if not is_leep else "אב",
        13:"" if not is_leep else "אלול",}
    return d.get(number)

# מילון לשמות הימים בחודש בעברית
def heb_month_day_names(number):
    d={
        1:"א",
        2:"ב",
        3:"ג",
        4:"ד",
        5:"ה",
        6:"ו",
        7:"ז",
        8:"ח",
        9:"ט",
        10:"י",
        11:"יא",
        12:"יב",
        13:"יג",
        14:"יד",
        15:"טו",
        16:"טז",
        17:"יז",
        18:"יח",
        19:"יט",
        20:"כ",
        21:"כא",
        22:"כב",
        23:"כג",
        24:"כד",
        25:"כה",
        26:"כו",
        27:"כז",
        28:"כח",
        29:"כט",
        30:"ל",}
    return d.get(number)

# מילון לשמות הימים בשבוע בעברית
def heb_weekday_names(number):
    d={
        1:"ראשון",
        2:"שני",
        3:"שלישי",
        4:"רביעי",
        5:"חמישי",
        6:"שישי",
        7:"שבת",}
    return d.get(number)


# מילון למבני השנים האפשריים בלוח העברי לפי מספר ימי השנה נותן את מספר הימים שיש בכל חודש
def get_year_structure(year_length):
    
    # מבני השנים האפשריים
    structures = {
        353: [30, 29, 29, 29, 30, 29, 30, 29, 30, 29, 30, 29],
        354: [30, 29, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29],
        355: [30, 30, 30, 29, 30, 29, 30, 29, 30, 29, 30, 29],
        383: [30, 29, 29, 29, 30, 30, 29, 30, 29, 30, 29, 30, 29],
        384: [30, 29, 30, 29, 30, 30, 29, 30, 29, 30, 29, 30, 29],
        385: [30, 30, 30, 29, 30, 30, 29, 30, 29, 30, 29, 30, 29]
    }
    return structures.get(year_length)

# פונקצייה נורא חשובה שמקבלת קלט של תאריך עברי שממנו רוצים להזיז ימים וקלט של כמה ימים רוצים להזיז וקלט מהו אורך השנה העברית
# ואז היא אומרת לאיזה תאריך הגענו. היא נבנתה רק על ידי צאט גיפיטי על בסיס נתונים שנתתי לו
def move_heb_date(start_day, start_month, year_length, days_to_move):
    # קבלת מבנה השנה
    year_structure = get_year_structure(year_length)
    if not year_structure:
        raise ValueError("אורך השנה לא תקין")

    # האם השנה מעוברת
    is_leep = year_length in [383, 384, 385]

    # חישוב היום החדש
    current_day = start_day
    current_month = start_month

    # הזזה קדימה או אחורה
    while days_to_move != 0:
        days_in_month = year_structure[current_month - 1]
        if days_to_move > 0:  # הזזה קדימה
            remaining_days_in_month = days_in_month - current_day
            if days_to_move <= remaining_days_in_month:
                current_day += days_to_move
                days_to_move = 0
            else:
                days_to_move -= (remaining_days_in_month + 1)
                current_day = 1
                current_month += 1
                if current_month > len(year_structure):  # מעבר לשנה הבאה
                    if days_to_move == 0:  # בדיוק ביום האחרון
                        current_month -= 1
                        current_day = year_structure[current_month - 1]
                    else:
                        raise ValueError("החישוב חרג מגבולות השנה")
        else:  # הזזה אחורה
            if abs(days_to_move) < current_day:
                current_day += days_to_move
                days_to_move = 0
            else:
                days_to_move += current_day
                current_month -= 1
                if current_month < 1:  # מעבר לשנה קודמת
                    raise ValueError("החישוב חרג מגבולות השנה")
                current_day = year_structure[current_month - 1]

    # חישוב שם החודש והיום בעברית
    month_name = heb_month_names(current_month, is_leep)
    day_name = heb_month_day_names(current_day)

    return f"{day_name} {month_name}"




# פונקצייה שמחזירה את התאריך הגרגוריאני שבו יחול פסח בשנה נתונה או את התאריך הגרגוריאני שבו יחול ראש השנה שאחרי פסח של השנה הנתונה
# כברירת מחדל מקבל קלט של שנה לועזית אך יכול לקבל קלט של שנה עברית במספרים אם מגדירים זאת בקריאה לפונקצייה
def get_geus_rosh_hasha_greg(year, from_heb_year = False):

    if from_heb_year:
        A = year
        # הגדרת שנה לועזית המקבילה לשנה העברית שהוזנה
        B = A - 3760

    else:
        B = year
        A = B + 3760

    # אינני יודע מה מייצגות שתי ההגדרות הבאות 

    # איי קטנה נותן מספר בין 0 ל- 18 שממנו יודעים האם השנה העברית פשוטה או מעוברת. אם איי קטנה קטן מ-11 השנה היא פשוטה, ואם גדול מ-12 השנה היא מעוברת
    # בנוסף, ככל שאיי קטנה קרובה יותר למספר 18, זה אומר שפסח רחוק יותר מתקופת ניסן
    a = (12 * A + 17) % 19
    
    # נוסחה לקבל את מספר השנה במחזור השנים הפשוטות והמעוברות לפי איי קטנה
    # לדוגמא אם איי קטנה שווה 10 אז מספר השנה במחזור 19 השנים הוא 1
    shana_bemachzor19 = {10:1,3:2,15:3,8:4,1:5,13:6,6:7,18:8,11:9,4:10,16:11,9:12,2:13,14:14,7:15,0:16,12:17,5:18,17:19}.get(a)

    # בי קטנה מציינת האם השנה היוליאנית המקבילה היא פשוטה (365 יום) או כבושה (366 יום). אם אין שארית, השנה היא כבושה
    b = A % 4

    # נוסחת גאוס בשברים עשרוניים
    nuscha = 32.0440931611436 + (1.5542417966211826) * a + 0.25 * b - (0.0031777940220922675) * A 

    # נוסחת גאוס בשברים פשוטים
    #nuscha = 32 + 4343/98496 + (1 + 272953/492480) * a + 1/4 * b - (313/98496) * A

    # אם גדולה זה השלם של הנוסחה
    # ט"ו בניסן של השנה המבוקשת יחול ביום אם גדולה בחודש מרס
    M = int(nuscha)

    # אם קטנה היא השארית של הנוסחה, והיא חשובה לצורך הדחיות
    m = nuscha - int(nuscha)

    # סי הוא היום בשבוע שבו יחול פסח של השנה המבוקשת. אם סי שווה לאפס הכוונה ליום שבת 7
    c = (M + 3 * A + 5 * b + 5) % 7

    # מידע: דחיית מולד זקן מוכנסת כבר במספר 32 שבנוסחה הראשית

    # חישוב דחיית לא בד"ו פסח שהיא שיקוף של דחיית לא אד"ו ראש
    if c in (2,4,6):
        c = c + 1
        M = M + 1
    # חישוב השפעת דחיית גטר"ד בשנה פשוטה
    elif c == 1 and a > 6 and m >= 0.6329:
        c = c + 2
        M = M + 2
    # חישוב השפעת דחיית בטו תקפט בשנה פשוטה שהיא מוצאי מעוברת
    elif c == 0 and a > 11 and m >= 0.8977:
        c = c + 1
        M = M + 1
    else:
        c = c
        M = M

    # טיפול באם היום בשבוע של פסח יוצא אפס זה אומר יום 7 שזה שבת
    if c == 0:
        c = c + 7

    # אם אם גדולה קטן או שווה לשלושים ואחד פסח יהיה בחודש מרס
    if M <= 31:
        M = M
        chodesh_julyani_pesach = 3 
    # במצב הבא התאריך יהיה בחודש אפריל במקום בחודש מרס
    elif M > 31:
        M = M - 31
        chodesh_julyani_pesach = 4
        
        
    # מעבר ללוח הגרגוריאני
    # חודש מרס הוא תמיד 31 ימים

    if B >= 1582 and B < 1700:
        M = (M + 10) 
    elif B >= 1700 and B < 1800:
        M = (M + 11) 
    elif B >= 1800 and B < 1900:
        M = (M + 12) 
    elif B >= 1900 and B < 2100:
        M = (M + 13) 
    elif B >= 2100 and B < 2200:
        M = (M + 14) 
    elif B >= 2200 and B < 2300:
        M = (M + 15) 
    else:
        M = M

    # אם אם גדולה קטן או שווה לשלושים ואחד פסח יהיה בחודש מרס
    if M <= 31:
        M = M
        chodesh_gregoriani_pesach = chodesh_julyani_pesach

    # במצב הבא התאריך יהיה בחודש אפריל במקום בחודש מרס
    elif M > 31:
        M = M - 31
        chodesh_gregoriani_pesach = chodesh_julyani_pesach + 1

    pesach_greg_day = M
    pesach_greg_month = chodesh_gregoriani_pesach
    pesach_greg_year = B
    pesach_weekday = c
    
    # האם זו שנה עברית מעוברת
    heb_leep_year = shana_bemachzor19 in (3,6,8,11,14,17,19)
    
    #############################################################################################################
    # מציאת התאריך הלועזי של ראש השנה של השנה הבא לאחר הפסח ראו ספר שערים ללוח העברי עמוד 204
    next_rosh_hashana_greg_day = pesach_greg_day + 10
    if pesach_greg_month == 3:
        next_rosh_hashana_greg_month = 8
    elif pesach_greg_month == 4:
        next_rosh_hashana_greg_month = 9
        
    next_rosh_hashana_greg_year = pesach_greg_year
    
    if next_rosh_hashana_greg_day > 31 and pesach_greg_month == 3:
        next_rosh_hashana_greg_day = next_rosh_hashana_greg_day - 31
        next_rosh_hashana_greg_month = 9
    elif next_rosh_hashana_greg_day > 30 and pesach_greg_month == 4:
        next_rosh_hashana_greg_day = next_rosh_hashana_greg_day - 30
        next_rosh_hashana_greg_month = 10
        
    #print(next_rosh_hashana_greg_year, next_rosh_hashana_greg_month, next_rosh_hashana_greg_day)
    ############################################################################################################
    
    return (next_rosh_hashana_greg_year,next_rosh_hashana_greg_month,next_rosh_hashana_greg_day)

    
# פונקצייה שמחשבת כמה ימים עברו מאז ראש השנה העברי ועד היום
# היא ספציפית למיקרופייתון אך יכולה לעבוד בפייתון רגיל עם שינויים מתאימים לקבלת חותמת זמן
# פונקצייה זו משתמשת בפונקציות אחרות שהוגדרו למעלה
def get_days_from_rosh_hashana(greg_year, greg_month, greg_day):
     
    current_year = greg_year
    current_month = greg_month
    current_day = greg_day
    
    # הגדרת חותמת זמן של היום הנוכחי
    current_timestamp = utime.mktime((current_year, current_month, current_day, 0, 0, 0, 0, 0))
    
    # חישוב התאריך הלועזי של ראש השנה והגדרת חותמת זמן שלו
    rosh_hashana_greg = get_geus_rosh_hasha_greg(current_year)
    rosh_hashana_year, rosh_hashana_month, rosh_hashana_day = rosh_hashana_greg
    rosh_hashana_timestamp = utime.mktime((rosh_hashana_year, rosh_hashana_month, rosh_hashana_day, 0, 0, 0, 0, 0))
    
    # אם ראש השנה גדול מהיום הנוכחי כלומר שהוא עוד לא היה סימן שאנחנו צריכים את ראש השנה הקודם ולכן החישוב הוא על השנה הקודמת
    if rosh_hashana_timestamp > current_timestamp:
        # חישוב התאריך הלועזי של ראש השנה והגדרת חותמת זמן שלו
        rosh_hashana_greg = get_geus_rosh_hasha_greg(current_year-1) # הקטנת שנה
        rosh_hashana_year, rosh_hashana_month, rosh_hashana_day = rosh_hashana_greg
        rosh_hashana_timestamp = utime.mktime((rosh_hashana_year, rosh_hashana_month, rosh_hashana_day, 0, 0, 0, 0, 0))

      
    # חישוב ראש השנה הבא אחרי ראש השנה המבוקש
    next_rosh_hashana_greg = get_geus_rosh_hasha_greg(rosh_hashana_year+1) # חישוב ראש השנה הבא לאחר ראש השנה המבוקש 
    next_rosh_hashana_year, next_rosh_hashana_month, next_rosh_hashana_day = next_rosh_hashana_greg
    next_rosh_hashana_timestamp = utime.mktime((next_rosh_hashana_year, next_rosh_hashana_month, next_rosh_hashana_day, 0, 0, 0, 0, 0))

    # חישוב אורך השנה בימים
    length_heb_year_in_seconds = next_rosh_hashana_timestamp - rosh_hashana_timestamp
    length_heb_year_in_days = length_heb_year_in_seconds // (24 * 60 * 60)
    
    # חישוב הפרש הימים בין ראש השנה לבין היום
    days_from_rosh_hashana_in_seconds = current_timestamp - rosh_hashana_timestamp
    days_from_rosh_hashana = days_from_rosh_hashana_in_seconds // (24 * 60 * 60)
 
    rosh_hashana_heb_year_int = rosh_hashana_year + 3761 # זה בכוונה כך ולא 3760 כי מדובר על ראש השנה שחל לפני תחילת השנה הלועזית   
    
    return days_from_rosh_hashana, length_heb_year_in_days, rosh_hashana_heb_year_int

# פונקצייה שמחזירה את התאריך העברי הנוכחי כסטרינג וגם את מספר השנה העברית כאינט בהתבסס על הפונקציות הקודמות
def get_current_heb_date_string(greg_year, greg_month, greg_day):
    days_from_rosh_hashana, length_heb_year_in_days, heb_year_int = get_days_from_rosh_hashana(greg_year, greg_month, greg_day)
    rosh_hashana_day, rosh_hashana_month = 1,1
    return move_heb_date(rosh_hashana_day, rosh_hashana_month, length_heb_year_in_days, days_from_rosh_hashana), heb_year_int
    

################################################################################################################################################################
#################################################################################################################################################################
#################################################################################################################################################################


# כל המיקומים. כל מיקום מוגדר כמילון
# בינתיים ההפרש מיוטיסי עבור מיקומים בחו"ל אינם מחושבים וזה כרגע בכוונה
# המיקום הראשון ברשימה יהיה ברירת המחדל


locations = [
    
    {'heb_name': 'משווה-0-0', 'lat': 0.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'Equals 0-0'} , # קו המשווה בכוונה נמצא פעמיים כדי שבהעברת מיקומים תמיד יראו אותו ראשון
    {'heb_name': 'קו-המשווה', 'lat': 0.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'Equals 0-0'} ,
    {'heb_name': 'הקוטב-הצפוני', 'lat': 90.0, 'long': 0.0, 'altitude': 0.0, 'utc_offset': '', 'name': 'North Pole'} ,
    {'heb_name': 'ניו-יורק-ארהב', 'lat': 40.7143528, 'long': -74.0059731, 'altitude': 9.775694, 'utc_offset': '', 'name': 'New York US'} ,
    {'heb_name': 'אופקים', 'lat': 31.309, 'long': 34.61, 'altitude': 170.0, 'utc_offset': '', 'name': 'Ofakim IL'} ,
    {'heb_name': 'אילת', 'lat': 29.55, 'long': 34.95, 'altitude': 0.0, 'utc_offset': '', 'name': 'Eilat IL'} ,
    {'heb_name': 'אלעד', 'lat': 32.05, 'long': 34.95, 'altitude': 150.0, 'utc_offset': '', 'name': 'Elad IL'} ,
    {'heb_name': 'אמסטרדם-הולנד', 'lat': 52.38108, 'long': 4.88845, 'altitude': 15.0, 'utc_offset': '', 'name': 'Amsterdam NL'} ,
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
    {'heb_name': 'וילנא-ליטא', 'lat': 54.672298, 'long': 25.2697, 'altitude': 112.0, 'utc_offset': '', 'name': 'Vilnius LT'} ,
    {'heb_name': "ז'שוב-פולין", 'lat': 50.0332, 'long': 21.985848, 'altitude': 209.0, 'utc_offset': '', 'name': 'Rzeszow PL'} ,
    {'heb_name': 'זכרון יעקב', 'lat': 32.57, 'long': 34.95, 'altitude': 170.0, 'utc_offset': '', 'name': 'Zichron Yaakov IL'} ,
    {'heb_name': 'חברון', 'lat': 31.53, 'long': 35.09, 'altitude': 950.0, 'utc_offset': '', 'name': 'Hebron IL'} ,
    {'heb_name': 'חדרה', 'lat': 32.43, 'long': 34.92, 'altitude': 53.0, 'utc_offset': '', 'name': 'Hadera IL'} ,
    {'heb_name': 'חיפה', 'lat': 32.8, 'long': 34.991, 'altitude': 300.0, 'utc_offset': '', 'name': 'Haifa IL'} ,
    {'heb_name': 'חרשה', 'lat': 31.944738, 'long': 35.1485598, 'altitude': 760.0, 'utc_offset': '', 'name': 'Harasha'} ,
    {'heb_name': 'טבריה', 'lat': 32.79, 'long': 35.531, 'altitude': 0.0, 'utc_offset': '', 'name': 'Tiberias IL'} ,
    {'heb_name': 'טלזסטון', 'lat': 31.78, 'long': 35.1, 'altitude': 720.0, 'utc_offset': '', 'name': 'Telzstone IL'} ,
    {'heb_name': 'ירוחם', 'lat': 30.99, 'long': 34.91, 'altitude': 0.0, 'utc_offset': '', 'name': 'Yeruham IL'} ,
    {'heb_name': 'ירושלים', 'lat': 31.776812, 'long': 35.235694, 'altitude': 750.0, 'utc_offset': '', 'name': 'Jerusalem IL'} ,
    {'heb_name': 'כרמיאל', 'lat': 32.915, 'long': 35.292, 'altitude': 315.0, 'utc_offset': '', 'name': 'Carmiel IL'} ,
    {'heb_name': 'לוד', 'lat': 31.95, 'long': 34.89, 'altitude': 0.0, 'utc_offset': '', 'name': 'Lod IL'} ,
    {'heb_name': 'לונדון-אנגליה', 'lat': 51.5001524, 'long': -0.1262362, 'altitude': 14.605533, 'utc_offset': '', 'name': 'London GB'} ,
    {'heb_name': 'מגדל-העמק', 'lat': 32.67, 'long': 35.23, 'altitude': 0.0, 'utc_offset': '', 'name': 'Migdal Haemek IL'} ,
    {'heb_name': 'מוסקווה-רוסיה', 'lat': 55.755786, 'long': 37.617633, 'altitude': 151.189835, 'utc_offset': '', 'name': 'Moscow RU'} ,
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
    {'heb_name': "פראג-צ'כיה", 'lat': 50.0878114, 'long': 14.4204598, 'altitude': 191.103485, 'utc_offset': '', 'name': 'Prague CZ'} ,
    {'heb_name': 'פריז-צרפת', 'lat': 48.8566667, 'long': 2.3509871, 'altitude': 0.0, 'utc_offset': '', 'name': 'Paris FR'} ,
    {'heb_name': 'פרנקפורט-גרמניה', 'lat': 50.1115118, 'long': 8.6805059, 'altitude': 106.258285, 'utc_offset': '', 'name': 'Frankfurt DE'} ,
    {'heb_name': 'פתח-תקווה', 'lat': 32.09, 'long': 34.88, 'altitude': 0.0, 'utc_offset': '', 'name': 'Petah Tikva IL'} ,
    {'heb_name': 'צפת', 'lat': 32.962, 'long': 35.496, 'altitude': 850.0, 'utc_offset': '', 'name': 'Zefat IL'} ,
    {'heb_name': 'קהיר-מצרים', 'lat': 30.00022, 'long': 31.231873, 'altitude': 23.0, 'utc_offset': '', 'name': 'Cairo EG'} ,
    {'heb_name': 'קצרין', 'lat': 32.98, 'long': 35.69, 'altitude': 0.0, 'utc_offset': '', 'name': 'Katzrin IL'} ,
    {'heb_name': 'קרית-גת', 'lat': 31.61, 'long': 34.77, 'altitude': 159.0, 'utc_offset': '', 'name': 'Kiryat Gat IL'} ,
    {'heb_name': 'קרית-שמונה', 'lat': 33.2, 'long': 35.56, 'altitude': 0.0, 'utc_offset': '', 'name': 'Kiryat Shmona IL'} ,
    {'heb_name': 'ראש-העין', 'lat': 32.08, 'long': 34.95, 'altitude': 90.0, 'utc_offset': '', 'name': 'Rosh HaAyin IL'} ,
    {'heb_name': 'ראשון-לציון', 'lat': 31.96, 'long': 34.8, 'altitude': 0.0, 'utc_offset': '', 'name': 'Rishon Lezion IL'} ,
    {'heb_name': 'רומא-איטליה', 'lat': 41.8954656, 'long': 12.4823243, 'altitude': 19.704413, 'utc_offset': '', 'name': 'Rome IT'} ,
    {'heb_name': 'רחובות', 'lat': 31.89, 'long': 34.81, 'altitude': 76.0, 'utc_offset': '', 'name': 'Rechovot IL'} ,
    {'heb_name': 'רכסים', 'lat': 32.74, 'long': 35.08, 'altitude': 154.0, 'utc_offset': '', 'name': 'Rechasim IL'} ,
    {'heb_name': 'רמלה', 'lat': 31.92, 'long': 34.86, 'altitude': 0.0, 'utc_offset': '', 'name': 'Ramla IL'} ,
    {'heb_name': 'רמרוג-צרפת רת', 'lat': 48.518606, 'long': 4.3034152, 'altitude': 101.0, 'utc_offset': '', 'name': 'Ramerupt FR'} ,
    {'heb_name': 'רעננה', 'lat': 32.16, 'long': 34.85, 'altitude': 71.0, 'utc_offset': '', 'name': 'Raanana IL'} ,
    {'heb_name': 'שדרות', 'lat': 31.52, 'long': 34.59, 'altitude': 0.0, 'utc_offset': '', 'name': 'Sderot IL'} ,
    {'heb_name': 'תל-אביב-חולון', 'lat': 32.01, 'long': 34.75, 'altitude': 0.0, 'utc_offset': '', 'name': 'Tel Aviv-Holon IL'} ,
    {'heb_name': 'תפרח', 'lat': 31.32, 'long': 34.67, 'altitude': 173.0, 'utc_offset': '', 'name': 'Tifrach IL'} ,
        
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


# הדפסת טקסט במרכז המסך
def center(text, font):
    """
    Centers the given text on the display.
    """
    return tft.width() // 2 - len(text) // 2 * (9 if font==FontHeb20 else 12 if font==FontHeb25 else 10) #font.MAX_WIDTH


esberim = [
    
        ["שעון ההלכה גרסה",f"{VERSION}"],
        ["מאת שמחה גרשון בורר - כוכבים וזמנים",""],
        [reverse("052-7661249 - sgbmzm@gmail.com  "), ""],
        ["כל הזכויות שמורות - להלן הסברים", ""],
        ["כשהשעון מכוון: דיוק הזמנים 01 שניות", ""],
        ["אבל: דיוק גובה הירח סוטה בכדקה", ""],
        
        ["  לחיצה מתמשכת מגדירה מיקום קבוע", ""],

        [" מתחת גרא/מגא:  דקות בשעה זמנית", ""],
        [" מתחת שמש/ירח:  אזימוט שמש/ירח", ""],
        ["אזימוט = מעלות מהצפון, וכדלהלן", ""],
        ["צפון=063/0, מז=09, דר=081, מע=072", ""], # המספרים כתובים בכוונה הפוך כי אחר כך מיישרים אותם ברוורס יחד עם העברית
        
        ["רשימת זמני היום בשעות זמניות", ""],
        
        ["זריחה ושקיעה במישור", "00:00"],
        ["סוף שמע ביום/רבע הלילה", "03:00"],
        ["  סוף תפילה ביום/שליש הלילה", "04:00"],
        ["חצות יום ולילה", "06:00"],
        ["מנחה גדולה", "06:30"],
        ["מנחה קטנה", "09:30"],
        ["פלג המנחה", "10:45"],
        
        ["   זמנים במעלות כשהשמש תחת האופק", ""],
        ["זריחת ושקיעת מרכז השמש", "0.0°"],
        ["  זריחה ושקיעה במישור", "-0.833°"],
        
        ["זמני צאת הכוכבים במעלות", ""],
        ["לפי 4/3 מיל של 81 דקות", "-3.65°"],
        ["לפי 4/3 מיל של 5.22 דקות", "-4.2°"],
        ["לפי 4/3 מיל של 42 דקות", "-4.61°"],
        ["צאת כוכבים קטנים רצופים", "-6.3°"],
        
        ["  מעלות: עלות השחר/צאת הכוכבים דרת", ""],
        ["לפי 4 מיל של 81 דקות", "-16.02°"],
        ["לפי 4 מיל של 5.22 דקות", "-19.75°"],
        ["לפי 5 מיל של 42 דקות", "-25.8°"],
        ["משיכיר/תחילת ציצית ותפילין", "-10.5°"],
        ["מגא מחושב לפי °61- בבוקר ובערב", ""],
        
        ["זמנים נוספים", ""],
        ["להימנע מסעודה בערב שבת", "09:00"],
        ["סוף אכילת חמץ", "04:00"],
        ["סוף שריפת חמץ", "05:00"],

        ["  שלב הירח במסלולו החודשי - באחוזים", ""],
        ["מולד=001/0, ניגוד=05, רבע=57/52", ""],
        ["להלן מאפייני ירח לראייה ראשונה", ""],
        ["מינימום: מסלול לראייה ראשונה: 2%", ""],
        ["וגובה ירח 4°+ כשגובה השמש 4°-", ""],
    
    ]
    


# את השורה הזו צריך להגדיר רק אם רוצים להגדיר ידנית את השעון הפנימי של הבקר וזה בדרך כלל לא יישומי כאן
#machine.RTC().datetime((2025, 3, 26, get_rtc_weekday(4), 10, 59, 0, 0))  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)

# קריאה לפונקצייה שמעדכנת את שעון המכונה לפי שעון כרכיב נלווה ואם יש שגיאה או שהוא לא מחובר מעדכנת זמן אחר
# זה קורה רק פעם בהתחלה ולא כל שנייה מחדש
sync_rtc_with_ds3231()


########################################################################################3
# פונקציה לקרוא את מספר המיקום ברירת מחדל מתוך הקובץ
def read_default_location():
    try:
        with open("default_location.txt", "r") as f:
            return int(f.read().strip())  # קורא וממיר למספר שלם
    except:
        return 0  # אם יש שגיאה, ברירת מחדל תהיה 0

# הגדרת משתנה גלובלי חשוב מאוד שקובע מה המיקום הנוכחי שעליו מתבצעים החישובים
# משתנה זה נקבע לפי המיקום האינדקסי ששמור בקובץ מיקום ברירת מחדל תוך בדיקה שהאינדקס לא חורג מגבולות הרשימה ואם כן חורג אז יוגדר המיקום האפס כברירת מחדל
# קריאת המיקום מתוך הרשימה בהתאם למספר שבקובץ
default_index = read_default_location()
location = locations[default_index] if 0 <= default_index < len(locations) else locations[0] 



##############################################################################################


# משתנה לשליטה על איזה נתונים יוצגו במסך בכל שנייה
current_screen = 0.0  # 




# הפונקצייה הראשית שבסוף גם מפעילה את הנתונים על המסך
def main():
    
    ###########################################################################################
    # הגדרות מאוד חשובות על איזה זמן יתבצעו החישובים
    # כרגע השעון של הבקר הוא שעון ישראל ואני ממיר את זה ליוטיסי ומשם לזמן מקומי והכל בחותמות זמן באמצעות פונקצייה שהוגדרה לעיל
    # בעתיד אולי שעון המכונה יהיה יוטיסי ואז יצטרכו לשנות בהתאם.
    # גם צריך לטפל ב אר.טי.סי. החיצוני שאולי הוא יהיה באיזור זמן יוטיסי
    rtc_system_timestamp =  time.time() # או: utime.mktime(utime.localtime())
    is_location_dst = True if is_now_israel_DST() else False # כרגע כל שעון הקיץ או לא שעון קיץ נקבע לפי החוק בישראל גם עבור מקומות אחרים
    israel_offset_seconds = get_generic_utc_offset(35, dst=is_location_dst, in_seconds = True) # ישראל זה קו אורך 35
    current_utc_timestamp = rtc_system_timestamp - israel_offset_seconds # כי ישראל היא אחרי יוטיסי
    location_offset_hours = get_generic_utc_offset(location["long"], dst=is_location_dst)
    location_offset_seconds = get_generic_utc_offset(location["long"], dst=is_location_dst, in_seconds = True)
    current_location_timestamp = current_utc_timestamp + location_offset_seconds
    # עכשיו הגענו לנתון הכי חשוב שהוא חותמת הזמן המקומית הנוכחית
    current_timestamp = current_location_timestamp
    
    ##############################################################################################
    
    
    
    # משתנה ששולט על חישוב גובה השמש במעלות לשיטת המג"א ונועד במקור לחישוב דמדומים
    # אם כותבים 16 זה אומר מינוס 16
    # אם רוצים פלוס אז אולי צריך לעשות +16 אבל לא יודע אם זה יעבוד
    # אם עושים None או False או 0 זה לא מחושב כלל ולכן אם רוצים כאן זריחה גיאומטרית חייבים להגדיר 0.00001
    MGA_deg = 16 # אם רוצים ששעות זמניות לא יחושבו בכלל לפי המג"א צריך לעשות None או False או 0 ולכן אם רוצים גרא גיאומטרי חייבים לעשות 0.0001
    
    # הצהרה על משתנים גלובליים ששומרים את הזמנים הדרושים
    global sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise
    
    # ריקון כל המשתנים כדי שלא ישתמשו בנתונים לא נכונים
    sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
    
        
    # יצירת אובייקט RiSet
    RiSet.tim = round(current_location_timestamp) ############### אם לא מגדירים את זה אז הזמן הוא לפי הזמן הפנימי של הבקר
    #RiSet.sinho_sun_riset = 0.0 # אם רוצים שזריחה ושקיעה של השמש יהיו לפי זריחה ושקיעה גיאומטריים ולא לפי מינוס 0.833. אם לא מגדירים אז כברירת מחדל יהיה 0.833 מינוס
    riset = RiSet(lat=location["lat"], long=location["long"], lto=location_offset_hours, tl=MGA_deg) # lto=location_offset_hours
    
    
    # שמירת כל הנתונים על היום הנוכחי כי כולם נוצרים ביחד בעת הגדרת "riset" או בעת שמשנים לו יום
    sunrise, sunset, mga_sunrise, mga_sunset = riset.sunrise(1), riset.sunset(1), riset.tstart(1), riset.tend(1)
    
    
    # הגדרת הזמן הנוכחי המקומי מחותמת זמן לזמן רגיל
    tm = utime.localtime(current_location_timestamp)
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
    
     
    # אם מדובר אחרי 12 בלילה ולפני הזריחה ויודעים את זה לפי ששעת הזריחה מאוחרת מהרגע הנוכחי לפי אחת משתי השיטות ההלכתיות
    # מגדרים את יום האתמול ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום האתמול    
    
    # כל החישובים נעשים רק אם יש זריחה כי אולי במיקום הזה אין בכלל זריחה ביום זה
    if sunrise:
        
        if (current_timestamp < sunrise) or (MGA_deg and current_timestamp < mga_sunrise):
            riset.set_day(-1)
            yesterday_sunset, mga_yesterday_sunset = riset.sunset(1), riset.tend(1) if MGA_deg else None
            tomorrow_sunrise, mga_tomorrow_sunrise = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
            
        # אם מדובר אחרי השקיעה לפי אחת השיטות ולפני השעה 12 בלילה
        # מגדרים את יום המחר ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום המחר
        elif (current_timestamp > sunrise and current_timestamp >= sunset) or (MGA_deg and current_timestamp > mga_sunrise and current_timestamp >= mga_sunset):
            riset.set_day(1)
            tomorrow_sunrise, mga_tomorrow_sunrise  = riset.sunrise(1), riset.tstart(1) if MGA_deg else None, 
            yesterday_sunset, mga_yesterday_sunset = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
        
    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        sunrise_timestamp, sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = True)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        temporal_time, seconds_in_temporal_hour = calculate_temporal_time(current_timestamp, sunrise_timestamp, sunset_timestamp)
        minutes_in_temporal_hour = str(round(seconds_in_temporal_hour / 60)) # str(convert_seconds(seconds_in_temporal_hour))
             
    else:
        
        temporal_time = reverse("שגיאה  ")
        minutes_in_temporal_hour = ""
        
    
    # רק אם רוצים ואפשר לחשב זריחות ושקיעות לפי מגן אברהם
    if MGA_deg:
        
        # רק אם השמש מגיעה לגובה זה כי אולי במיקום הזה היא לא מגיעה כרגע לגובה זה
        if mga_sunrise:
    
            # חישוב מחדש עבור שיטת מגן אברהם    
            # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
            mga_sunrise_timestamp, mga_sunset_timestamp = get_sunrise_sunset_timestamps(current_timestamp, is_gra = False)
             
            # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
            mga_temporal_time, seconds_in_mga_temporal_hour = calculate_temporal_time(current_timestamp, mga_sunrise_timestamp, mga_sunset_timestamp)
            minutes_in_mga_temporal_hour = str(round(seconds_in_mga_temporal_hour / 60)) # str(convert_seconds(seconds_in_mga_temporal_hour))
        else:
            
            mga_temporal_time = reverse("שגיאה  ")
            minutes_in_mga_temporal_hour = ""


    # חישובים שלב הירח הנוכחי. בעתיד לסדר לזה tim
    mp = MoonPhase()  # datum is midnight last night
    phase = mp.phase()
    #phase_percent = (phase / 0.5) * 100 if phase <= 0.5 else ((1 - phase) / 0.5) * 100
    phase_percent = round(mp.phase() * 100,1)
                    
    ###############################################################
    # מכאן והלאה ההדפסות למסך
    
    # קרירת המתח שהמכשיר מקבל
    voltage = read_battery_voltage()
    voltage_string = f"{round(voltage,1)}v"
    
    greg_date_string = "{:02d}/{:02d}/{:04d}".format(day, month, year)
    time_string = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
    
    # חישוב תאריך עברי נוכחי באמצעות פונקצייה שהוגדרה לעיל
    heb_date, heb_year_int = get_current_heb_date_string(year, month, day)
    heb_year_string = gematria_pyluach._num_to_str(heb_year_int, thousands=False, withgershayim=False)
    hebrew_weekday = heb_weekday_names(get_normal_weekday(rtc_week_day))
    # מוצאי יום עברי מוגדר משעת השקיעה עד השעה 11:59 של אותה יממה של השקיעה שבזמן זה התאריך הלועזי והעברי אינם שווים. וזה רק כשיש שקיעה
    motsaei = reverse("מוצאי: ") if sunset and current_timestamp > sunset and (current_timestamp // 86400 == sunset_timestamp // 86400) else "" # מספר השניות ביממה הוא 86400
    heb_date_string = f'{reverse(heb_year_string)} {reverse(heb_date)} ,{reverse(hebrew_weekday)}{motsaei}'
    magrab_time = calculate_magrab_time(current_timestamp, sunset_timestamp) if sunrise else reverse("שגיאה  ") # רק אם יש זריחה ושקיעה אפשר לחשב
    utc_offset_string = 'utc+0' if location_offset_hours == 0 else f'utc+{location_offset_hours}' if location_offset_hours >0 else "utc"+str(location_offset_hours)
    #coteret = f'{reverse(location["heb_name"])} - {reverse("השעון ההלכתי")}'
    coteret = f'  {voltage_string} - {reverse(location["heb_name"])} - {reverse("שעון ההלכה")}'
    
    tft.fill(0) # מחיקת המסך
    tft.write(FontHeb20,f'{coteret}',center(coteret,FontHeb20),0, s3lcd.GREEN, s3lcd.BLACK) #fg=s3lcd.WHITE, bg=s3lcd.BLACK בכוונה מוגדר אחרי השורה הקודמת בגלל הרקע הצהוב
    tft.write(FontHeb25,f'{heb_date_string}',center(heb_date_string,FontHeb25),20)
    tft.line(0, 45, 320, 45, s3lcd.YELLOW) # קו הפרדה
    tft.write(FontHeb20,f'                 {reverse("מגא")}                         {reverse("גרא")}',0,47)
    tft.write(FontHeb20,f'                  {minutes_in_mga_temporal_hour}                           {minutes_in_temporal_hour}',0,62, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb40,f'{temporal_time}', 140, 45, s3lcd.GREEN, s3lcd.BLACK)
    tft.line(20, 45, 300, 45, s3lcd.YELLOW) # קו הפרדה
    if MGA_deg:
        tft.write(FontHeb25,f' {mga_temporal_time}', 0, 52, s3lcd.GREEN, s3lcd.BLACK)
    tft.write(FontHeb20,f'                 {reverse("ירח")}                         {reverse("שמש")}',0,82)
    tft.write(FontHeb20,f'{round(m_az)}°', 100,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb20,f'{round(s_az)}°', 281,100, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb25,f' {" " if m_alt > 0 else ""}{" " if abs(m_alt) <10 else ""}{m_alt:.3f}°',0,80, s3lcd.GREEN, s3lcd.BLACK)
    #tft.write(FontHeb20,f'{phase_percent:.1f}% :{reverse("שלב")}',0,101, s3lcd.MAGENTA, s3lcd.BLACK)
    tft.write(FontHeb20,f'    {phase_percent:.1f}%',0,101, s3lcd.CYAN, s3lcd.BLACK)
    tft.write(FontHeb40,f"{" " if s_alt > 0 else ""}{" " if abs(s_alt) <10 else ""}{round(s_alt,3):.3f}°", 135, 83, s3lcd.GREEN, s3lcd.BLACK)
    #tft.write(FontHeb20,f'                 :{reverse("שעון מהשקיעה )אי/מגרב(")}',0,123) #    {riset.sunset(2)} :{reverse("שקיעה")}    
    #tft.write(FontHeb25,f' {magrab_time}',0,120, s3lcd.GREEN, s3lcd.BLACK) #
    
    # שורת הסברים מתחלפת
    text = reverse(esberim[int(current_screen)][0])  # רוורס של הטקסט העברי
    time_value = esberim[int(current_screen)][1]  # הערך להצגה
    CCC = f"{time_value}  :{text}" if time_value != "" else f"{text}"
    tft.write(FontHeb20, f"{CCC}" ,center(CCC, FontHeb20) , 123)  # כתיבה למסך
         
    tft.write(FontHeb25,f' {greg_date_string}                  {utc_offset_string}',0,147)
    tft.write(FontHeb30,f'{time_string}', 133, 145, s3lcd.GREEN, s3lcd.BLACK)
    tft.line(0, 145, 320, 145, s3lcd.YELLOW) # קו הפרדה
    tft.line(0, 120, 320, 120, s3lcd.YELLOW) # קו הפרדה
    
    # ציור מסגרת לירח שני הקווים הבאים
    tft.line(0, 80, 320, 80, s3lcd.YELLOW) # קו הפרדה
    #tft.line(135, 80, 135, 120, s3lcd.YELLOW) # קו הפרדה
    
    
    tft.show() # כדי להציג את הנתונים על המסך
    
    
    
    
    ################################################################################



# אינדקס המיקום הנוכחי משתנה גלובלי חשוב מאוד
location_index = 0

# פונקצייה לשמירת המיקום האינדקסי של המיקום הנוכחי לקובץ מיקום ברירת מחדל כדי שזה המיקום שייפתח בפעם הראשונה שנכנסים לתוכנה
def save_default_location(index):
    """ שומר את המיקום הנוכחי בקובץ """
    try:
        with open("default_location.txt", "w") as f:
            f.write(str(index))
    except Exception as e:
        print("שגיאה בשמירת המיקום:", e)

############################################################################################33
        
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
    
    # הכרזה על משתנים גלובליים שיטופלו בלחיצה על הכפתור
    global location_index
    global location
    
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
        tft.write(FontHeb25,f'{reverse(locations[location_index]["heb_name"])}',130,100)
        tft.show() # כדי להציג את הנתונים על המסך
        time.sleep(5) # השהייה 5 שניות כדי שיהיה זמן לראות את ההודעה לפני שהמסך ייתמלא שוב בחישובים
        
       

# חיבור הכפתור לפונקציה
boot_button.irq(trigger=Pin.IRQ_FALLING, handler=toggle_location)




######################################################################################################




# משתנה לזמן הקריאה האחרונה
last_read_time = time.time()


# הגדרת הפינים שצריך לכבות כדי שהמסך ייכבה והמכשיר יהיה בצריכת חשמל נמוכה
LCD_POWER = Pin(15, Pin.OUT)
RD = Pin(9, Pin.OUT)
# לאחר מכן להפעיל PWM כדי לשלוט במידת התאורה האחורית של המסך
BACKLIGHT = PWM(Pin(38, Pin.OUT), freq=1000)
PWM_MAX = 1023 # תאורה הכי גבוהה
PWM_MIN = 0 # התאורה כבוייה


# לולאת רענון שחוזרת על עצמה כל הזמן והיא זו שמפעילה את הפונקצייה הראשית כל שנייה מחדש
while True:
    
    # אם כפתור הפעלת החישובים פועל אז מפעילים את המסך ואת הכוח ואת החישובים וחוזרים עליהם שוב ושוב
    if power_state:
        
        # כל שעה צריך לקרוא מחדש את השעה כי השעון הפנימי של הבקר עצמו לא מדוייק מספיק
        # בדיקה אם עברה שעה (3600 שניות)
        if time.time() - last_read_time >= 3600:
            sync_rtc_with_ds3231()
            # עדכון זמן הקריאה האחרונה
            last_read_time = time.time()
       
        # קריאת המתח של החשמל ולפי זה קביעת רמת התאורה האחורית של המסך כדי לחסוך בצריכת חשמל וכן הדלקת רכיבים נוספים שקשורים למסך ולכוח
        voltage = read_battery_voltage()
        # אם המתח מעל 4.6 וולט והמשתמש רוצה בהירות מקס כפי שהוגדר בתחילת הקוד אז הבהירות הכי גבוהה
        # אם המשתמש לא הגדיר בתחילת הקוד בהירות הכי גבוהה אז הבהירות תהיה בינונית אם המתח גדול מ 4.6 כלומר שלא מחובר רק לסוללה הפנימית
        # בכל מקרה אחר מחובר רק לסוללה הפנימית או גם אם לחיצונית אבל היא חלשה הכוח הוא 255 שזה רבע בהירות, כדי לחסוך בחשמל
        duty_for_backligth = PWM_MAX if (voltage >= 4.6 and behirut_max) else 450 if voltage > 4.6 else 255
        BACKLIGHT.duty(duty_for_backligth)
        RD.value(1)
        LCD_POWER.value(1)
        
        # הפעלת הפונקצייה הראשית והשהייה קטנה לפני שחוזרים עליה שוב
        main()
        current_screen = (current_screen + 0.25) % len(esberim)  # זה גורם מחזור של שניות לאיזה נתונים יוצגו במסך
        time.sleep(0.825)  # רענון כל שנייה אבל צריך לכוון את זה לפי כמה כבד הקוד עד שהתצוגה בפועל תתעדכן כל שנייה ולא יותר ולא בפחות
        gc.collect() # ניקוי הזיכרון חשוב נורא כדי למנוע קריסות
        
    # אם הכוח לא פועל אז יש לכבות הכל
    else:
        
        # ב S3 ליליגו עובד רק על כפתור 14 ולא על כפתור בוט שהוא אפס
        wake1 = Pin(14, Pin.IN, Pin.PULL_UP)
        
        # הגדרת כפתור ההשכמה מהשינה העמוקה
        #level parameter can be: esp32.WAKEUP_ANY_HIGH or esp32.WAKEUP_ALL_LOW
        esp32.wake_on_ext0(pin = wake1, level = esp32.WAKEUP_ALL_LOW)
       
        # הדפסה למסך
        tft.fill(0) # מחיקת המסך
        tft.write(FontHeb25,f'{reverse("בתהליך כניסה למצב שינה...")}',30,75)
        tft.show() # כדי להציג את הנתונים על המסך
        time.sleep(3) # השהייה 5 שניות כדי שיהיה זמן לראות את ההודעה לפני שהמסך ייתמלא שוב בחישובים
        tft.fill(0) # מחיקת המסך
        tft.show() # כדי להציג את הנתונים על המסך
        # כיבוי הכוח והתאורה וכל מה שקשור למסך.
        # כנראה לי שזה לא הכרחי ולא מקטין את צריכת החשמל יותר מאשר המצב בשניה עמוקה רגילה.
        BACKLIGHT.duty(PWM_MIN)
        RD.value(0)
        LCD_POWER.value(0)
        
        # מצב שינה. היציאה ממצב שינה מתבצעת באמצעות לחיצה על הכפתור שמעיר את המכשיר וקורא שוב למיין שקורא שוב למיין שמש
        machine.deepsleep()

            

    ##########################################################################################################################








