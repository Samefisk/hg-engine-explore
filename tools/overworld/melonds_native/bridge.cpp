#include "bridge.h"
#include "phase_scope.h"
#include "NDS.h"
#include "NDSCart.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <vector>
#include <time.h>

using namespace melonDS;
namespace {
struct Hook { uint32_t length; md_callback callback; void* user; };
struct ExecMiss { u32 address=0; u64 generation=0; };
struct PhaseFrame {u64 start=0,children=0;u32 phase=0;};
struct Bridge {
    std::unique_ptr<NDS> nds;
    std::map<uint32_t, Hook> exec[2], writes[2];
    std::array<uint8_t, 1<<20> execPages[2]{};
    std::array<ExecMiss,256> execMisses[2]{};
    u64 execGeneration[2]{1,1};
    std::string error;
    bool opened=false, faulted=false, running=false, redirect=false;
    int callbackCPU=-1;
    uint32_t callbackPC=0;
    bool countDispatches=false;
    md_dispatch_counts dispatchCounts{1,0,0,0,0};
    bool profileEnabled=false;
    md_profile profile{1,0,0,0,0,{}};
    bool timePhases=false;
    md_phase_timing phaseTiming{2,0,0,{}};
    std::array<PhaseFrame,8> phaseStack{};
    u32 phaseDepth=0;
};
static_assert(sizeof(md_dispatch_counts)==32, "dispatch count ABI size differs");
static_assert(sizeof(md_profile)==262176, "profile ABI size differs");
static_assert(sizeof(md_guest_clock)==32, "guest clock ABI size differs");
static_assert(sizeof(md_phase_timing)==64, "phase timing ABI size differs");
// Handles belong to the single owning worker thread, like the core itself.
std::set<void*> liveHandles;
bool phase_clock(u64& value) noexcept {
    timespec t{};
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)!=0||t.tv_sec<0||t.tv_nsec<0||t.tv_nsec>=1000000000)return false;
    value=u64(t.tv_sec)*1000000000+u64(t.tv_nsec);return true;
}
struct Abort {};
Bridge& get(void* h) { if (!h) throw std::runtime_error("null core"); return *static_cast<Bridge*>(h); }
ARM& cpu(Bridge& b,int n) { if(n==0)return b.nds->ARM9; if(n==1)return b.nds->ARM7; throw std::runtime_error("invalid CPU"); }
int fail(Bridge& b,const char* msg) { b.error=msg; return -1; }
template<class F> int checked(void* h,F fn) { try {auto& b=get(h); fn(b);return 0;}catch(const std::exception& e){if(h)get(h).error=e.what();return -1;} }
template<class F> int phase_checked(void* h,F fn) { try {auto& b=get(h);fn(b);return 0;}catch(const std::exception& e){if(h&&!get(h).faulted)get(h).error=e.what();return -1;} }
void reset_profile(Bridge& b) noexcept {
    b.profile.version=1;
    b.profile.flags=b.profileEnabled?MD_PROFILE_FLAG_ENABLED:0;
    b.profile.frame_sequence=b.dispatchCounts.frame_sequence;
    b.profile.total=0;
    b.profile.unmapped=0;
    std::memset(b.profile.counts,0,sizeof(b.profile.counts));
}
void profile_instruction(Bridge& b,int n,u32 address) noexcept {
    if(!b.profileEnabled||n!=0)return;
    bool mapped=address>=MD_PROFILE_PC_BASE&&address<MD_PROFILE_PC_LIMIT;
    u32* count=mapped
        ? &b.profile.counts[(address-MD_PROFILE_PC_BASE)>>MD_PROFILE_PC_BIN_SHIFT]
        : nullptr;
    if(b.profile.total==UINT64_MAX
        || (count!=nullptr&&*count==UINT32_MAX)
        || (count==nullptr&&b.profile.unmapped==UINT64_MAX)) {
        b.profile.flags|=MD_PROFILE_FLAG_INVALID;
        return;
    }
    if(count!=nullptr)++*count;
    else ++b.profile.unmapped;
    ++b.profile.total;
}
std::vector<u8> file(const char* path,size_t max) {
    if(!path)throw std::runtime_error("missing file path");
    std::ifstream in(path,std::ios::binary|std::ios::ate);
    if(!in)throw std::runtime_error("cannot open input file");
    auto size=in.tellg();if(size<=0||uint64_t(size)>max)throw std::runtime_error("invalid input size");
    std::vector<u8> out(size);in.seekg(0);in.read(reinterpret_cast<char*>(out.data()),size);
    if(!in)throw std::runtime_error("short input read");return out;
}
u32* spsr(ARM& a) {switch(a.CPSR&31){case 0x11:return &a.R_FIQ[7];case 0x12:return &a.R_IRQ[2];case 0x13:return &a.R_SVC[2];case 0x17:return &a.R_ABT[2];case 0x1b:return &a.R_UND[2];default:return nullptr;}}
u8* tcm(Bridge& b,int n,u32 addr) {
    if(n)return nullptr;auto& a=b.nds->ARM9;
    if(addr<a.ITCMSize)return &a.ITCM[addr&(ITCMPhysicalSize-1)];
    if((addr&a.DTCMMask)==a.DTCMBase)return &a.DTCM[addr&(DTCMPhysicalSize-1)];
    return nullptr;
}
void range(int n,u32 addr,u32 len){if(n<0||n>1||len>0x1000000||uint64_t(addr)+len>0x100000000ULL)throw std::runtime_error("invalid memory range");}
void dispatch(Bridge& b,int n,u32 addr,u32 width,const Hook& h) {
    auto callback=h.callback;auto user=h.user;
    callback(n,addr,width,user);
    if(b.faulted)throw Abort{};
}
}

u32 MD_PhaseEnter(void* handle,u32 phase) noexcept {
    auto* b=static_cast<Bridge*>(handle);
    if(!b||!b->timePhases)return 0; // disabled: no clock or allocation
    if(phase>=3||b->phaseDepth==b->phaseStack.size()) {b->phaseTiming.flags|=4;return 0;}
    u64 start;
    if(!phase_clock(start)){b->phaseTiming.flags|=4;return 0;}
    b->phaseStack[b->phaseDepth++]={start,0,phase};return b->phaseDepth;
}
void MD_PhaseLeave(void* handle,u32 token) noexcept {
    auto* b=static_cast<Bridge*>(handle);
    if(!b)return;
    if(!token||token!=b->phaseDepth){b->phaseTiming.flags|=4;return;}
    auto frame=b->phaseStack[--b->phaseDepth];u64 end;
    if(!phase_clock(end)||end<frame.start||end-frame.start<frame.children){b->phaseTiming.flags|=4;return;}
    u64 elapsed=end-frame.start;
    auto& row=b->phaseTiming.phases[frame.phase];
    if(row.calls>=100000||row.cpu_ns>1000000000000ULL||elapsed-frame.children>1000000000000ULL-row.cpu_ns)
        b->phaseTiming.flags|=4;
    else {row.cpu_ns+=elapsed-frame.children;++row.calls;}
    if(b->phaseDepth)b->phaseStack[b->phaseDepth-1].children+=elapsed;
}

/* Called only by the pinned interpreter patch, before prefetch/dispatch. */
template<bool cacheMisses> static bool BeforeInstruction(ARM* a) {
    auto* bp=static_cast<Bridge*>(a->NDS.UserData);if(!bp)return false;
    auto& b=*bp;int n=(a==&b.nds->ARM9)?0:1;
    if(b.faulted)throw Abort{};
    u32 width=(a->CPSR&32)?2:4, address=a->R[15]-width;
    if(!b.execPages[n][address>>12]) {
        if(b.countDispatches)++(n?b.dispatchCounts.arm7:b.dispatchCounts.arm9);
        profile_instruction(b,n,address);
        return false;
    }
    auto& miss=b.execMisses[n][(address>>1)&255];
    if constexpr(cacheMisses) {
        if(miss.generation==b.execGeneration[n]&&miss.address==address) {
            if(b.countDispatches)++(n?b.dispatchCounts.arm7:b.dispatchCounts.arm9);
            profile_instruction(b,n,address);
            return false;
        }
    }
    auto it=b.exec[n].find(address);if(it==b.exec[n].end()) {
        if constexpr(cacheMisses)miss={address,b.execGeneration[n]};
        if(b.countDispatches)++(n?b.dispatchCounts.arm7:b.dispatchCounts.arm9);
        profile_instruction(b,n,address);
        return false;
    }
    Hook hook=it->second;b.callbackCPU=n;b.callbackPC=address;b.redirect=false;
    try{dispatch(b,n,address,width,hook);}catch(...){b.callbackCPU=-1;throw;}
    b.callbackCPU=-1;
    if(!b.redirect) {
        if(b.countDispatches)++(n?b.dispatchCounts.arm7:b.dispatchCounts.arm9);
        profile_instruction(b,n,address);
    }
    return b.redirect;
}
bool MD_BeforeInstruction(ARM* a) {return BeforeInstruction<true>(a);}
void MD_AfterWrite(ARM* a,u32 addr,u32 width) {
    auto* bp=static_cast<Bridge*>(a->NDS.UserData);if(!bp)return;
    auto& b=*bp;int n=(a==&b.nds->ARM9)?0:1;
    // Snapshot matching listeners: callers may change hook registration.
    std::vector<Hook> matches;
    for(const auto& item:b.writes[n])if(uint64_t(addr)<uint64_t(item.first)+item.second.length && uint64_t(item.first)<uint64_t(addr)+width)matches.push_back(item.second);
    for(const auto& h:matches)dispatch(b,n,addr,width,h);
}

extern "C" {
uint32_t md_abi_version(){return 1;}
const char* md_source_revision(){return "b86390e4428bf38ce4c1ce0e9ca446d6d25955e8";}
void* md_create(){try{auto b=std::make_unique<Bridge>();b->nds=std::make_unique<NDS>();b->nds->UserData=b.get();b->nds->Reset();liveHandles.insert(b.get());return b.release();}catch(...){return nullptr;}}
void md_destroy(void* h){liveHandles.erase(h);delete static_cast<Bridge*>(h);}
const char* md_last_error(void* h){return h?get(h).error.c_str():"null core";}
int md_open_rom(void* h,const char* path){return checked(h,[&](Bridge& b){
    if(b.opened||b.faulted)throw std::runtime_error("core cannot reopen");
    auto bytes=file(path,0x40000000);auto cart=NDSCart::ParseROM(bytes.data(),bytes.size(),&b);
    if(!cart)throw std::runtime_error("invalid NDS cartridge");
    b.nds->SetNDSCart(std::move(cart));b.nds->Reset();b.nds->SetupDirectBoot(path);b.nds->Start();b.opened=true;
});}
int md_import_save(void* h,const char* path){return checked(h,[&](Bridge& b){if(!b.opened||b.running||b.faulted)throw std::runtime_error("save import state");auto data=file(path,0x1000000);b.nds->SetNDSSave(data.data(),data.size());});}
u32 md_save_size(void* h){try{auto& b=get(h);if(!b.opened)throw std::runtime_error("cartridge not opened");return b.nds->GetNDSSaveLength();}catch(const std::exception& e){if(h)get(h).error=e.what();return 0;}}
int md_read_save(void* h,void* out,u32 len){return checked(h,[&](Bridge& b){if(!b.opened||b.running)throw std::runtime_error("save export state");auto size=b.nds->GetNDSSaveLength();auto data=b.nds->GetNDSSave();if(!size||!data||!out||len!=size)throw std::runtime_error("save export length differs");std::memcpy(out,data,size);});}
int md_read_framebuffer(void* h,void* out,u32 len){return checked(h,[&](Bridge& b){if(!b.opened||b.running)throw std::runtime_error("capture requires paused opened core");if(!out||len!=256*384*4)throw std::runtime_error("framebuffer length differs");auto dest=static_cast<u8*>(out);auto& gpu=b.nds->GPU;for(int screen=0;screen<2;screen++){auto source=gpu.Framebuffer[gpu.FrontBuffer][screen].get();if(!source)throw std::runtime_error("framebuffer unavailable");for(u32 i=0;i<256*192;i++){u32 pixel=source[i];*dest++=(pixel>>16)&255;*dest++=(pixel>>8)&255;*dest++=pixel&255;*dest++=(pixel>>24)&255;}}});}
int md_run_frame(void* h){if(!h)return -1;auto& b=get(h);if(b.faulted)return -1;if(!b.opened||b.running)return fail(b,"core not runnable");b.running=true;
    b.dispatchCounts.flags=b.countDispatches?1:0;
    ++b.dispatchCounts.frame_sequence;b.dispatchCounts.arm9=0;b.dispatchCounts.arm7=0;
    if(b.profileEnabled)reset_profile(b);
    b.phaseTiming={2,b.timePhases?1U:0U,b.dispatchCounts.frame_sequence,{}};
    if(b.phaseDepth){b.phaseTiming.flags|=4;b.phaseDepth=0;}
    try{{MD_PhaseScope frameTiming(h,0);b.nds->RunFrame();}b.running=false;if(b.phaseDepth)b.phaseTiming.flags|=4;if(b.faulted)return -1;if(!b.nds->IsRunning()){b.faulted=true;return fail(b,"native core stopped");}b.dispatchCounts.flags|=2;if(b.profileEnabled)b.profile.flags|=MD_PROFILE_FLAG_COMPLETE;b.phaseTiming.flags|=2;return 0;}
    catch(const Abort&){b.running=false;return -1;}catch(const std::exception& e){b.running=false;b.faulted=true;return fail(b,e.what());}
}
int md_read_guest_clock(void* h,void* out,u32 len){
    if(!h||liveHandles.find(h)==liveHandles.end())return -1;
    return phase_checked(h,[&](Bridge& b){
        if(!b.opened||b.faulted||!b.nds->IsRunning()
            ||(b.running&&b.callbackCPU<0)||!out||len!=sizeof(md_guest_clock))
            throw std::runtime_error("guest clock read state or size");
        const md_guest_clock value{1,b.running?1U:0U,
            b.nds->ARM9Timestamp,b.nds->ARM7Timestamp,b.dispatchCounts.frame_sequence};
        std::memcpy(out,&value,sizeof(value));
    });
}
int md_set_dispatch_counts(void* h,u32 enabled){return checked(h,[&](Bridge& b){
    if(enabled>1||b.running||(enabled&&b.faulted))throw std::runtime_error("dispatch count scope state");
    if(b.countDispatches!=bool(enabled)) {
        b.countDispatches=bool(enabled);
        b.dispatchCounts.flags=enabled;b.dispatchCounts.arm9=0;b.dispatchCounts.arm7=0;
    }
});}
int md_read_dispatch_counts(void* h,void* out,u32 len){return checked(h,[&](Bridge& b){
    if(b.running||!out||len!=sizeof(md_dispatch_counts))throw std::runtime_error("dispatch count read state or size");
    std::memcpy(out,&b.dispatchCounts,sizeof(b.dispatchCounts));
});}
int md_profile_enable(void* h,u32 enabled){return checked(h,[&](Bridge& b){
    if(enabled>1||b.running||(enabled&&b.faulted))throw std::runtime_error("profile scope state");
    if(enabled) {
        b.profileEnabled=true;
        reset_profile(b);
    } else if(b.profileEnabled) {
        b.profileEnabled=false;
        reset_profile(b);
    }
});}
int md_profile_read(void* h,void* out,u32 len){return checked(h,[&](Bridge& b){
    if(b.running||!out||len!=sizeof(md_profile))throw std::runtime_error("profile read state or size");
    std::memcpy(out,&b.profile,sizeof(b.profile));
});}
int md_set_phase_timing(void* h,u32 enabled){return phase_checked(h,[&](Bridge& b){
    if(enabled>1||b.running||b.phaseDepth||(enabled&&b.faulted))throw std::runtime_error("phase timing scope state");
    if(b.timePhases!=bool(enabled)) {
        b.timePhases=bool(enabled);b.phaseTiming={2,enabled,b.dispatchCounts.frame_sequence,{}};
    }
});}
int md_read_phase_timing(void* h,void* out,u32 len){return phase_checked(h,[&](Bridge& b){
    if(b.running||b.phaseDepth||!out||len!=sizeof(md_phase_timing))throw std::runtime_error("phase timing read state or size");
    std::memcpy(out,&b.phaseTiming,sizeof(b.phaseTiming));
});}
int md_read_bytes(void* h,int n,u32 addr,void* out,u32 len){return checked(h,[&](Bridge& b){range(n,addr,len);if(len&&!out)throw std::runtime_error("null read buffer");auto p=static_cast<u8*>(out);for(u32 i=0;i<len;i++){auto t=tcm(b,n,addr+i);p[i]=t?*t:(n?b.nds->ARM7Read8(addr+i):b.nds->ARM9Read8(addr+i));}});}
int md_write_bytes(void* h,int n,u32 addr,const void* data,u32 len){return checked(h,[&](Bridge& b){range(n,addr,len);if(b.faulted)throw std::runtime_error("core faulted");if(len&&!data)throw std::runtime_error("null write buffer");auto p=static_cast<const u8*>(data);for(u32 i=0;i<len;i++){auto t=tcm(b,n,addr+i);if(t)*t=p[i];else if(n)b.nds->ARM7Write8(addr+i,p[i]);else b.nds->ARM9Write8(addr+i,p[i]);}});}
u32 md_get_reg(void* h,int n,int index){try{auto& b=get(h);auto& a=cpu(b,n);if(index==16)return a.CPSR;if(index==17){auto p=spsr(a);return p?*p:a.CPSR;}if(index<0||index>15)throw std::runtime_error("invalid register");if(index==15&&b.callbackCPU==n)return b.callbackPC+((a.CPSR&32)?4:8);return a.R[index];}catch(const std::exception& e){if(h)get(h).error=e.what();return 0;}}
int md_set_reg(void* h,int n,int index,u32 value){return checked(h,[&](Bridge& b){if(b.faulted)throw std::runtime_error("core faulted");auto& a=cpu(b,n);if(index==16){a.UpdateMode(a.CPSR&31,value&31);a.CPSR=value;}else if(index==17){auto p=spsr(a);if(!p)throw std::runtime_error("mode has no SPSR");*p=value;}else if(index>=0&&index<16)a.R[index]=value;else throw std::runtime_error("invalid register");});}
u32 md_next_pc(void* h,int n){try{auto& b=get(h);auto& a=cpu(b,n);return b.callbackCPU==n?b.callbackPC:a.R[15]-((a.CPSR&32)?2:4);}catch(const std::exception& e){if(h)get(h).error=e.what();return 0;}}
int md_branch(void* h,int n,u32 addr){return checked(h,[&](Bridge& b){if(b.faulted)throw std::runtime_error("core faulted");auto& a=cpu(b,n);auto cycles=a.Cycles;
    // The caller may already have assigned r15. JumpTo's old-region check
    // cannot then recover the original region, so refresh explicitly.
    a.SetupCodeMem(addr&~1U);a.JumpTo(addr);a.Cycles=cycles;if(b.callbackCPU==n)b.redirect=true;});}
int md_set_keys(void* h,u32 mask){return checked(h,[&](Bridge& b){if(b.faulted)throw std::runtime_error("core faulted");if(mask&~0xfffU)throw std::runtime_error("invalid keys");b.nds->SetKeyMask((~mask)&0xfff);});}
int md_touch(void* h,u32 x,u32 y){return checked(h,[&](Bridge& b){if(b.faulted)throw std::runtime_error("core faulted");if(x>255||y>191)throw std::runtime_error("touch coordinates outside screen");b.nds->TouchScreen(x,y);});}
int md_release_touch(void* h){return checked(h,[&](Bridge& b){if(b.faulted)throw std::runtime_error("core faulted");b.nds->ReleaseScreen();});}
int md_hook_exec(void* h,int n,u32 addr,md_callback cb,void* user){return checked(h,[&](Bridge& b){range(n,addr,2);addr&=~1U;
    // Invalidate before any registration mutation, including callback-owned
    // edits. Cached negatives never own or retain a Hook pointer.
    if(++b.execGeneration[n]==0){b.execMisses[n].fill({});b.execGeneration[n]=1;}
    if(cb){b.exec[n][addr]={0,cb,user};b.execPages[n][addr>>12]=1;}else{b.exec[n].erase(addr);auto next=b.exec[n].lower_bound(addr&~0xfffU);b.execPages[n][addr>>12]=(next!=b.exec[n].end()&&(next->first>>12)==(addr>>12));}});}
int md_hook_write(void* h,int n,u32 addr,u32 len,md_callback cb,void* user){return checked(h,[&](Bridge& b){range(n,addr,len);if(cb){if(!len)throw std::runtime_error("empty write hook");b.writes[n][addr]={len,cb,user};}else b.writes[n].erase(addr);});}
void md_abort(void* h,const char* msg){if(!h)return;auto& b=get(h);if(!b.faulted)b.error=msg?msg:"callback aborted";b.faulted=true;}
}
