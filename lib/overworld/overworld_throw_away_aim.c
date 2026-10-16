#include "../../include/overworld_throw_away_aim.h"

static int AwayDistance(int x, int z)
{
    x=x<0?-x:x; z=z<0?-z:z;
    return x>z?x:z;
}

u8 OverworldThrowAwayAim_Validate(
    const OverworldThrowAwayAimCall *call, const OverworldThrowAwayAim *saved)
{
    s32 baseY;
    if(call==NULL || saved==NULL || call->landing==NULL
        || call->distance==0 || call->distance>8 || saved->distance!=call->distance
        || saved->direction>3 || (u32)saved->x>32767 || (u32)saved->z>32767
        || (u32)call->originX>32767 || (u32)call->originZ>32767
        || (u32)call->playerX>32767 || (u32)call->playerZ>32767
        || AwayDistance(saved->x-call->originX,saved->z-call->originZ)!=call->distance
        || AwayDistance(saved->x-call->playerX,saved->z-call->playerZ)
            <=AwayDistance(call->originX-call->playerX,call->originZ-call->playerZ)) return FALSE;
    return call->landing(call->world,saved->x,saved->z,&baseY)
        ==OVERWORLD_MOTION_DECISION_ACCEPTED && baseY==saved->baseY;
}

u8 OverworldThrowAwayAim_Select(
    const OverworldThrowAwayAimCall *call, OverworldThrowAwayAim *out)
{
    static const signed char deltaX[4]={0,0,-1,1};
    static const signed char deltaZ[4]={-1,1,0,0};
    u8 directions[4];
    int dx,dz,originDistance,projectedX,projectedZ;
    if(call==NULL || out==NULL || call->landing==NULL
        || call->distance==0 || call->distance>8
        || (u32)call->originX>32767 || (u32)call->originZ>32767
        || (u32)call->playerX>32767 || (u32)call->playerZ>32767) return FALSE;
    dx=call->originX-call->playerX; dz=call->originZ-call->playerZ;
    originDistance=AwayDistance(dx,dz);
    directions[0]=2+(dx>0); directions[1]=dz>0;
    if((dx<0?-dx:dx)<(dz<0?-dz:dz)) {
        u8 swap=directions[0]; directions[0]=directions[1]; directions[1]=swap;
    }
    directions[2]=directions[0]^1; directions[3]=directions[1]^1;
    projectedX=projectedZ=0;
    if(originDistance!=0) {
        /* Scale the outward vector to the exact Chebyshev radius, rounding
         * its shorter axis to the nearest tile. Valid input keeps these
         * products below 32767*8+32767/2. */
        u32 scaledX=(dx<0?-dx:dx)*call->distance+originDistance/2;
        u32 scaledZ=(dz<0?-dz:dz)*call->distance+originDistance/2;
        /* The radius is at most eight: each exact quotient needs at most
         * eight subtracts. Keep the existing native import whitelist. */
        while(scaledX>=(u32)originDistance) {
            scaledX-=originDistance; ++projectedX;
        }
        while(scaledZ>=(u32)originDistance) {
            scaledZ-=originDistance; ++projectedZ;
        }
        if(dx<0) projectedX=-projectedX;
        if(dz<0) projectedZ=-projectedZ;
    }
    for(u8 i=0;i<5;i++) {
        u8 direction=directions[i!=0?i-1:0];
        int x,z;
        if(i==0) {
            /* A cardinal projection is already the first old candidate. */
            if(projectedX==0 || projectedZ==0) continue;
            x=call->originX+projectedX;z=call->originZ+projectedZ;
        } else {
            x=call->originX+deltaX[direction]*call->distance;
            z=call->originZ+deltaZ[direction]*call->distance;
        }
        s32 baseY;
        OverworldMotionDecision decision;
        if((u32)x>32767 || (u32)z>32767
            || AwayDistance(x-call->playerX,z-call->playerZ)<=originDistance) continue;
        decision=call->landing(call->world,x,z,&baseY);
        if(decision==OVERWORLD_MOTION_DECISION_ACCEPTED) {
            *out=(OverworldThrowAwayAim){x,z,baseY,direction,call->distance};
            return TRUE;
        }
        if((u32)(decision-OVERWORLD_MOTION_DECISION_BLOCKED)
            >OVERWORLD_MOTION_DECISION_RESERVED-OVERWORLD_MOTION_DECISION_BLOCKED) return FALSE;
    }
    return FALSE;
}
