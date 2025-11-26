[app]

# (str) Title of your application
title = 智能医疗报告解读

# (str) Package name
package.name = medical_ocr_ai

# (str) Package domain (needed for android/ios packaging)
package.domain = com.medical.helper

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,ttf,ini

# (str) Application versioning (method 1)
version = 0.1

# (list) Application requirements
# 核心依赖锁死版本，防止冲突
requirements = python3,kivy==2.3.0,kivymd==1.1.1,pillow,requests,android,pyjnius

# (str) Custom source folders for requirements
# Sets custom source for any requirements with recipes
# requirements.source.kivy = ../../kivy

# (list) Garden requirements
# garden_requirements =

# (str) Presplash of the application
# presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
# icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) List of service to declare
# services = NAME:ENTRY_POINT_TO_PY,NAME2:ENTRY_POINT2_TO_PY

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (string) Presplash background color (for android)
# Supported formats are: #RRGGBB #AARRGGBB or one of the following names:
# red, blue, green, black, white, gray, cyan, magenta, yellow, lightgray, darkgray, grey, lightgrey, darkgrey, aqua, fuchsia, lime, maroon, navy, olive, purple, silver, teal.
android.presplash_color = #FFFFFF

# (list) Permissions
# 关键权限申请
android.permissions = INTERNET,CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
# 适配 Android 13+
android.api = 33

# (int) Minimum API your APK will support.
# 适配 Android 8.0+
android.minapi = 26

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (bool) Use --private data storage (True) or --dir public storage (False)
# 强制使用私有存储，避免 Android 10+ 权限崩溃
android.private_storage = True

# (str) Android logcat filters to use
android.logcat_filters = *:S python:D

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# 现代手机一般都是 arm64-v8a
android.archs = arm64-v8a

# (bool) enable/disable waithome presplash
android.wakelock = False

# (list) The Android entry point, default is 'org.kivy.android.PythonActivity'
# android.entrypoint = org.kivy.android.PythonActivity

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1