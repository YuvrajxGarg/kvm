// KvmCam.dll: "Kvm Camera", a Windows 11 virtual webcam that shows the other computer's camera.
//
// Kvm writes each picture into shared memory ("Global\KvmCamera": a 64-byte header, then 1280x720
// BGRA) with KvmCamWrite, and creates the camera with KvmCamStart (MFCreateVirtualCamera). Windows'
// Frame Server then loads this DLL as the camera's media source and hands its pictures (NV12 or
// RGB32) to any app that opens "Kvm Camera".
//
// Build: native/win/build.cmd (MSVC, Windows 11 SDK).

#include <windows.h>
#include <sddl.h>
#include <wrl.h>
#include <wrl/module.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mferror.h>
#include <mfvirtualcamera.h>
#include <ks.h>
#include <ksproxy.h>
#include <ksmedia.h>
#include <mutex>
#include <cstring>

using namespace Microsoft::WRL;

#define KVMCAM_CLSID_STR L"{5B7C1D2E-8A4F-4C3B-9E61-4B564D43414D}"
static const UINT32 W = 1280, H = 720, FPS = 30;
static const UINT32 MAGIC = 0x4B564D43;  // "KVMC"
static const wchar_t* SHM_NAME = L"Global\\KvmCamera";

struct ShmHeader {
    UINT32 magic, width, height;
    volatile LONG seq;  // odd while Kvm is writing
    UINT32 pad[12];
};
static const size_t SHM_SIZE = sizeof(ShmHeader) + (size_t)W * H * 4;

extern "C" IMAGE_DOS_HEADER __ImageBase;

// ---- reading the picture Kvm wrote ---------------------------------------------------------
class FrameReader {
    HANDLE map_ = nullptr;
    const BYTE* view_ = nullptr;
    std::mutex m_;

public:
    ~FrameReader() {
        if (view_) UnmapViewOfFile(view_);
        if (map_) CloseHandle(map_);
    }
    // Copies the newest picture (BGRA, W x H). False if Kvm hasn't written one.
    bool Read(BYTE* dst) {
        std::lock_guard<std::mutex> lock(m_);
        if (!view_) {
            map_ = OpenFileMappingW(FILE_MAP_READ, FALSE, SHM_NAME);
            if (!map_) return false;
            view_ = (const BYTE*)MapViewOfFile(map_, FILE_MAP_READ, 0, 0, SHM_SIZE);
            if (!view_) {
                CloseHandle(map_);
                map_ = nullptr;
                return false;
            }
        }
        auto* h = (const ShmHeader*)view_;
        if (h->magic != MAGIC || h->width != W || h->height != H) return false;
        for (int tries = 0; tries < 4; tries++) {
            LONG s1 = h->seq;
            if (s1 & 1) { Sleep(1); continue; }
            MemoryBarrier();
            memcpy(dst, view_ + sizeof(ShmHeader), (size_t)W * H * 4);
            MemoryBarrier();
            if (h->seq == s1) return true;
        }
        return true;  // a torn picture is better than none
    }
};

static void BgraToNv12(const BYTE* src, BYTE* dst) {
    BYTE* y = dst;
    BYTE* uv = dst + W * H;
    for (UINT32 r = 0; r < H; r++) {
        const BYTE* p = src + (size_t)r * W * 4;
        for (UINT32 c = 0; c < W; c++, p += 4)
            y[r * W + c] = (BYTE)(((66 * p[2] + 129 * p[1] + 25 * p[0] + 128) >> 8) + 16);
    }
    for (UINT32 r = 0; r < H; r += 2) {
        for (UINT32 c = 0; c < W; c += 2) {
            int R = 0, G = 0, B = 0;
            for (int dy = 0; dy < 2; dy++)
                for (int dx = 0; dx < 2; dx++) {
                    const BYTE* p = src + ((size_t)(r + dy) * W + c + dx) * 4;
                    B += p[0]; G += p[1]; R += p[2];
                }
            R >>= 2; G >>= 2; B >>= 2;
            BYTE* o = uv + (r / 2) * W + c;
            o[0] = (BYTE)(((-38 * R - 74 * G + 112 * B + 128) >> 8) + 128);
            o[1] = (BYTE)(((112 * R - 94 * G - 18 * B + 128) >> 8) + 128);
        }
    }
}

static HRESULT MakeType(const GUID& sub, IMFMediaType** out) {
    ComPtr<IMFMediaType> t;
    HRESULT hr = MFCreateMediaType(&t);
    if (FAILED(hr)) return hr;
    UINT32 stride = sub == MFVideoFormat_NV12 ? W : W * 4;
    UINT32 size = sub == MFVideoFormat_NV12 ? W * H * 3 / 2 : W * H * 4;
    t->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
    t->SetGUID(MF_MT_SUBTYPE, sub);
    MFSetAttributeSize(t.Get(), MF_MT_FRAME_SIZE, W, H);
    MFSetAttributeRatio(t.Get(), MF_MT_FRAME_RATE, FPS, 1);
    MFSetAttributeRatio(t.Get(), MF_MT_PIXEL_ASPECT_RATIO, 1, 1);
    t->SetUINT32(MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive);
    t->SetUINT32(MF_MT_ALL_SAMPLES_INDEPENDENT, TRUE);
    t->SetUINT32(MF_MT_DEFAULT_STRIDE, stride);
    t->SetUINT32(MF_MT_FIXED_SIZE_SAMPLES, TRUE);
    t->SetUINT32(MF_MT_SAMPLE_SIZE, size);
    *out = t.Detach();
    return S_OK;
}

#define KS_NOT_FOUND HRESULT_FROM_WIN32(ERROR_SET_NOT_FOUND)

// ---- the stream ------------------------------------------------------------------------------
class Stream : public RuntimeClass<RuntimeClassFlags<ClassicCom>,
                                   ChainInterfaces<IMFMediaStream2, IMFMediaStream, IMFMediaEventGenerator>, IKsControl> {
    std::mutex m_;
    ComPtr<IMFMediaEventQueue> queue_;
    ComPtr<IMFStreamDescriptor> sd_;
    ComPtr<IMFMediaSource> source_;
    MF_STREAM_STATE state_ = MF_STREAM_STATE_STOPPED;
    GUID subtype_ = MFVideoFormat_NV12;
    FrameReader reader_;
    BYTE* bgra_ = nullptr;
    bool shut_ = false;

public:
    bool started = false;
    ~Stream() { delete[] bgra_; }

    HRESULT Init(IMFMediaSource* source) {
        source_ = source;
        bgra_ = new (std::nothrow) BYTE[(size_t)W * H * 4];
        if (!bgra_) return E_OUTOFMEMORY;
        HRESULT hr = MFCreateEventQueue(&queue_);
        if (FAILED(hr)) return hr;
        ComPtr<IMFMediaType> types[2];
        if (FAILED(hr = MakeType(MFVideoFormat_NV12, &types[0]))) return hr;
        if (FAILED(hr = MakeType(MFVideoFormat_RGB32, &types[1]))) return hr;
        IMFMediaType* raw[2] = {types[0].Get(), types[1].Get()};
        if (FAILED(hr = MFCreateStreamDescriptor(0, 2, raw, &sd_))) return hr;
        ComPtr<IMFMediaTypeHandler> handler;
        if (FAILED(hr = sd_->GetMediaTypeHandler(&handler))) return hr;
        handler->SetCurrentMediaType(types[0].Get());
        sd_->SetGUID(MF_DEVICESTREAM_STREAM_CATEGORY, PINNAME_VIDEO_CAPTURE);
        sd_->SetUINT32(MF_DEVICESTREAM_STREAM_ID, 0);
        sd_->SetUINT32(MF_DEVICESTREAM_FRAMESERVER_SHARED, 1);
        sd_->SetUINT32(MF_DEVICESTREAM_ATTRIBUTE_FRAMESOURCE_TYPES, MFFrameSourceTypes_Color);
        return S_OK;
    }
    IMFStreamDescriptor* Descriptor() { return sd_.Get(); }

    void SetType(IMFMediaType* t) {
        std::lock_guard<std::mutex> lock(m_);
        GUID sub;
        if (t && SUCCEEDED(t->GetGUID(MF_MT_SUBTYPE, &sub))) subtype_ = sub;
    }
    HRESULT Start() {
        std::lock_guard<std::mutex> lock(m_);
        state_ = MF_STREAM_STATE_RUNNING;
        started = true;
        return queue_->QueueEventParamVar(MEStreamStarted, GUID_NULL, S_OK, nullptr);
    }
    HRESULT Stop() {
        std::lock_guard<std::mutex> lock(m_);
        state_ = MF_STREAM_STATE_STOPPED;
        return queue_->QueueEventParamVar(MEStreamStopped, GUID_NULL, S_OK, nullptr);
    }
    void Shutdown() {
        std::lock_guard<std::mutex> lock(m_);
        shut_ = true;
        if (queue_) queue_->Shutdown();
        source_.Reset();
    }

    // IMFMediaEventGenerator
    STDMETHODIMP GetEvent(DWORD flags, IMFMediaEvent** ev) override {
        ComPtr<IMFMediaEventQueue> q;
        { std::lock_guard<std::mutex> lock(m_); if (shut_) return MF_E_SHUTDOWN; q = queue_; }
        return q->GetEvent(flags, ev);
    }
    STDMETHODIMP BeginGetEvent(IMFAsyncCallback* cb, IUnknown* state) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->BeginGetEvent(cb, state);
    }
    STDMETHODIMP EndGetEvent(IMFAsyncResult* r, IMFMediaEvent** ev) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->EndGetEvent(r, ev);
    }
    STDMETHODIMP QueueEvent(MediaEventType t, REFGUID ext, HRESULT st, const PROPVARIANT* v) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->QueueEventParamVar(t, ext, st, v);
    }
    // IMFMediaStream
    STDMETHODIMP GetMediaSource(IMFMediaSource** s) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return source_.CopyTo(s);
    }
    STDMETHODIMP GetStreamDescriptor(IMFStreamDescriptor** sd) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return sd_.CopyTo(sd);
    }
    STDMETHODIMP RequestSample(IUnknown* token) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        if (state_ != MF_STREAM_STATE_RUNNING) return MF_E_MEDIA_SOURCE_WRONGSTATE;
        bool nv12 = subtype_ == MFVideoFormat_NV12;
        DWORD size = nv12 ? W * H * 3 / 2 : W * H * 4;
        if (!reader_.Read(bgra_)) {
            for (size_t i = 0; i < (size_t)W * H; i++) {  // no picture yet: dark grey
                bgra_[i * 4] = bgra_[i * 4 + 1] = bgra_[i * 4 + 2] = 24;
                bgra_[i * 4 + 3] = 255;
            }
        }
        ComPtr<IMFMediaBuffer> buf;
        HRESULT hr = MFCreateMemoryBuffer(size, &buf);
        if (FAILED(hr)) return hr;
        BYTE* p = nullptr;
        if (FAILED(hr = buf->Lock(&p, nullptr, nullptr))) return hr;
        if (nv12) BgraToNv12(bgra_, p);
        else memcpy(p, bgra_, size);
        buf->Unlock();
        buf->SetCurrentLength(size);
        ComPtr<IMFSample> sample;
        if (FAILED(hr = MFCreateSample(&sample))) return hr;
        sample->AddBuffer(buf.Get());
        sample->SetSampleTime(MFGetSystemTime());
        sample->SetSampleDuration(10000000 / FPS);
        if (token) sample->SetUnknown(MFSampleExtension_Token, token);
        return queue_->QueueEventParamUnk(MEMediaSample, GUID_NULL, S_OK, sample.Get());
    }
    // IMFMediaStream2
    STDMETHODIMP SetStreamState(MF_STREAM_STATE s) override {
        if (s == state_) return S_OK;
        if (s == MF_STREAM_STATE_RUNNING) return Start();
        if (s == MF_STREAM_STATE_STOPPED) return Stop();
        std::lock_guard<std::mutex> lock(m_);
        state_ = s;
        return S_OK;
    }
    STDMETHODIMP GetStreamState(MF_STREAM_STATE* s) override {
        if (!s) return E_POINTER;
        *s = state_;
        return S_OK;
    }
    // IKsControl
    STDMETHODIMP KsProperty(PKSPROPERTY, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
    STDMETHODIMP KsMethod(PKSMETHOD, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
    STDMETHODIMP KsEvent(PKSEVENT, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
};

// ---- the source ------------------------------------------------------------------------------
class Source : public RuntimeClass<RuntimeClassFlags<ClassicCom>,
                                   ChainInterfaces<IMFMediaSourceEx, IMFMediaSource, IMFMediaEventGenerator>,
                                   IMFGetService, IKsControl> {
    std::mutex m_;
    ComPtr<IMFMediaEventQueue> queue_;
    ComPtr<IMFAttributes> attrs_;
    ComPtr<IMFPresentationDescriptor> pd_;
    ComPtr<Stream> stream_;
    bool shut_ = false;

public:
    HRESULT Init() {
        HRESULT hr = MFCreateEventQueue(&queue_);
        if (FAILED(hr)) return hr;
        if (FAILED(hr = MFCreateAttributes(&attrs_, 4))) return hr;
        stream_ = Make<Stream>();
        if (!stream_) return E_OUTOFMEMORY;
        if (FAILED(hr = stream_->Init(this))) return hr;
        IMFStreamDescriptor* sds[1] = {stream_->Descriptor()};
        if (FAILED(hr = MFCreatePresentationDescriptor(1, sds, &pd_))) return hr;
        return pd_->SelectStream(0);
    }

    // IMFMediaEventGenerator
    STDMETHODIMP GetEvent(DWORD flags, IMFMediaEvent** ev) override {
        ComPtr<IMFMediaEventQueue> q;
        { std::lock_guard<std::mutex> lock(m_); if (shut_) return MF_E_SHUTDOWN; q = queue_; }
        return q->GetEvent(flags, ev);
    }
    STDMETHODIMP BeginGetEvent(IMFAsyncCallback* cb, IUnknown* state) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->BeginGetEvent(cb, state);
    }
    STDMETHODIMP EndGetEvent(IMFAsyncResult* r, IMFMediaEvent** ev) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->EndGetEvent(r, ev);
    }
    STDMETHODIMP QueueEvent(MediaEventType t, REFGUID ext, HRESULT st, const PROPVARIANT* v) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return queue_->QueueEventParamVar(t, ext, st, v);
    }
    // IMFMediaSource
    STDMETHODIMP GetCharacteristics(DWORD* c) override {
        if (!c) return E_POINTER;
        *c = MFMEDIASOURCE_IS_LIVE;
        return S_OK;
    }
    STDMETHODIMP CreatePresentationDescriptor(IMFPresentationDescriptor** pd) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return pd_->Clone(pd);
    }
    STDMETHODIMP Start(IMFPresentationDescriptor* pd, const GUID* fmt, const PROPVARIANT*) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        if (!pd) return E_INVALIDARG;
        if (fmt && *fmt != GUID_NULL) return MF_E_UNSUPPORTED_TIME_FORMAT;
        BOOL selected = FALSE;
        ComPtr<IMFStreamDescriptor> sd;
        HRESULT hr = pd->GetStreamDescriptorByIndex(0, &selected, &sd);
        if (FAILED(hr)) return hr;
        ComPtr<IMFMediaTypeHandler> handler;
        ComPtr<IMFMediaType> type;
        if (SUCCEEDED(sd->GetMediaTypeHandler(&handler)) && SUCCEEDED(handler->GetCurrentMediaType(&type)))
            stream_->SetType(type.Get());
        if (selected) {
            hr = queue_->QueueEventParamUnk(stream_->started ? MEUpdatedStream : MENewStream, GUID_NULL, S_OK,
                                            static_cast<IMFMediaStream*>(stream_.Get()));
            if (FAILED(hr)) return hr;
            stream_->Start();
        }
        PROPVARIANT now;
        PropVariantInit(&now);
        now.vt = VT_I8;
        now.hVal.QuadPart = MFGetSystemTime();
        return queue_->QueueEventParamVar(MESourceStarted, GUID_NULL, S_OK, &now);
    }
    STDMETHODIMP Stop() override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        stream_->Stop();
        return queue_->QueueEventParamVar(MESourceStopped, GUID_NULL, S_OK, nullptr);
    }
    STDMETHODIMP Pause() override { return MF_E_INVALID_STATE_TRANSITION; }
    STDMETHODIMP Shutdown() override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        shut_ = true;
        if (stream_) stream_->Shutdown();
        if (queue_) queue_->Shutdown();
        return S_OK;
    }
    // IMFMediaSourceEx
    STDMETHODIMP GetSourceAttributes(IMFAttributes** a) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        return attrs_.CopyTo(a);
    }
    STDMETHODIMP GetStreamAttributes(DWORD id, IMFAttributes** a) override {
        std::lock_guard<std::mutex> lock(m_);
        if (shut_) return MF_E_SHUTDOWN;
        if (id != 0) return MF_E_INVALIDSTREAMNUMBER;
        return stream_->Descriptor()->QueryInterface(IID_PPV_ARGS(a));
    }
    STDMETHODIMP SetD3DManager(IUnknown*) override { return S_OK; }
    // IMFGetService
    STDMETHODIMP GetService(REFGUID, REFIID, LPVOID*) override { return MF_E_UNSUPPORTED_SERVICE; }
    // IKsControl
    STDMETHODIMP KsProperty(PKSPROPERTY, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
    STDMETHODIMP KsMethod(PKSMETHOD, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
    STDMETHODIMP KsEvent(PKSEVENT, ULONG, LPVOID, ULONG, ULONG*) override { return KS_NOT_FOUND; }
};

// ---- the activator (what Frame Server creates by CLSID) --------------------------------------
#define FWD(sig, call) STDMETHODIMP sig override { return attrs_ ? attrs_->call : E_OUTOFMEMORY; }

class __declspec(uuid("5B7C1D2E-8A4F-4C3B-9E61-4B564D43414D")) Activator
    : public RuntimeClass<RuntimeClassFlags<ClassicCom>, ChainInterfaces<IMFActivate, IMFAttributes>> {
    ComPtr<IMFAttributes> attrs_;
    ComPtr<Source> source_;
    std::mutex m_;

public:
    Activator() { MFCreateAttributes(&attrs_, 4); }

    STDMETHODIMP ActivateObject(REFIID riid, void** out) override {
        std::lock_guard<std::mutex> lock(m_);
        if (!source_) {
            auto s = Make<Source>();
            if (!s) return E_OUTOFMEMORY;
            HRESULT hr = s->Init();
            if (FAILED(hr)) return hr;
            source_ = s;
        }
        return source_->QueryInterface(riid, out);
    }
    STDMETHODIMP ShutdownObject() override {
        std::lock_guard<std::mutex> lock(m_);
        if (source_) source_->Shutdown();
        source_.Reset();
        return S_OK;
    }
    STDMETHODIMP DetachObject() override {
        std::lock_guard<std::mutex> lock(m_);
        source_.Reset();
        return S_OK;
    }

    FWD(GetItem(REFGUID k, PROPVARIANT* v), GetItem(k, v))
    FWD(GetItemType(REFGUID k, MF_ATTRIBUTE_TYPE* t), GetItemType(k, t))
    FWD(CompareItem(REFGUID k, REFPROPVARIANT v, BOOL* r), CompareItem(k, v, r))
    FWD(Compare(IMFAttributes* o, MF_ATTRIBUTES_MATCH_TYPE t, BOOL* r), Compare(o, t, r))
    FWD(GetUINT32(REFGUID k, UINT32* v), GetUINT32(k, v))
    FWD(GetUINT64(REFGUID k, UINT64* v), GetUINT64(k, v))
    FWD(GetDouble(REFGUID k, double* v), GetDouble(k, v))
    FWD(GetGUID(REFGUID k, GUID* v), GetGUID(k, v))
    FWD(GetStringLength(REFGUID k, UINT32* n), GetStringLength(k, n))
    FWD(GetString(REFGUID k, LPWSTR v, UINT32 n, UINT32* l), GetString(k, v, n, l))
    FWD(GetAllocatedString(REFGUID k, LPWSTR* v, UINT32* l), GetAllocatedString(k, v, l))
    FWD(GetBlobSize(REFGUID k, UINT32* n), GetBlobSize(k, n))
    FWD(GetBlob(REFGUID k, UINT8* b, UINT32 n, UINT32* l), GetBlob(k, b, n, l))
    FWD(GetAllocatedBlob(REFGUID k, UINT8** b, UINT32* l), GetAllocatedBlob(k, b, l))
    FWD(GetUnknown(REFGUID k, REFIID r, LPVOID* v), GetUnknown(k, r, v))
    FWD(SetItem(REFGUID k, REFPROPVARIANT v), SetItem(k, v))
    FWD(DeleteItem(REFGUID k), DeleteItem(k))
    FWD(DeleteAllItems(), DeleteAllItems())
    FWD(SetUINT32(REFGUID k, UINT32 v), SetUINT32(k, v))
    FWD(SetUINT64(REFGUID k, UINT64 v), SetUINT64(k, v))
    FWD(SetDouble(REFGUID k, double v), SetDouble(k, v))
    FWD(SetGUID(REFGUID k, REFGUID v), SetGUID(k, v))
    FWD(SetString(REFGUID k, LPCWSTR v), SetString(k, v))
    FWD(SetBlob(REFGUID k, const UINT8* b, UINT32 n), SetBlob(k, b, n))
    FWD(SetUnknown(REFGUID k, IUnknown* v), SetUnknown(k, v))
    FWD(LockStore(), LockStore())
    FWD(UnlockStore(), UnlockStore())
    FWD(GetCount(UINT32* n), GetCount(n))
    FWD(GetItemByIndex(UINT32 i, GUID* k, PROPVARIANT* v), GetItemByIndex(i, k, v))
    FWD(CopyAllItems(IMFAttributes* d), CopyAllItems(d))
};

CoCreatableClass(Activator);

// ---- COM plumbing ----------------------------------------------------------------------------
STDAPI DllGetClassObject(REFCLSID clsid, REFIID riid, void** out) {
    return Module<InProc>::GetModule().GetClassObject(clsid, riid, out);
}
STDAPI DllCanUnloadNow() { return Module<InProc>::GetModule().Terminate() ? S_OK : S_FALSE; }

static HRESULT SetKey(HKEY root, const wchar_t* path, const wchar_t* name, const wchar_t* value) {
    HKEY k;
    LONG r = RegCreateKeyExW(root, path, 0, nullptr, 0, KEY_WRITE, nullptr, &k, nullptr);
    if (r != ERROR_SUCCESS) return HRESULT_FROM_WIN32(r);
    r = RegSetValueExW(k, name, 0, REG_SZ, (const BYTE*)value, (DWORD)((wcslen(value) + 1) * sizeof(wchar_t)));
    RegCloseKey(k);
    return HRESULT_FROM_WIN32(r);
}
STDAPI DllRegisterServer() {
    wchar_t path[MAX_PATH];
    if (!GetModuleFileNameW((HMODULE)&__ImageBase, path, MAX_PATH)) return HRESULT_FROM_WIN32(GetLastError());
    const wchar_t* key = L"SOFTWARE\\Classes\\CLSID\\" KVMCAM_CLSID_STR L"\\InprocServer32";
    HRESULT hr = SetKey(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Classes\\CLSID\\" KVMCAM_CLSID_STR, nullptr, L"Kvm Camera");
    if (FAILED(hr)) return hr;
    if (FAILED(hr = SetKey(HKEY_LOCAL_MACHINE, key, nullptr, path))) return hr;
    return SetKey(HKEY_LOCAL_MACHINE, key, L"ThreadingModel", L"Both");
}
STDAPI DllUnregisterServer() {
    LONG r = RegDeleteTreeW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Classes\\CLSID\\" KVMCAM_CLSID_STR);
    return r == ERROR_SUCCESS || r == ERROR_FILE_NOT_FOUND ? S_OK : HRESULT_FROM_WIN32(r);
}

// ---- what Kvm calls --------------------------------------------------------------------------
static std::mutex g_m;
static ComPtr<IMFVirtualCamera> g_cam;
static HANDLE g_map = nullptr;
static BYTE* g_view = nullptr;

// Creates "Kvm Camera" (for every user when allUsers, which needs admin/SYSTEM). Call from a
// thread that stays alive while the camera should exist; the camera goes when Kvm exits.
extern "C" __declspec(dllexport) HRESULT __stdcall KvmCamStart(int allUsers) {
    std::lock_guard<std::mutex> lock(g_m);
    if (g_cam) return S_OK;
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) return hr;
    DllRegisterServer();  // needs admin; the installer and the service have it
    if (FAILED(hr = MFStartup(MF_VERSION))) return hr;
    hr = MFCreateVirtualCamera(MFVirtualCameraType_SoftwareCameraSource, MFVirtualCameraLifetime_Session,
                               allUsers ? MFVirtualCameraAccess_AllUsers : MFVirtualCameraAccess_CurrentUser,
                               L"Kvm Camera", KVMCAM_CLSID_STR, nullptr, 0, &g_cam);
    if (FAILED(hr)) return hr;
    hr = g_cam->Start(nullptr);
    if (FAILED(hr)) {
        g_cam->Remove();
        g_cam.Reset();
    }
    return hr;
}

extern "C" __declspec(dllexport) HRESULT __stdcall KvmCamStop() {
    std::lock_guard<std::mutex> lock(g_m);
    if (g_cam) {
        g_cam->Remove();
        g_cam->Shutdown();
        g_cam.Reset();
    }
    return S_OK;
}

// Writes one picture (BGRA, 1280x720, top-down) for the camera to show.
extern "C" __declspec(dllexport) HRESULT __stdcall KvmCamWrite(const BYTE* bgra, int width, int height) {
    if (width != (int)W || height != (int)H || !bgra) return E_INVALIDARG;
    std::lock_guard<std::mutex> lock(g_m);
    if (!g_view) {
        // Readable by everyone: Frame Server runs as LOCAL SERVICE.
        PSECURITY_DESCRIPTOR sd = nullptr;
        ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GR;;;WD)", SDDL_REVISION_1, &sd,
                                                             nullptr);
        SECURITY_ATTRIBUTES sa = {sizeof(sa), sd, FALSE};
        g_map = CreateFileMappingW(INVALID_HANDLE_VALUE, sd ? &sa : nullptr, PAGE_READWRITE, 0, (DWORD)SHM_SIZE, SHM_NAME);
        if (sd) LocalFree(sd);
        if (!g_map) return HRESULT_FROM_WIN32(GetLastError());
        g_view = (BYTE*)MapViewOfFile(g_map, FILE_MAP_WRITE, 0, 0, SHM_SIZE);
        if (!g_view) return HRESULT_FROM_WIN32(GetLastError());
        auto* h = (ShmHeader*)g_view;
        h->width = W;
        h->height = H;
        h->magic = MAGIC;
    }
    auto* h = (ShmHeader*)g_view;
    InterlockedIncrement(&h->seq);  // odd: writing
    memcpy(g_view + sizeof(ShmHeader), bgra, (size_t)W * H * 4);
    InterlockedIncrement(&h->seq);  // even: done
    return S_OK;
}
