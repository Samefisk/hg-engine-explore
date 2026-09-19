/* Native interpreter contract tests, synthetic instructions only. No cartridge. */
#include "bridge.cpp"
#include <iostream>
#include <chrono>
#include <thread>

#define CHECK(x) do {if(!(x))throw std::runtime_error("check failed at line "+std::to_string(__LINE__)+": " #x);} while(0)
struct Owned {void* h=md_create();Owned(){CHECK(h);}~Owned(){md_destroy(h);}};
struct Probe {void* h;u32 start,target,end;bool thumb;int starts=0,targets=0,ends=0,writes=0;};
void stop(int cpu,u32 address,u32 width,void* data){auto& p=*static_cast<Probe*>(data);CHECK(cpu==0);CHECK(address==p.end);CHECK(width==(p.thumb?2:4));p.ends++;md_abort(p.h,"test terminal");}
void entry(int cpu,u32 address,u32 width,void* data){auto& p=*static_cast<Probe*>(data);CHECK(cpu==0);CHECK(address==p.start);CHECK(width==(p.thumb?2:4));CHECK(md_get_reg(p.h,0,0)==0);CHECK(md_get_reg(p.h,0,15)==address+(p.thumb?4:8));CHECK(md_next_pc(p.h,0)==address);p.starts++;
    CHECK(md_hook_exec(p.h,0,address,nullptr,nullptr)==0);
    CHECK(md_set_reg(p.h,0,0,9)==0);CHECK(md_set_reg(p.h,0,15,p.target)==0);
    CHECK(md_branch(p.h,0,p.target|(p.thumb?1:0))==0);
}
void target(int cpu,u32 addr,u32 width,void* data){auto& p=*static_cast<Probe*>(data);CHECK(cpu==0);CHECK(addr==p.target);CHECK(width==(p.thumb?2:4));CHECK(md_get_reg(p.h,0,0)==9);p.targets++;}
void execute(Bridge& b){b.nds->ARM9.Halted=0;b.nds->ARM9.IRQ=0;b.nds->ARM9.Cycles=0;b.nds->ARM9Timestamp=0;b.nds->ARM9Target=10000;try{b.nds->ARM9.Execute<CPUExecuteMode::Interpreter>();}catch(const Abort&){} }
void branch_test(bool thumb,bool crossRegion=false){Owned own;auto& b=get(own.h);Probe p{own.h,crossRegion?0xffff0100U:0x02000100U,0x02000110,0x02000110+(thumb?2U:4U),thumb};
    CHECK(md_set_dispatch_counts(own.h,1)==0);
    u32 armStart=0xe3a00001,armAdd=0xe2800002;u16 thumbStart=0x2001,thumbAdd=0x3002;
    if(crossRegion){std::array<u8,ARM9BIOSSize> bios{};std::memcpy(&bios[0x100],thumb?static_cast<void*>(&thumbStart):&armStart,thumb?2:4);b.nds->SetARM9BIOS(bios);}
    else CHECK(md_write_bytes(own.h,0,p.start,thumb?static_cast<void*>(&thumbStart):&armStart,thumb?2:4)==0);
    CHECK(md_write_bytes(own.h,0,p.target,thumb?static_cast<void*>(&thumbAdd):&armAdd,thumb?2:4)==0);
    CHECK(md_set_reg(own.h,0,16,0x1f|(thumb?32:0))==0);CHECK(md_set_reg(own.h,0,0,0)==0);
    CHECK(md_hook_exec(own.h,0,p.start,entry,&p)==0);CHECK(md_hook_exec(own.h,0,p.target,target,&p)==0);CHECK(md_hook_exec(own.h,0,p.end,stop,&p)==0);
    CHECK(md_branch(own.h,0,p.start|(thumb?1:0))==0);execute(b);
    CHECK(p.starts==1&&p.targets==1&&p.ends==1);CHECK(md_get_reg(own.h,0,0)==11);CHECK(md_run_frame(own.h)==-1);CHECK(std::string(md_last_error(own.h))=="test terminal");
    md_dispatch_counts counts{};CHECK(md_read_dispatch_counts(own.h,&counts,sizeof(counts))==0);
    CHECK(counts.arm9==1&&counts.arm7==0&&counts.flags==1); // redirected start and aborted END do not dispatch
}
void count_stop(int,u32,u32,void* h){md_abort(h,"count terminal");}
void count_noop(int,u32,u32,void*){}
struct ClockProbe {void* h;int cpu;std::vector<md_guest_clock> values;};
void clock_sample(int n,u32 address,u32 width,void* data){
    auto& p=*static_cast<ClockProbe*>(data);CHECK(n==p.cpu&&width==4);
    md_guest_clock first{},second{};
    CHECK(md_read_guest_clock(p.h,&first,sizeof(first))==0);
    CHECK(first.version==1&&first.flags==1);
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    CHECK(md_read_guest_clock(p.h,&second,sizeof(second))==0);
    CHECK(std::memcmp(&first,&second,sizeof(first))==0);
    p.values.push_back(first);
    CHECK(md_get_reg(p.h,n,0)==address/4-0x02000100/4);
    if(address==0x0200010c)md_abort(p.h,"clock terminal");
}
void guest_clock_test(){
    md_guest_clock value{};
    CHECK(md_read_guest_clock(nullptr,&value,32)==-1);
    int unknown=0;CHECK(md_read_guest_clock(&unknown,&value,32)==-1);
    void* closed=md_create();CHECK(closed);md_destroy(closed);
    CHECK(md_read_guest_clock(closed,&value,32)==-1);
    for(int n=0;n<2;n++){
        Owned own;auto& b=get(own.h);ClockProbe probe{own.h,n,{}};
        CHECK(md_read_guest_clock(own.h,&value,32)==-1); // unopened
        b.opened=true;b.nds->Start(); // synthetic interpreter, no cartridge
        CHECK(md_read_guest_clock(own.h,nullptr,32)==-1);
        CHECK(md_read_guest_clock(own.h,&value,31)==-1);
        CHECK(md_read_guest_clock(own.h,&value,33)==-1);
        b.running=true;CHECK(md_read_guest_clock(own.h,&value,32)==-1);
        b.running=false; // only a synchronous exec callback can read in-frame
        b.nds->ARM9Timestamp=uint64_t(1)<<40;b.nds->ARM7Timestamp=17;
        b.dispatchCounts.frame_sequence=9;
        CHECK(md_read_guest_clock(own.h,&value,32)==0);
        CHECK(value.version==1&&value.flags==0&&value.arm9_timestamp==(uint64_t(1)<<40)
            &&value.arm7_timestamp==17&&value.frame_sequence==9);
        auto paused=value;std::this_thread::sleep_for(std::chrono::milliseconds(1));
        CHECK(md_read_guest_clock(own.h,&value,32)==0);
        CHECK(std::memcmp(&paused,&value,32)==0);
        const u32 code[]={0xe3a00001,0xe2800001,0xe2800001,0xe2800001};
        CHECK(md_write_bytes(own.h,n,0x02000100,code,sizeof(code))==0);
        CHECK(md_set_reg(own.h,n,16,0x1f)==0);CHECK(md_set_reg(own.h,n,0,0)==0);
        for(u32 address=0x02000100;address<=0x0200010c;address+=4)
            CHECK(md_hook_exec(own.h,n,address,clock_sample,&probe)==0);
        CHECK(md_branch(own.h,n,0x02000100)==0);
        auto& a=cpu(b,n);a.Halted=0;a.IRQ=0;a.Cycles=0;
        b.nds->ARM9Timestamp=0;b.nds->ARM7Timestamp=0;
        b.nds->ARM9Target=10000;b.nds->ARM7Target=10000;b.running=true;
        try{if(n==0)b.nds->ARM9.Execute<CPUExecuteMode::Interpreter>();
            else b.nds->ARM7.Execute<CPUExecuteMode::Interpreter>();}catch(const Abort&){}
        b.running=false;CHECK(probe.values.size()==4);
        for(size_t i=1;i<probe.values.size();i++){
            const auto& before=probe.values[i-1];const auto& after=probe.values[i];
            CHECK((n?after.arm7_timestamp:after.arm9_timestamp)
                >(n?before.arm7_timestamp:before.arm9_timestamp));
            CHECK((n?after.arm9_timestamp:after.arm7_timestamp)==0);
            CHECK(after.frame_sequence==9);
        }
        value=paused;CHECK(md_read_guest_clock(own.h,&value,32)==-1);
        CHECK(std::memcmp(&paused,&value,32)==0); // faults return no receipt
        CHECK(std::string(md_last_error(own.h))=="clock terminal");
    }
    Owned own;auto& b=get(own.h);b.opened=true;b.nds->Start();b.nds->Halt();
    // Reset does not initialize NDS::Running. Use the real stopped state;
    // production opened=true is reached only after Start in md_open_rom.
    CHECK(!b.nds->IsRunning());
    CHECK(md_read_guest_clock(own.h,&value,32)==-1);
}
void phase_work(){volatile u32 value=0x1234;for(u32 i=0;i<4096;i++)value=(value*1664525+1013904223)^i;}
void phase_test(){Owned own;auto& b=get(own.h);md_phase_timing value{};
    CHECK(md_read_phase_timing(own.h,&value,64)==0);CHECK(value.version==2&&value.flags==0&&value.frame_sequence==0);
    CHECK(MD_PhaseEnter(own.h,0)==0);CHECK(b.phaseDepth==0); // disabled: no scope is opened
    CHECK(md_set_phase_timing(own.h,2)==-1);CHECK(md_read_phase_timing(own.h,nullptr,64)==-1);
    CHECK(md_read_phase_timing(own.h,&value,63)==-1);
    CHECK(md_read_phase_timing(own.h,&value,80)==-1); // old ABI cannot be read as v2
    CHECK(md_set_phase_timing(own.h,1)==0);u64 before,after;CHECK(phase_clock(before));
    {MD_PhaseScope parent(own.h,0);phase_work();{MD_PhaseScope child(own.h,1);phase_work();}phase_work();}
    CHECK(phase_clock(after));CHECK(md_read_phase_timing(own.h,&value,64)==0);
    CHECK(value.flags==1&&value.phases[0].calls==1&&value.phases[1].calls==1);
    CHECK(value.phases[0].cpu_ns>0&&value.phases[1].cpu_ns>0);
    CHECK(value.phases[0].cpu_ns+value.phases[1].cpu_ns<=after-before);
    auto token=MD_PhaseEnter(own.h,2);CHECK(token==1);
    CHECK(md_set_phase_timing(own.h,0)==-1);CHECK(md_read_phase_timing(own.h,&value,64)==-1);
    MD_PhaseLeave(own.h,token+1);MD_PhaseLeave(own.h,token);
    CHECK(md_read_phase_timing(own.h,&value,64)==0);CHECK(value.flags&4);
    CHECK(md_set_phase_timing(own.h,0)==0);CHECK(md_set_phase_timing(own.h,1)==0);
    for(u32 i=1;i<=8;i++)CHECK(MD_PhaseEnter(own.h,i%3)==i);
    CHECK(MD_PhaseEnter(own.h,0)==0);for(u32 i=8;i;i--)MD_PhaseLeave(own.h,i);
    CHECK(md_read_phase_timing(own.h,&value,64)==0);CHECK(value.flags&4);
    CHECK(md_set_phase_timing(own.h,0)==0);CHECK(md_set_phase_timing(own.h,1)==0);
    CHECK(MD_PhaseEnter(own.h,3)==0);CHECK(md_read_phase_timing(own.h,&value,64)==0);CHECK(value.flags&4);
    md_abort(own.h,"first phase native fault");CHECK(md_read_phase_timing(own.h,&value,63)==-1);
    CHECK(std::string(md_last_error(own.h))=="first phase native fault");
    CHECK(md_set_phase_timing(own.h,0)==0);CHECK(md_set_phase_timing(own.h,1)==-1);
    CHECK(std::string(md_last_error(own.h))=="first phase native fault");
}
struct CacheProbe {void* h;u64 hits=0,checksum=0;};
void cache_hit(int n,u32 address,u32 width,void* data){auto& p=*static_cast<CacheProbe*>(data);++p.hits;p.checksum+=address+width+n;}
void cache_install(int n,u32,u32,void* data){auto& p=*static_cast<CacheProbe*>(data);CHECK(md_hook_exec(p.h,n,0x02000100,cache_hit,&p)==0);}
bool cache_visit(Bridge& b,int n,u32 address,bool thumb=false){auto& a=cpu(b,n);a.CPSR=0x1f|(thumb?32:0);a.R[15]=address+(thumb?2:4);return MD_BeforeInstruction(&a);}
void cache_test(){Owned own;auto& b=get(own.h);CacheProbe p{own.h};CHECK(md_set_dispatch_counts(own.h,1)==0);
    for(int n=0;n<2;n++)CHECK(md_hook_exec(own.h,n,0x02000180,count_noop,nullptr)==0);
    CHECK(!cache_visit(b,0,0x02000100));CHECK(!cache_visit(b,0,0x02000100,true));
    CHECK(b.execMisses[1][128].generation==0); // a CPU's misses never populate the other CPU
    CHECK(md_hook_exec(own.h,1,0x02000100,cache_hit,&p)==0);CHECK(!cache_visit(b,1,0x02000100));CHECK(p.hits==1);
    CHECK(md_hook_exec(own.h,0,0x02000100,cache_hit,&p)==0);CHECK(!cache_visit(b,0,0x02000100));CHECK(p.hits==2);
    CHECK(md_hook_exec(own.h,0,0x02000100,count_noop,nullptr)==0);CHECK(!cache_visit(b,0,0x02000100));CHECK(p.hits==2);
    CHECK(md_hook_exec(own.h,0,0x02000100,nullptr,nullptr)==0);CHECK(!cache_visit(b,0,0x02000100));
    // Same direct-map index, different full PC: the cached negative cannot hide a hit.
    CHECK(md_hook_exec(own.h,0,0x02000300,cache_hit,&p)==0);
    CHECK(!cache_visit(b,0,0x02000100));CHECK(!cache_visit(b,0,0x02000300));CHECK(p.hits==3);
    CHECK(md_hook_exec(own.h,0,0x02000140,cache_install,&p)==0);
    CHECK(!cache_visit(b,0,0x02000100));CHECK(!cache_visit(b,0,0x02000140));
    CHECK(!cache_visit(b,0,0x02000100));CHECK(p.hits==4); // registration inside callback invalidates immediately
    CHECK(md_hook_exec(own.h,0,0x80,count_noop,nullptr)==0);
    CHECK(!cache_visit(b,0,0));CHECK(!cache_visit(b,0,0,true));
    CHECK(b.execMisses[0][0].address==0&&b.execMisses[0][0].generation==b.execGeneration[0]);
    b.execGeneration[0]=UINT64_MAX;
    CHECK(md_hook_exec(own.h,0,0,cache_hit,&p)==0);CHECK(b.execGeneration[0]==1);
    CHECK(!cache_visit(b,0,0));CHECK(p.hits==5);
    CHECK(!cache_visit(b,0,0x40));auto count=b.dispatchCounts.arm9;
    md_abort(own.h,"cached miss fault");bool rejected=false;
    try{cache_visit(b,0,0x40);}catch(const Abort&){rejected=true;}
    CHECK(rejected&&b.dispatchCounts.arm9==count);
}
// Test-only instantiation: no exported ABI or runtime cache switch.
bool uncached_before(ARM* a){return BeforeInstruction<false>(a);}
struct BenchResult {u64 elapsed,hits,checksum,arm9,arm7;};
BenchResult cache_bench(bool cached,bool collisions,u32 hookCount){Owned own;auto& b=get(own.h);CacheProbe p{own.h};
    for(int n=0;n<2;n++)CHECK(md_hook_exec(own.h,n,0x02000080,cache_hit,&p)==0);
    for(int n=0;n<2;n++)for(u32 hook=1;hook<hookCount;hook++)
        CHECK(md_hook_exec(own.h,n,0x01f00082+hook*0x8000,cache_hit,&p)==0);
    CHECK(b.exec[0].size()==hookCount&&b.exec[1].size()==hookCount);
    CHECK(md_set_dispatch_counts(own.h,1)==0);
    auto function=cached?MD_BeforeInstruction:uncached_before;
    constexpr u32 iterations=250000;
    auto start=std::chrono::steady_clock::now();
    for(u32 i=0;i<iterations;i++) {
        int n=i&1;bool thumb=(i&2)!=0;
        u32 address=(i%32==0)?0x02000080:0x02000100+((i>>2)&63)*4;
        if(i%17==0)address=0x02100100; // unhooked page
        else if(collisions&&i%32!=0)address+=((i>>8)&1)*512;
        auto& a=cpu(b,n);a.CPSR=0x1f|(thumb?32:0);a.R[15]=address+(thumb?2:4);
        CHECK(!function(&a));
    }
    u64 elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
    CHECK(b.dispatchCounts.arm9+b.dispatchCounts.arm7==iterations);
    return {elapsed,p.hits,p.checksum,b.dispatchCounts.arm9,b.dispatchCounts.arm7};
}
void benchmark(){for(u32 hookCount:{1U,64U,256U})for(bool collisions:{false,true}) {
    auto plain=cache_bench(false,collisions,hookCount),cached=cache_bench(true,collisions,hookCount);
    CHECK(plain.hits==cached.hits&&plain.checksum==cached.checksum&&plain.arm9==cached.arm9&&plain.arm7==cached.arm7);
    std::cout<<"BENCH dispatches=250000 hooks="<<hookCount<<" collisions="<<collisions<<" uncachedWallNs="<<plain.elapsed
             <<" cachedWallNs="<<cached.elapsed<<" hits="<<cached.hits<<" checksum="<<cached.checksum<<"\n";
}}
void dispatch_test(){
    for(int n=0;n<2;n++)for(bool enabled:{false,true}) {
        Owned own;auto& b=get(own.h);md_dispatch_counts counts{};
        CHECK(md_read_dispatch_counts(own.h,&counts,sizeof(counts))==0);
        CHECK(counts.version==1&&counts.flags==0&&counts.frame_sequence==0&&counts.arm9==0&&counts.arm7==0);
        CHECK(md_set_dispatch_counts(own.h,2)==-1);
        CHECK(md_read_dispatch_counts(own.h,nullptr,32)==-1);
        CHECK(md_read_dispatch_counts(own.h,&counts,31)==-1);
        CHECK(md_set_dispatch_counts(own.h,enabled)==0);
        const u32 code[]={0xe3a00001,0xe2800001,0xe2800001,0xe2800001};
        CHECK(md_write_bytes(own.h,n,0x02000100,code,sizeof(code))==0);
        CHECK(md_set_reg(own.h,n,16,0x1f)==0);
        CHECK(md_hook_exec(own.h,n,0x02000108,count_noop,nullptr)==0);
        CHECK(md_hook_exec(own.h,n,0x0200010c,count_stop,own.h)==0);
        CHECK(md_branch(own.h,n,0x02000100)==0);
        auto& a=cpu(b,n);a.Halted=0;a.IRQ=0;a.Cycles=0;
        if(n==0)execute(b);
        else {b.nds->ARM7Timestamp=0;b.nds->ARM7Target=10000;
            try{b.nds->ARM7.Execute<CPUExecuteMode::Interpreter>();}catch(const Abort&){} }
        CHECK(md_read_dispatch_counts(own.h,&counts,32)==0);
        CHECK(counts.arm9==(enabled&&n==0?3U:0U)&&counts.arm7==(enabled&&n==1?3U:0U));
        CHECK(!(counts.flags&2));CHECK(md_get_reg(own.h,n,0)==3);
        CHECK(md_set_dispatch_counts(own.h,1)==-1); // fault cannot enable work
        CHECK(md_set_dispatch_counts(own.h,0)==0);
    }
    Owned own;auto& b=get(own.h);md_dispatch_counts counts{};
    b.opened=true;b.nds->Start(); // no cartridge: both synthetic CPUs stay halted
    b.nds->ARM9.Halted=1;b.nds->ARM7.Halted=1;
    CHECK(md_set_dispatch_counts(own.h,1)==0);
    CHECK(md_set_phase_timing(own.h,1)==0);
    for(u64 frame=1;frame<=2;frame++) {
        b.dispatchCounts.arm9=999;b.dispatchCounts.arm7=999;
        CHECK(md_run_frame(own.h)==0);
        CHECK(md_read_dispatch_counts(own.h,&counts,32)==0);
        CHECK(counts.frame_sequence==frame&&counts.flags==3&&counts.arm9==0&&counts.arm7==0);
        md_phase_timing timing{};CHECK(md_read_phase_timing(own.h,&timing,64)==0);
        CHECK(timing.version==2&&timing.frame_sequence==frame&&timing.flags==3);
        CHECK(timing.phases[0].calls==1&&timing.phases[1].calls==1&&timing.phases[2].calls==384);
        b.phaseTiming.phases[2].calls=999; // next frame must reset, not accumulate
    }
    // A real md_run_frame failure must retain a new, incomplete count receipt.
    u32 nop=0xe1a00000;CHECK(md_write_bytes(own.h,0,0x02000100,&nop,4)==0);
    CHECK(md_set_reg(own.h,0,16,0x1f)==0);
    CHECK(md_hook_exec(own.h,0,0x02000100,count_stop,own.h)==0);
    CHECK(md_branch(own.h,0,0x02000100)==0);b.nds->ARM9.Halted=0;
    CHECK(md_run_frame(own.h)==-1);CHECK(md_read_dispatch_counts(own.h,&counts,32)==0);
    CHECK(counts.frame_sequence==3&&counts.flags==1&&counts.arm9==0&&counts.arm7==0);
    md_phase_timing timing{};CHECK(md_read_phase_timing(own.h,&timing,64)==0);
    CHECK(timing.frame_sequence==3&&timing.flags==1&&b.phaseDepth==0);
    CHECK(timing.phases[0].calls==1); // RAII closes the interrupted frame scope
}
struct ProfileRedirectProbe {void* h;u32 target;int calls=0;};
void profile_redirect(int cpu,u32 address,u32 width,void* data){
    auto& p=*static_cast<ProfileRedirectProbe*>(data);
    CHECK(cpu==0&&width==4&&address==0x02000180);
    ++p.calls;
    CHECK(md_branch(p.h,0,p.target)==0);
}
void profile_test(){
    Owned own;auto& b=get(own.h);auto value=std::make_unique<md_profile>();
    CHECK(sizeof(md_profile)==262176);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    CHECK(value->version==1&&value->flags==0&&value->frame_sequence==0
        &&value->total==0&&value->unmapped==0);
    CHECK(md_profile_enable(own.h,2)==-1);
    CHECK(md_profile_read(own.h,nullptr,sizeof(*value))==-1);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value)-1)==-1);
    CHECK(md_profile_enable(own.h,1)==0);
    CHECK(value->flags==0); // the old read remains unchanged until read again
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    CHECK(value->version==1&&value->flags==MD_PROFILE_FLAG_ENABLED
        &&value->total==0&&value->unmapped==0);

    /* A normal ARM9 instruction in each edge bin, two out-of-range ARM9
     * instructions, and one ARM7 instruction. Only the ARM9 five count. */
    CHECK(!cache_visit(b,0,0x02000100));
    CHECK(!cache_visit(b,0,0x02000100));
    CHECK(!cache_visit(b,0,0x023fffc0));
    CHECK(!cache_visit(b,0,0x01fffffc));
    CHECK(!cache_visit(b,0,0x02400000));
    CHECK(!cache_visit(b,1,0x02000100));

    ProfileRedirectProbe redirect{own.h,0x02000200};
    CHECK(md_hook_exec(own.h,0,0x02000180,profile_redirect,&redirect)==0);
    CHECK(cache_visit(b,0,0x02000180));
    CHECK(redirect.calls==1);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    u64 sum=0;
    for(u32 count:value->counts)sum+=count;
    CHECK(value->flags==MD_PROFILE_FLAG_ENABLED&&value->total==5
        &&value->unmapped==2&&sum==3&&sum+value->unmapped==value->total);
    CHECK(value->counts[(0x02000100-MD_PROFILE_PC_BASE)>>MD_PROFILE_PC_BIN_SHIFT]==2);
    CHECK(value->counts[MD_PROFILE_PC_BIN_COUNT-1]==1);
    CHECK(md_hook_exec(own.h,0,0x02000180,nullptr,nullptr)==0);

    /* Enabling again starts a fresh profile. A successful frame also clears
     * the bins before execution and marks the fixed receipt complete. */
    CHECK(md_profile_enable(own.h,1)==0);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    CHECK(value->flags==MD_PROFILE_FLAG_ENABLED&&value->total==0);
    b.opened=true;b.nds->Start();b.nds->ARM9.Halted=1;b.nds->ARM7.Halted=1;
    CHECK(md_run_frame(own.h)==0);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    CHECK(value->flags==(MD_PROFILE_FLAG_ENABLED|MD_PROFILE_FLAG_COMPLETE)
        &&value->frame_sequence==1&&value->total==0&&value->unmapped==0);
    CHECK(!cache_visit(b,0,0x02000100));
    CHECK(md_run_frame(own.h)==0);
    CHECK(md_profile_read(own.h,value.get(),sizeof(*value))==0);
    CHECK(value->frame_sequence==2&&value->total==0);

    Owned fault;auto& faultBridge=get(fault.h);auto faultValue=std::make_unique<md_profile>();
    CHECK(md_profile_enable(fault.h,1)==0);
    faultBridge.running=true;
    CHECK(md_profile_read(fault.h,faultValue.get(),sizeof(*faultValue))==-1);
    faultBridge.running=false;
    md_abort(fault.h,"profile test fault");
    CHECK(md_profile_read(fault.h,faultValue.get(),sizeof(*faultValue))==0);
    CHECK(md_profile_enable(fault.h,1)==-1); // enabling work after a fault is rejected
    CHECK(md_profile_enable(fault.h,0)==0); // explicit disable remains allowed
}
struct WriteProbe{void* h;int cpu;u32 addr,value;int count=0;};
void written(int n,u32 addr,u32 width,void* user){auto& p=*static_cast<WriteProbe*>(user);CHECK(n==p.cpu);CHECK(addr==p.addr);u32 value=0;CHECK(md_read_bytes(p.h,n,addr,&value,width)==0);CHECK(value==(p.value&(width==1?0xff:width==2?0xffff:0xffffffff)));p.count++;}
void writes_test(){Owned own;auto& b=get(own.h);b.nds->ARM9.ITCMSize=0x02000000;b.nds->ARM9.DTCMBase=0x027c0000;b.nds->ARM9.DTCMMask=0xffffc000;
    for(int n=0;n<2;n++)for(u32 addr: {0x02000200U,0x00000180U,0x01000180U,0x027c0180U}){if(n&&addr!=0x02000200)continue;WriteProbe p{own.h,n,addr,0x1234abcd};CHECK(md_hook_write(own.h,n,addr,4,written,&p)==0);
        auto& a=cpu(b,n);a.DataWrite8(addr,p.value);a.DataWrite16(addr,p.value);a.DataWrite32(addr,p.value);a.DataWrite32S(addr,p.value);CHECK(p.count==4);
        CHECK(md_write_bytes(own.h,n,addr,&p.value,4)==0);CHECK(p.count==4);CHECK(md_hook_write(own.h,n,addr,0,nullptr,nullptr)==0);
    }
    u32 low=0,high=0;CHECK(md_read_bytes(own.h,0,0x180,&low,4)==0);CHECK(md_read_bytes(own.h,0,0x01000180,&high,4)==0);CHECK(low==high&&low==0x1234abcd);
}
void bank_test(){Owned own;CHECK(md_set_reg(own.h,0,16,0x1f)==0);CHECK(md_set_reg(own.h,0,13,0x1234)==0);CHECK(md_set_reg(own.h,0,16,0x12)==0);CHECK(md_set_reg(own.h,0,13,0x9876)==0);CHECK(md_set_reg(own.h,0,17,0x6000003f)==0);CHECK(md_get_reg(own.h,0,17)==0x6000003f);CHECK(md_set_reg(own.h,0,16,0x1f)==0);CHECK(md_get_reg(own.h,0,13)==0x1234);CHECK(md_set_reg(own.h,0,16,0x12)==0);CHECK(md_get_reg(own.h,0,13)==0x9876);CHECK(md_get_reg(own.h,0,17)==0x6000003f);}
struct SaveFixture: NDSCart::CartCommon {
    std::array<u8,4> saved{1,2,3,4};
    SaveFixture(): CartCommon(std::make_unique<u8[]>(0x1000),0x1000,0,false,{},NDSCart::Default,nullptr){}
    u8* GetSaveMemory() override{return saved.data();}
    const u8* GetSaveMemory()const override{return saved.data();}
    u32 GetSaveMemoryLength()const override{return saved.size();}
};
void output_test(){Owned own;auto& b=get(own.h);std::vector<u8> rgba(256*384*4);
    CHECK(md_read_framebuffer(own.h,rgba.data(),rgba.size())==-1);
    // Synthetic buffers only. No image is displayed, saved or taken from a ROM.
    b.opened=true;auto& gpu=b.nds->GPU;gpu.Framebuffer[gpu.FrontBuffer][0][0]=0x80112233;gpu.Framebuffer[gpu.FrontBuffer][1][0]=0xffabcdef;
    CHECK(md_read_framebuffer(own.h,rgba.data(),rgba.size())==0);CHECK(rgba[0]==0x11&&rgba[1]==0x22&&rgba[2]==0x33&&rgba[3]==0x80);
    CHECK(rgba[256*192*4]==0xab&&rgba[256*192*4+1]==0xcd&&rgba[256*192*4+2]==0xef&&rgba[256*192*4+3]==0xff);
    CHECK(md_read_framebuffer(own.h,rgba.data(),rgba.size()-1)==-1);
    CHECK(md_save_size(own.h)==0);u8 saved[4]{};CHECK(md_read_save(own.h,saved,4)==-1);
    b.nds->SetNDSCart(std::make_unique<SaveFixture>());CHECK(md_save_size(own.h)==4);CHECK(md_read_save(own.h,saved,4)==0);CHECK(saved[0]==1&&saved[3]==4);CHECK(md_read_save(own.h,saved,3)==-1);
    CHECK(md_touch(own.h,0,0)==0);CHECK(md_touch(own.h,255,191)==0);CHECK(md_touch(own.h,256,191)==-1);CHECK(md_touch(own.h,255,192)==-1);CHECK(md_release_touch(own.h)==0);
    md_abort(own.h,"test fault");CHECK(md_touch(own.h,0,0)==-1);CHECK(md_release_touch(own.h)==-1);
}
int main(int argc,char** argv){try{CHECK(argc==1||(argc==2&&std::string(argv[1])=="--benchmark"));CHECK(md_run_frame(nullptr)==-1);branch_test(false);branch_test(true);branch_test(false,true);branch_test(true,true);phase_test();guest_clock_test();dispatch_test();profile_test();cache_test();writes_test();bank_test();output_test();std::cout<<"PASS: ARM/Thumb pre-exec, cross-region redirect, guest scheduler clock reads, dispatch counts, ARM9 PC profile, native phase timing, cache mutation, abort latch, ARM9 TCM aliases, CPU writes, banked SPSR, output bytes and touch bounds (no ROM)\n";if(argc==2)benchmark();return 0;}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
