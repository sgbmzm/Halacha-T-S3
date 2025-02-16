from machine import Pin

# הגדרת הכפתורים הפיזיים במכשיר
boot_button = Pin(0, Pin.IN, Pin.PULL_UP) # משמש בקוד לשינוי המיקומים ולקביעת מיקום ברירת מחדל
button_14 = Pin(14, Pin.IN, Pin.PULL_UP) # משמש בקוד להכנסת המכשיר למצב שינה ולהתעוררות ולשליטה על הכוח

# אם שני הכפתורים לחוצים בעשה שהמכשיר מאותחל אז קוראים לפוקציית עדכון שעון ההלכה
if boot_button.value() == 0 and button_14.value() == 0:
    from halacha_clock import update_halacha_clock
# בכל מקרה אחר מפעילים את שעון ההלכה
else:
    from halacha_clock import main_shemesh_s3 
