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
version = 0.3

# (list) Application requirements
# 关键修改：移除了所有 alibabacloud_* 库，只保留 requests
requirements = python3,kivy==2.3.0,kivymd==1.1.1,pillow,requests,android,pyjnius,plyer

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# (int) Target Android API
android.api = 33
android.minapi = 26
android.sdk = 33
android.ndk = 25b

# (bool) Use --private data storage
android.private_storage = True

# (str) Android arch
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1