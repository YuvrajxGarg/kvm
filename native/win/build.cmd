@echo off
rem Builds native-build\KvmCam.dll (the "Kvm Camera" virtual webcam) with MSVC and the Windows 11 SDK.
setlocal
cd /d "%~dp0\..\.."
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set VS=%%i
if not defined VS (echo Visual Studio C++ tools not found & exit /b 1)
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
if not exist native-build mkdir native-build
cl /nologo /LD /O2 /EHsc /std:c++17 /W3 /DUNICODE /D_UNICODE native\win\kvmcam.cpp ^
  /Fo:native-build\kvmcam.obj /Fe:native-build\KvmCam.dll ^
  /link /DEF:native\win\kvmcam.def mfplat.lib mf.lib mfuuid.lib mfsensorgroup.lib ole32.lib advapi32.lib runtimeobject.lib delayimp.lib /DELAYLOAD:mfsensorgroup.dll || exit /b 1
echo Built native-build\KvmCam.dll
