
import utime
from halacha_clock import gematria_pyluach

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
                
    return current_day, current_month




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
def get_heb_date_from_greg_date(greg_year, greg_month, greg_day):
    days_from_rosh_hashana, length_heb_year_in_days, heb_year_int = get_days_from_rosh_hashana(greg_year, greg_month, greg_day)
    rosh_hashana_day, rosh_hashana_month = 1,1
    heb_day_int, heb_month_int = move_heb_date(rosh_hashana_day, rosh_hashana_month, length_heb_year_in_days, days_from_rosh_hashana)
    
    # האם השנה מעוברת
    is_leep_year = length_heb_year_in_days in [383, 384, 385]
    
    # חישוב שם החודש והיום בעברית
    heb_day_string = heb_month_day_names(heb_day_int)
    heb_month_string = heb_month_names(heb_month_int, is_leep_year)
    heb_year_string = gematria_pyluach._num_to_str(heb_year_int, thousands=False, withgershayim=False)
    
    heb_date_string = f'{heb_day_string} {heb_month_string} {heb_year_string}'
    
    return heb_day_int, heb_month_int, heb_year_int, heb_date_string
    
