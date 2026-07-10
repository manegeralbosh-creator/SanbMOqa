[app]
title = Bocsh App
package.name = bocshapp
package.domain = org.bocsh
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
version = 0.1
requirements = python3,kivy,requests,urllib3,charset_normalizer,idna

orientation = portrait
fullscreen = 0
android.archs = arm64-v8a

# الصلاحيات المطلوبة لتشغيل الإنترنت وفتح الواتساب آلياً
android.permissions = INTERNET, ACCESS_NETWORK_STATE
