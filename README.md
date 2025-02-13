# Halacha-watch-T-DISPLAY-S3

## License  
**The file `main_shemesh_s3` is for personal use only!**  
**Modification is strictly prohibited.** You may use it as-is, but you may not edit, modify, or alter its content.  
**Commercial use is forbidden.** If you wish to use `main_shemesh_s3` for business or organizational purposes, please contact the author.  

Other files in this repository may have different licensing terms.

```
import network
import time

# פרטי הרשת שלך
SSID = "SSID_NAME"
PASSWORD = "123456789"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)  # מצב תחנת WiFi
    wlan.active(True)  # הפעלת WiFi
    if not wlan.isconnected():
        print("מתחבר לרשת WiFi...")
        wlan.connect(SSID, PASSWORD)  # חיבור לרשת
        while not wlan.isconnected():
            time.sleep(1)  # המתן לחיבור
    print("מחובר ל-WiFi בהצלחה!")
    print("כתובת IP:", wlan.ifconfig()[0])  # הצגת כתובת IP

# קריאה לפונקציה
connect_wifi()


import mip
mip.install("github:sgbmzm/Halacha-T-S3/package.json",target="/")
```

