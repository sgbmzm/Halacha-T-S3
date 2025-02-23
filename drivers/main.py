from machine import Pin

# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח

# אם שני הכפתורים לחוצים בעשה שהמכשיר מאותחל אז קוראים לפוקציית עדכון שעון ההלכה
if boot_button.value() == 0 and button_14.value() == 0:
    from halacha_clock import update_halacha_clock
# בכל מקרה אחר מפעילים את שעון ההלכה
else:
        
    try:
        # אם מחובר חיישן טמפרטורה ולחות מפעילים את תוכנת מזג האוויר
        from machine import Pin, I2C
        from halacha_clock import bme280
        original_i2c = I2C(scl=Pin(44), sda=Pin(43))
        bme = bme280.BME280(i2c=original_i2c)
        from halacha_clock import main_bme280_s3
    except:
        # אם הוא לא מחובר מקבלים שגיאה ואז מפעילים את שעון ההלכה
        from halacha_clock import main_shemesh_s3
