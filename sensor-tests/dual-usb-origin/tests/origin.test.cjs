const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../dashboard.html'),'utf8');
const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
function setup(){
  let now=0,tick,closed=false;
  const elements=new Map();
  const element=id=>{
    if(!elements.has(id))elements.set(id,{textContent:'',disabled:false,className:'',style:{},classList:{add(){},remove(){}},clientWidth:600,clientHeight:200,getContext:()=>new Proxy({},{get:()=>()=>{}})});
    return elements.get(id);
  };
  const port={readable:new ReadableStream(),async open(){},async close(){closed=true;}};
  const c=vm.createContext({document:{getElementById:element},navigator:{serial:{requestPort:async()=>port}},window:{isSecureContext:true,devicePixelRatio:1},performance:{now:()=>now},setInterval:fn=>{tick=fn;},TextDecoder,console});
  scripts.forEach(s=>vm.runInContext(s,c));
  return {element,c,receive:line=>vm.runInContext(`receive(${JSON.stringify(line)})`,c),time:value=>{now=value;tick();},closed:()=>closed};
}
const imu=(ts,roll=10,pitch=-5,yaw=359)=>`IMU,${ts},${roll},${pitch},${yaw},1,2,3,4,5,6,0,1,2,3,OK`;
const tof=(ts,mm=245)=>`TOF,${ts},${mm},OK,11`;

test('independent origins preserve raw data and support negative distance and yaw wrap',async()=>{
  const {element:$,c,receive}=setup();
  assert.equal($('zeroAngles').disabled,true);assert.equal($('zeroDistance').disabled,true);
  await $('connect').onclick();receive(imu(1000));receive(tof(1000));
  $('zeroDistance').onclick();assert.equal($('distance').textContent,0);assert.equal($('roll').textContent,'10.00');
  $('zeroAngles').onclick();
  for(const id of ['roll','pitch','yaw'])assert.equal($(id).textContent,'0.00');
  assert.equal($('distanceRaw').textContent,'Original: 245 mm');
  assert.equal($('yawRaw').textContent,'Original: 359.00°');
  receive(imu(1100,12,-8,1));receive(tof(1500,220));
  assert.equal($('roll').textContent,'2.00');assert.equal($('pitch').textContent,'-3.00');assert.equal($('yaw').textContent,'2.00');
  assert.equal($('distance').textContent,-25);
  assert.equal($('gyro').textContent,'1.00 / 2.00 / 3.00');
  $('resetAngles').onclick();assert.equal($('yaw').textContent,'1.00');assert.equal($('distance').textContent,-25);
  $('resetDistance').onclick();assert.equal($('distance').textContent,220);
  assert.equal(vm.runInContext('relativeAngle(359,1)',c),-2);
  assert.equal(vm.runInContext('relativeAngle(180,0)',c),-180);
  await $('disconnect').onclick();
});

test('origin setters reject stale or invalid data and do not fabricate fresh readings',async()=>{
  const {element:$,c,receive,time}=setup();await $('connect').onclick();
  receive(imu(1000));receive(tof(1000));$('zeroAngles').onclick();$('zeroDistance').onclick();
  time(600);assert.equal($('zeroAngles').disabled,true);assert.equal($('zeroDistance').disabled,false);
  $('zeroAngles').onclick();assert.equal($('roll').textContent,'—');
  time(1600);$('zeroDistance').onclick();assert.equal($('distance').textContent,'—');
  receive(imu(1100,20));receive(tof(1500,300));
  assert.equal($('roll').textContent,'10.00');assert.equal($('distance').textContent,55);
  receive('TOF,2000,NA,INVALID_RANGE,4');$('zeroDistance').onclick();assert.equal($('distance').textContent,'—');
  assert.equal(vm.runInContext('distanceOrigin',c),245);
  receive('IMU,1200,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,INVALID');
  assert.equal($('zeroAngles').disabled,true);$('zeroAngles').onclick();
  assert.equal(vm.runInContext('angleOrigin.roll',c),10);
  await $('disconnect').onclick();
});

test('origins clear on reset and reconnect, including reset after invalid readings',async()=>{
  const {element:$,c,receive}=setup();await $('connect').onclick();
  receive(imu(1000));receive(tof(1000));$('zeroAngles').onclick();$('zeroDistance').onclick();
  receive('IMU,1200,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,NA,INVALID');receive(imu(100,30));
  assert.equal(vm.runInContext('angleOrigin',c),null);assert.equal(vm.runInContext('distanceOrigin',c),null);
  assert.equal($('roll').textContent,'30.00');assert.equal($('distance').textContent,'—');
  receive(tof(1000));$('zeroAngles').onclick();$('zeroDistance').onclick();receive('# DUAL_USB v1');
  assert.equal(vm.runInContext('angleOrigin',c),null);assert.equal(vm.runInContext('distanceOrigin',c),null);
  receive(imu(200));receive(tof(200));$('zeroAngles').onclick();$('zeroDistance').onclick();
  await $('disconnect').onclick();
  assert.equal(vm.runInContext('angleOrigin',c),null);assert.equal(vm.runInContext('distanceOrigin',c),null);
  assert.equal($('zeroDistance').disabled,true);assert.equal($('zeroAngles').disabled,true);
});
