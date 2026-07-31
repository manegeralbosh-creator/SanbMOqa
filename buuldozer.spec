[app]

# (str) Title of your application
title = Al-Boush SMS Manager

# (str) Package name
package.name = alboushmanager

# (str) Package domain (needed for android packaging)
package.domain = org.alboush

# (str) Source files where the let's go app lives (relative to directory of spec file)
source.include_exts = py,png,jpg,kv,atlas

# (list) Source files to include (let it empty to include all the files)
source.include_patterns = assets/*,images/*.png

# (str) Application versioning
version = 1.0

# (list) Application requirements
# Add kivy, pyjnius, and python dependencies here
requirements = python3,kivy,pyjnius

# (list) Permissions
# الصلاحيات السيادية المطلوبة للتحكم بالرسائل والخلفية
android.permissions = INTERNET,SEND_SMS,WAKE_LOCK,FOREGROUND_SERVICE,RECEIVE_BOOT_COMPLETED

# (str) Supported orientations
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Target Android API, should be as high as possible.
android.api = 33

# (list) Minimum API your APK will support.
android.minapi = 21

[buildozer]

# (int) Log level (0 = error, 1 = info, 2 = debug (withcommand output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = Danger, 2 = Verify5)
log_level_debug = 1
