# קוד נורא חשוב לחישובי שמש וירח במיקרופייתון

# https://github.com/peterhinch/micropython-samples/issues/42
# https://github.com/peterhinch/micropython-samples/tree/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy
# https://github.com/peterhinch/micropython-samples/blob/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy/sun_moon.py
# https://github.com/peterhinch/micropython-samples/blob/d2929df1b4556e71fcfd7d83afd9cf3ffd98fdac/astronomy/moonphase.py



# למה בניו יורק יש בעיה עם שעה זמנית מגן אברהם???????????????????????????????????????????????????????????????????????????????????????????
# בדקתי חלקית והבעיה נגרמת בגלל בעיה בפונקציית get_sunrise_sunset_timestamps אבל לא ברור לי למה זה הולך לאחרי השקיעה ולפני 12 בלילה בשעה שבאמת יום



# צריך לחשוב איך לגרום שהשעון יהיה מוגדר אוטומטית לשעון קיץ בתאריכים המתאימים.


import time, math, machine, utime
#import datetime as dt
from sun_moon import RiSet  # יבוא הספרייה
from machine import I2C, Pin
#from ssd1306 import SSD1306_I2C  # ספריית OLED
from ds3231 import DS3231

# למסך
import vga1_bold_16x32 as Font16B
#import vga1_8x8 as font
import miriam40 as FontHeb40
import miriam20 as FontHeb20
import miriam30 as FontHeb30
import tft_config
import s3lcd

# הגדרת המסך
tft = tft_config.config(tft_config.WIDE)
tft.init()



#########################################

# פונקצייה לקבלת הפרש השעות המקומי מגריניץ בלי התחשבות בשעון קיץ
def get_generic_utc_offset(longitude_degrees):
    return abs(round(longitude_degrees/15)) % 24

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
        
        ################################################################################################
        # כל החלק הזה קשור לאופצייה של עדכון השעון הפנימי שבדרך כלל לא מתבצעת
        
        # ברירת המחדל היא לא לעדכן את השעון החיצוני
        # ואם הבקר לא מחובר למחשב אסור לעדכן את השעון החיצוני לפי השעון הפנימי
        # רק אם הבקר מחובר למחשב אפשר לעדכן את השעון החיצוני לפי שעון המחשב אם רוצים
        # גם זה לא מומלץ כי יתן שעון קיץ בקיץ וכדאי לשמור את השעון החיצוני על שעון חורף
        update_rtc_ds3231 = False # False or True  
        update_rtc_ds3231_from_computer = False # False or True  
        
        if update_rtc_ds3231:
            
            if update_rtc_ds3231_from_computer:
            
                # קריאת זמן המערכת של הבקר שזה הזמן המדוייק של המחשב רק כאשר הבקר מחובר למחשב
                year, month, day, week_day, hour, minute, second, micro_second = rtc.datetime()
                # חייבים למפות מחדש את סדר הנתונים וצורתם כי כל ספרייה משתמשת בסדר וצורה אחרים קצת
                new_time = (year, month, day, hour, minute, second, get_normal_weekday(week_day))
            
            else:
                
                # כאן אפשר לבחור לבד איזה נתונים לכוון לשעון החיצוני
                year, month, day, hour, minute, second, weekday = 1988, 2, 24, 18, 45, 56, 1 # 1 = sunday                
                new_time = (year, month, day, hour, minute, second, weekday)


            print("השעה בשעון החיצוני לפני העדכון", rtc_ds3231.datetime())
            
            # עדכון הזמן ב-RTC
            rtc_ds3231.datetime(new_time)

            print("הזמן בשעון החיצוני עודכן בהצלחה השעה לאחר העדכון היא", rtc_ds3231.datetime())

        ###################################################################################################################    
        
        # קריאת הזמן מ-DS3231
        ds3231_time = rtc_ds3231.datetime()

        # עדכון ה-machine RTC עם הזמן שנקרא מ-DS3231
        rtc_system.datetime(ds3231_time)
        print("Time synced with DS3231: ", ds3231_time)
        
        # כיבוי החשמל החיובי שהולך לשעון החיצוני כי כבר לא צריך אותו
        # זה לא חובה
        ds3231_plus.value(0)

    except Exception as e:
        print("Error reading from DS3231: ", e)
        #במקרה של שגיאה, נגדיר זמן ידני ב-machine.RTC()
        manual_time = (2024, 12, 20, get_rtc_weekday(6), 16, 39, 0, 0)  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)
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
        seconds_per_hour_in_day_or_night = day_or_night_length_seconds / 12
        
        # חישוב כמה שניות עברו מאז הזריחה או השקיעה עד הזמן הנוכחי 
        time_since_last_sunrise_or_sunset = timestamp - (sunrise_timestamp if is_day else sunset_timestamp)
        
        # המרת השניות לפורמט שעות, דקות ושניות
        A = (time_since_last_sunrise_or_sunset / seconds_per_hour_in_day_or_night) + 0.0000001
        zmanit_hour = int(A)
        B = ((A - zmanit_hour) * 60) + 0.0000001
        zmanit_minute = int(B)
        C = ((B - zmanit_minute) * 60) + 0.0000001
        zmanit_second = int(C)

        # הדפסת השעה הזמנית המתאימה בפורמט שעות:דקות:שניות
        temporal_time = f'{zmanit_hour:02.0f}:{zmanit_minute:02.0f}:{zmanit_second:02.0f}'
        
        return temporal_time

##############################################################################################################        
# הגדרת שמות עבור משתנים גלובליים ששומרים את כל הזמנים הדרושים לחישובים
sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise = [None] * 8
##############################################################################################################    

def get_sunrise_sunset_timestamps(rtc_timestamp, is_gra = True):
    
    # הצהרה על משתנים גלובליים ששומרים את הזמנים הדרושים
    global sunrise, sunset, mga_sunrise, mga_sunset, yesterday_sunset, mga_yesterday_sunset, tomorrow_sunrise, mga_tomorrow_sunrise
    
    #  חותמת זמן של רגע הזריחה והשקיעה היום
    # חוממת זמן של תחילת וסוף הדמדומים של מגן אברהם כרגע מוגדר לעיל מינוס 16
    sunrise_timestamp = sunrise if is_gra else mga_sunrise
    sunset_timestamp = sunset if is_gra else mga_sunset
           
    # בדיקה האם זה יום לפי בדיקה האם הזמן הנוכחי גדול משעת הזריחה וקטן משעת השקיעה
    is_day = rtc_timestamp >= sunrise_timestamp and rtc_timestamp < sunset_timestamp 
    
    #print("is_gra", is_gra)
    #print("is_day", is_day)
    
    if is_day:
        
        return sunrise_timestamp, sunset_timestamp
                
    else:
        # אם מדובר אחרי 12 בלילה ולפני הזריחה
        if rtc_timestamp < sunrise_timestamp:
            
            # הגדרת הזמן על אתמול וחישוב השקיעה של אתמול
            yesterday_sunset_timestamp = yesterday_sunset if is_gra else mga_yesterday_sunset
        
            return sunrise_timestamp, yesterday_sunset_timestamp
            
            
        # אם מדובר אחרי השקיעה ולפני השעה 12 בלילה
        elif (rtc_timestamp > sunrise_timestamp) and (rtc_timestamp >= sunset_timestamp):
            
            # הגדרת הזמן על מחר וחישוב הזריחה של מחר
            tomorrow_sunrise_timestamp = tomorrow_sunrise if is_gra else mga_tomorrow_sunrise
            
            return tomorrow_sunrise_timestamp, sunset_timestamp


############################################################################################################################
############################################פונקציות לחישוב לוח עברי#########################################################
############################################################################################################################

# מילון לשמות החודשים בעברית
def heb_month_names(number, is_leep=False):
    d={
        1:"תשרי",
        2:"חשוון",
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
def get_days_from_rosh_hashana():
    
    # קבלת התאריך הלועזי הנוכחי    
    current_date = rtc.datetime()
    
    current_year = current_date[0]
    current_month = current_date[1]
    current_day = current_date[2]
    
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
    
    #print(rosh_hashana_greg) 
    #print(next_rosh_hashana_greg) 
    #print(days_from_rosh_hashana)
    #print(length_heb_year_in_days)
    
    return days_from_rosh_hashana, length_heb_year_in_days

def get_current_heb_date_string():
    days_from_rosh_hashana, length_heb_year_in_days = get_days_from_rosh_hashana()
    rosh_hashana_day, rosh_hashana_month = 1,1
    return move_heb_date(rosh_hashana_day, rosh_hashana_month, length_heb_year_in_days, days_from_rosh_hashana)
    

############################################################################################################################
############################################################################################################################
############################################################################################################################



# הגדרת RTC השעון של המיקרו בקר
rtc = machine.RTC()

# את השורה הזו צריך להגדיר רק אם רוצים להגדיר ידנית את השעון הפנימי של הבקר וזה בדרך כלל לא יישומי כאן
#rtc.datetime((2025, 3, 26, get_rtc_weekday(4), 10, 59, 0, 0))  # (שנה, חודש, יום, יום בשבוע, שעה, דקות, שניות, תת-שניות)

# קריאה לפונקצייה שמעדכנת את שעון המכונה לפי שעון כרכיב נלווה ואם יש שגיאה או שהוא לא מחובר מעדכנת זמן אחר
# זה קורה רק פעם בהתחלה ולא כל שנייה מחדש
sync_rtc_with_ds3231()

# כל המיקומים. כל מיקום מוגדר כמילון
# בינתיים ההפרש מיוטיסי עבור מיקומים בחו"ל אינם מחושבים וזה כרגע בכוונה
# המיקום הראשון ברשימה יהיה ברירת המחדל


locations = [
    {"name": "modiin-illit", "heb_name": "מודיעין עילית", "lat": 31.940826, "long": 35.037057, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "jerusalem", "heb_name": "ירושלים", "lat": 31.776812, "long": 35.235694, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "bnei_brak", "heb_name": "בני ברק", "lat": 32.083156, "long": 34.832722, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "equator", "heb_name": "קו-המשווה", "lat": 0, "long": 0, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "new_york", "heb_name": "ניו-יורק", "lat": 40.7143528, "long": -74.0059731, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "london", "heb_name": "לונדון", "lat": 51.5001524, "long": -0.1262362, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "vilna", "heb_name": "וילנא", "lat": 54.672298, "long": 25.2697, "utc_offset": 3 if is_now_israel_DST() else 2},
    {"name": "north_pole", "heb_name": "הקוטב הצפוני", "lat": 89.99, "long": 0, "utc_offset": 3 if is_now_israel_DST() else 2}, # בעיה בספרייה גורמת שיש שגיאה אם מחשבים 90 מעלות. הבעיה לא קורית במחשב
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

# מיקום ברירת המחדל הוא הראשון ברשימת המיקומים
location = locations[0]

#location = {"name": "new_york", "heb_name": "ניו-יורק", "lat": 40.7143528, "long": -74.0059731, "utc_offset": 3 if is_now_israel_DST() else 2}

# משתנה לשליטה על איזה נתונים יוצגו במסך בכל שנייה
current_screen = 0  # 
    

# תצוגה על מסך OLED
def main():
    
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
    riset = RiSet(lat=location["lat"], long=location["long"], lto=location["utc_offset"], tl=MGA_deg)
    
    # שמירת כל הנתונים על היום הנוכחי כי כולם נוצרים ביחד בעת הגדרת "riset" או בעת שמשנים לו יום
    sunrise, sunset, mga_sunrise, mga_sunset = riset.sunrise(1), riset.sunset(1), riset.tstart(1), riset.tend(1)
   
        
    # קבלת הזמן הנוכחי מהמכשיר
    year, month, day, rtc_week_day, hour, minute, second, micro_second = rtc.datetime()
    
    # חישוב מה השעה הנוכחית בשבר עשרוני
    current_hour = (hour + (minute / 60) + (second / 3600)) - location["utc_offset"]
    
    # חישוב גובה השמש והירח ברגע זה כלומר שעה נוכחית בשבר עשרוני
    # לדעת את גובה השמש והירח אפשר גם במיקום שאין בו זריחות ושקיאות וזה לא מחזיר שגיאה
    altitude = math.degrees(math.asin(riset.sin_alt(current_hour, sun=True)))
    m_altitude = math.degrees(math.asin(riset.sin_alt(current_hour, sun=False)))
    
    # חותמת זמן של הרגע
    rtc_timestamp = utime.mktime(utime.localtime())
    
     
    # אם מדובר אחרי 12 בלילה ולפני הזריחה ויודעים את זה לפי ששעת הזריחה מאוחרת מהרגע הנוכחי לפי אחת משתי השיטות ההלכתיות
    # מגדרים את יום האתמול ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום האתמול    
    
    # כל החישובים נעשים רק אם יש זריחה כי אולי במיקום הזה אין בכלל זריחה ביום זה
    if sunrise:
        
        if (rtc_timestamp < sunrise) or (MGA_deg and rtc_timestamp < mga_sunrise):
            riset.set_day(-1)
            yesterday_sunset, mga_yesterday_sunset = riset.sunset(1), riset.tend(1) if MGA_deg else None
            tomorrow_sunrise, mga_tomorrow_sunrise = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
            
        # אם מדובר אחרי השקיעה לפי אחת השיטות ולפני השעה 12 בלילה
        # מגדרים את יום המחר ושומרים את כל הנתונים הדרושים עכשיו או בעתיד על יום המחר
        elif (rtc_timestamp > sunrise and rtc_timestamp >= sunset) or (MGA_deg and rtc_timestamp > mga_sunrise and rtc_timestamp >= mga_sunset):
            riset.set_day(1)
            tomorrow_sunrise, mga_tomorrow_sunrise  = riset.sunrise(1), riset.tstart(1) if MGA_deg else None, 
            yesterday_sunset, mga_yesterday_sunset = None, None # לא חייבים את זה אבל זה מוסיף לביטחות שלא יתבצעו חישובים על נתונים לא נכונים
        
    
        # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
        sunrise_timestamp, sunset_timestamp = get_sunrise_sunset_timestamps(rtc_timestamp, is_gra = True)
         
        # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
        temporal_time = calculate_temporal_time(rtc_timestamp, sunrise_timestamp, sunset_timestamp)
             
    else:
        
        temporal_time = "Eror"
        
    
    # רק אם רוצים ואפשר לחשב זריחות ושקיעות לפי מגן אברהם
    if MGA_deg:
        
        # רק אם השמש מגיעה לגובה זה כי אולי במיקום הזה היא לא מגיעה כרגע לגובה זה
        if mga_sunrise:
    
            # חישוב מחדש עבור שיטת מגן אברהם    
            # חישוב מה הם הזריחה והשקיעה הקובעים את השעון של שעה זמנית באמצעות פונקצייה שהוגדרה למעלה    
            mga_sunrise_timestamp, mga_sunset_timestamp = get_sunrise_sunset_timestamps(rtc_timestamp, is_gra = False)
             
            # חישוב שעון שעה זמנית על הזריחה והשקיעה באמצעות פונקצייה שהוגדרה למעלה
            mga_temporal_time = calculate_temporal_time(rtc_timestamp, mga_sunrise_timestamp, mga_sunset_timestamp)
            
        else:
            
            mga_temporal_time = "Eror"
            
            
    ###############################################################
    # חישוב התאריך העברי הנוכחי באמצעות פונקציות שהוגדרו לעיל        
    
    ################################################################
        
    
        
    # הצגת נתונים על מסך OLED
    tft.fill(0) # מחיקת המסך
    greg_date_string = "{:02d}/{:02d}/{:04d}".format(day, month, year)
    time_string = "{:02d}:{:02d}:{:02d}".format(hour, minute, second)
    
    # חישוב תאריך עברי נוכחי באמצעות פונקצייה שהוגדרה לעיל
    heb_date = get_current_heb_date_string()
    hebrew_weekday = heb_weekday_names(get_normal_weekday(rtc_week_day))
    all_date_string = f'{reverse("התשפה")} {reverse(heb_date)} - {reverse(hebrew_weekday)}'
    
    utc_offset_string = 'utc' if location["utc_offset"] == 0 else f'utc+{location["utc_offset"]}' if location["utc_offset"] >0 else "utc"+str(location["utc_offset"])
    tft.write(FontHeb20,f'{reverse(location["heb_name"])}',100,0, s3lcd.BLACK, s3lcd.YELLOW) #fg=s3lcd.WHITE, bg=s3lcd.BLACK בכוונה מוגדר אחרי השורה הקודמת בגלל הרקע הצהוב
    tft.write(FontHeb20,f'{all_date_string}',50,20)
    tft.write(FontHeb20,f' {mga_temporal_time} :{reverse("מגא")}                           :{reverse("גרא")}',0,50)
    tft.write(FontHeb40,f'{temporal_time}', 127, 40)
    tft.write(FontHeb20,f' {" " if m_altitude > 0 else ""}{m_altitude:.3f}° :{reverse("ירח")}                          :{reverse("שמש")}',0,90)
    tft.write(FontHeb40,f"{" " if altitude > 0 else ""}{round(altitude,3):.3f}°", 125, 80)
    tft.write(FontHeb20,f'{greg_date_string}                            {utc_offset_string}',0,140)
    tft.write(FontHeb40,f'  {time_string}', 90, 130)
    #tft.write(FontHeb30,f'{mga_temporal_time}', 0, 70)
    #tft.write(FontHeb20,f'                שעון ההלכה',0,145)
    
    #tft.text(f"S_rise: {sunrise}", 0, 40)
    #if MGA_deg:
    #    tft.text(font,f"{mga_temporal_time}", 0, 54)
    
    
    tft.show()
    
    
    
    ################################################################################




# הגדרת GPIO0 כקלט עם התנגדות פנימית כלפי מעלה
#boot_button = Pin(0, Pin.IN, Pin.PULL_UP)
boot_button = Pin(14, Pin.IN, Pin.PULL_UP)

# אינדקס המיקום הנוכחי
location_index = 0

# משתנה לזמן הקריאה האחרונה
last_read_time = time.time()


    
# לולאת רענון
while True:
    
    # כל שעה צריך לקרוא מחדש את השעה כי השעון הפנימי של הבקר עצמו לא מדוייק מספיק
    # בדיקה אם עברה שעה (3600 שניות)
    if time.time() - last_read_time >= 3600:
        sync_rtc_with_ds3231()
        # עדכון זמן הקריאה האחרונה
        last_read_time = time.time()
   
    # טיפול בשינויי מיקום גיאוגרפי בלחיצה על הכפתור
    if boot_button.value() == 0:  # בדיקת אם הכפתור נלחץ
            # עדכון אינדקס המיקום באופן מעגלי
            location_index = (location_index + 1) % len(locations)
            location = locations[location_index]  # שליפת המילון של המיקום הנוכחי
            # ניתן להוסיף כאן קוד לבצע פעולה
            main()
            time.sleep(0.1)  # מניעת קריאה מרובה בזמן הלחיצה

    
    # הפעלת הפונקצייה הראשית והשהייה קטנה לפני שחוזרים עליה שוב
    main()
    current_screen = (current_screen + 1) % 10  # זה גורם מחזור של 10 שניות לאיזה נתונים יוצגו במסך
    time.sleep(0.75)  # רענון כל שנייה אבל צריך לכוון את זה לפי כמה כבד הקוד עד שהתצוגה בפועל תתעדכן כל שנייה ולא יותר ולא בפחות


