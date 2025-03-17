from machine import Pin, PWM

# למסך
import halacha_clock.tft_config as tft_config
import s3lcd
import halacha_clock.miriam25 as FontHeb25

# פונקצייה להפיכת טקסט כדי שעברית תהיה משמאל לימין
def reverse(string):
    return "".join(reversed(string))

# הצגת הודעה על המסך כמה שיותר מהר כדי שיראו שהכל בסדר
try:
    tft = tft_config.config(rotation=3) # כיוון סיבוב התצוגה שאני רוצה
    tft.init() # כך חייבים לעשות
    BACKLIGHT = PWM(Pin(38, Pin.OUT), freq=1000)
    BACKLIGHT.duty(255)
    tft.fill(0) # מחיקת המסך
    tft.write(FontHeb25,f'{reverse("מתחיל...")}',200,20)
    #tft.line(0, 45, 320, 45, s3lcd.YELLOW)
    tft.show()
finally:
    tft_config.deinit(tft)

# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח

# אם שני הכפתורים לחוצים בעשה שהמכשיר מאותחל אז קוראים לפוקציית עדכון שעון ההלכה
if boot_button.value() == 0 and button_14.value() == 0:
    from halacha_clock import update_halacha_clock

# בכל מקרה אחר מפעילים את שעון ההלכה
else:
    from halacha_clock import main_shemesh_s3

