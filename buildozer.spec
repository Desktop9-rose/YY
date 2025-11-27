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
requirements = python3,kivy==2.3.0,kivymd==1.1.1,requests,pillow,android,pyjnius,urllib3,sqlite3

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = INTERNET,CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,RECORD_AUDIO

# (int) Target Android API
android.api = 33

# (int) Minimum Android API
android.minapi = 26

# (int) Android SDK version to use
android.sdk = 33

# (str) Android NDK version to use
android.ndk = 25b

# (str) Android Build Tools version to use
android.build_tools_version = 34.0.0

# (bool) Use --private data storage
android.private_storage = True

# (str) Android arch
android.archs = arm64-v8a

# (bool) Skip byte compile for .py files
android.no_byte_compile_python = 0

# (bool) Accept SDK license automatically
android.accept_sdk_license = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0