/* Headless, session-local platform. No camera, microphone, network or save-file
 * writes. Battery contents remain in the owned core, never the source save. */
#include "Platform.h"
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <mutex>
#include <thread>
#include <sys/stat.h>

namespace melonDS::Platform {
struct FileHandle { FILE* file; };
struct Thread {std::thread thread;};
struct Mutex {std::mutex mutex;};
struct Semaphore {std::mutex mutex;std::condition_variable cv;unsigned count=0;};
void SignalStop(StopReason,void*) {}
std::string GetLocalFilePath(const std::string& path){return path;}
FileHandle* OpenFile(const std::string& path,FileMode mode){
    // Core assets are explicitly passed by the bridge. Never create files.
    if(mode&Write)return nullptr;
    auto f=fopen(path.c_str(),(mode&Text)?"r":"rb");return f?new FileHandle{f}:nullptr;
}
FileHandle* OpenLocalFile(const std::string&,FileMode){return nullptr;}
bool FileExists(const std::string& name){struct stat s;return stat(name.c_str(),&s)==0;}
bool LocalFileExists(const std::string&){return false;}
bool CheckFileWritable(const std::string&){return false;}
bool CheckLocalFileWritable(const std::string&){return false;}
bool CloseFile(FileHandle* f){if(!f)return false;bool ok=fclose(f->file)==0;delete f;return ok;}
bool IsEndOfFile(FileHandle* f){return feof(f->file);}
bool FileReadLine(char* s,int n,FileHandle* f){return fgets(s,n,f->file)!=nullptr;}
u64 FilePosition(FileHandle* f){return ftello(f->file);}
bool FileSeek(FileHandle* f,s64 n,FileSeekOrigin o){return fseeko(f->file,n,o==FileSeekOrigin::Start?SEEK_SET:o==FileSeekOrigin::Current?SEEK_CUR:SEEK_END)==0;}
void FileRewind(FileHandle* f){rewind(f->file);}
u64 FileRead(void* p,u64 s,u64 n,FileHandle* f){return fread(p,s,n,f->file);}
bool FileFlush(FileHandle* f){return fflush(f->file)==0;}
u64 FileWrite(const void*,u64,u64,FileHandle*){return 0;}
u64 FileWriteFormatted(FileHandle*,const char*,...){return 0;}
u64 FileLength(FileHandle* f){auto p=ftello(f->file);fseeko(f->file,0,SEEK_END);auto n=ftello(f->file);fseeko(f->file,p,SEEK_SET);return n;}
void Log(LogLevel level,const char* fmt,...){if(level<Warn)return;va_list a;va_start(a,fmt);vfprintf(stderr,fmt,a);va_end(a);}
Thread* Thread_Create(std::function<void()> fn){return new Thread{std::thread(std::move(fn))};}
void Thread_Wait(Thread* t){if(t&&t->thread.joinable())t->thread.join();}
void Thread_Free(Thread* t){Thread_Wait(t);delete t;}
Semaphore* Semaphore_Create(){return new Semaphore;}
void Semaphore_Free(Semaphore* s){delete s;}
void Semaphore_Reset(Semaphore* s){std::lock_guard<std::mutex> l(s->mutex);s->count=0;}
void Semaphore_Wait(Semaphore* s){std::unique_lock<std::mutex> l(s->mutex);s->cv.wait(l,[&]{return s->count>0;});--s->count;}
bool Semaphore_TryWait(Semaphore* s,int ms){std::unique_lock<std::mutex> l(s->mutex);if(!s->cv.wait_for(l,std::chrono::milliseconds(ms),[&]{return s->count>0;}))return false;--s->count;return true;}
void Semaphore_Post(Semaphore* s,int n){std::lock_guard<std::mutex> l(s->mutex);s->count+=n;s->cv.notify_all();}
Mutex* Mutex_Create(){return new Mutex;}
void Mutex_Free(Mutex* m){delete m;}
void Mutex_Lock(Mutex* m){m->mutex.lock();}
void Mutex_Unlock(Mutex* m){m->mutex.unlock();}
bool Mutex_TryLock(Mutex* m){return m->mutex.try_lock();}
void Sleep(u64 us){std::this_thread::sleep_for(std::chrono::microseconds(us));}
u64 GetUSCount(){return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
u64 GetMSCount(){return GetUSCount()/1000;}
void WriteNDSSave(const u8*,u32,u32,u32,void*){}
void WriteGBASave(const u8*,u32,u32,u32,void*){}
void WriteFirmware(const Firmware&,u32,u32,void*){}
void WriteDateTime(int,int,int,int,int,int,void*){}
void MP_Begin(void*){} void MP_End(void*){}
int MP_SendPacket(u8*,int,u64,void*){return 0;}
int MP_RecvPacket(u8*,u64*,void*){return 0;}
int MP_SendCmd(u8*,int,u64,void*){return 0;}
int MP_SendReply(u8*,int,u64,u16,void*){return 0;}
int MP_SendAck(u8*,int,u64,void*){return 0;}
int MP_RecvHostPacket(u8*,u64*,void*){return 0;}
u16 MP_RecvReplies(u8*,u64,u16,void*){return 0;}
int Net_SendPacket(u8*,int,void*){return 0;}
int Net_RecvPacket(u8*,void*){return 0;}
void Camera_Start(int,void*){} void Camera_Stop(int,void*){}
void Camera_CaptureFrame(int,u32*,int,int,bool,void*){}
void Mic_Start(void*){} void Mic_Stop(void*){}
int Mic_ReadInput(s16*,int,void*){return 0;}
AACDecoder* AAC_Init(){return nullptr;}
void AAC_DeInit(AACDecoder*){}
bool AAC_Configure(AACDecoder*,int,int){return false;}
bool AAC_DecodeFrame(AACDecoder*,const void*,int,void*,int){return false;}
bool Addon_KeyDown(KeyType,void*){return false;}
void Addon_RumbleStart(u32,void*){} void Addon_RumbleStop(void*){}
float Addon_MotionQuery(MotionQueryType,void*){return 0;}
DynamicLibrary* DynamicLibrary_Load(const char*){return nullptr;}
void DynamicLibrary_Unload(DynamicLibrary*){}
void* DynamicLibrary_LoadFunction(DynamicLibrary*,const char*){return nullptr;}
}
