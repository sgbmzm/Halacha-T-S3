import time, math, machine, utime, esp32, network, ntptime
from machine import I2C, Pin, ADC, PWM

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

# פונקצייה להפיכת טקסט כדי שעברית תהיה משמאל לימין
def reverse(string):
    return "".join(reversed(string))


# מונקצייה שמנסה להתחבר לווייפי ולקבל את הזמן הנוכחי ב UTC-0
def update_software():
    """עדכון השעה משרת NTP עם ניסיון לרשתות נוספות במקרה של כישלון, כולל כיבוי Wi-Fi בסוף."""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(False) # חייבים קודם לכבות ואחר כך להדליק
    wlan.active(True)  # הפעלת ה-WiFi

    try:
        networks = wlan.scan()  # סריקת רשתות זמינות
        
        open_networks = [net for net in networks if net[4] == 0]  # מסנן רק רשתות פתוחות כלומר שהן ללא סיסמה
        
        # אם אין רשתות פתוחות מפסיקים את הניסיון
        if not open_networks:
            return "לא נמצאה בסביבה רשת ללא סיסמה!!!"
        
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
                    import mip
                    mip.install("github:sgbmzm/Halacha-T-S3/package.json",target="/")
                    print("התוכנה עודכנה בהצלחה!")
                    return "התוכנה עודכנה בהצלחה!"  # מחזיר את הזמן ומכבה את ה-WiFi (נכבה תמיד ב-finally)
                
                except Exception as error_1:
                    print(f"שגיאה בעדכון התוכנה מהרשת {ssid}: {error_1}")
                    wlan.disconnect()  # ניתוק בלבד, ננסה רשת אחרת

        raise Exception("כשלון בעדכון התוכנה משרת בכל רשת")

    except Exception as error:
        return f"{str(error)}"

    finally:
        wlan.active(False)  # כיבוי ה-WiFi תמיד בסוף, בין אם הצלחנו או נכשלנו



# הדפסה למסך
# הדפסה למסך
tft.fill(0) # מחיקת המסך
tft.write(FontHeb25,f'{reverse("בתהליך עדכון התוכנה...")}',20,15)
tft.write(FontHeb20,f'{reverse("המתן בסבלנות להודעה נוספת")}',10,40)
tft.show() # כדי להציג את הנתונים על המסך
DDD = update_software()
tft.write(FontHeb20,f'{reverse(DDD)}',0,75)
tft.write(FontHeb20,f'{reverse("בעוד 5 שניות המכשיר יופעל מחדש")}',0,110)
tft.show() # כדי להציג את הנתונים על המסך
time.sleep(5)
machine.reset()
   



