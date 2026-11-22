#include <cassert>
#include <cstring>
#include <iostream>
#include "telemetry.h"

int main(){
    ImuSample s;mapEuler(30,10,-5,s);assert(s.yaw==30&&s.roll==10&&s.pitch==-5);
    s.gx=1.25f;s.gy=-2;s.gz=3;s.ax=0.1f;s.ay=0.2f;s.az=0.3f;s.seq=1;s.ts_ms=100;s.valid=true;
    assert(finiteSample(s));assert(fresh(s,299));assert(!fresh(s,301));
    char out[640];csvLine(out,sizeof(out),s,true);assert(std::strstr(out,"100,10.00,-5.00,30.00,1.25")!=nullptr);
    s.qw=0;assert(!finiteSample(s));s.qw=1;s.valid=false;assert(!fresh(s,150));
    s.gy=std::nanf("");assert(std::strcmp(invalidReason(s),"gy")==0);s.gy=0;
    s.qw=0;assert(std::strcmp(invalidReason(s),"quaternion_norm")==0);s.qw=1;
    csvLine(out,sizeof(out),s,false);assert(std::strstr(out,"NA,NA,NA")&&std::strstr(out,"INVALID"));
    std::cout<<"PASS: axes, serialization, invalid and stale states\n";
}
