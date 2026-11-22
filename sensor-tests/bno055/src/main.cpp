#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Adafruit_BNO055.h>
#include "telemetry.h"

#ifndef BNO_AP_PASSWORD
#define BNO_AP_PASSWORD "BicopterIMU2026!"
#endif
#ifndef BNO_USE_NDOF
#define BNO_USE_NDOF 0
#endif

namespace {
constexpr uint8_t SDA_PIN=21, SCL_PIN=22;
constexpr uint32_t SAMPLE_MS=20, SERIAL_MS=50, RETRY_MS=2000;
constexpr char SSID[]="Bicopter-IMU-Test";
static_assert(sizeof(BNO_AP_PASSWORD)-1 >= 8 && sizeof(BNO_AP_PASSWORD)-1 <= 63,"WPA2 password must be 8-63 characters");
Adafruit_BNO055 bno28(-1,0x28,&Wire), bno29(-1,0x29,&Wire);
Adafruit_BNO055* sensor=nullptr;
WebServer server(80);
portMUX_TYPE sampleMux=portMUX_INITIALIZER_UNLOCKED;
ImuSample latest;
bool connected=false;
uint8_t activeAddress=0;
uint32_t errors=0, lastAttempt=0, lastRead=0, lastSerial=0, serialSeq=0;
const char* modeName=BNO_USE_NDOF ? "NDOF" : "IMUPLUS";

const char PAGE[] PROGMEM=R"HTML(<!doctype html><html lang="es"><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>Bicopter IMU</title><style>
body{font:16px system-ui;background:#101a2a;color:#edf4ff;margin:0;padding:20px}main{max-width:980px;margin:auto}h1{font-size:1.5rem}section{background:#1c2c43;border-radius:12px;padding:16px;margin:12px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.value{font-size:1.7rem;font-weight:700}.label{color:#a9bed7}.bad{color:#ff9b91}.good{color:#99e8c5}#tiltbox{height:130px;display:grid;place-items:center;perspective:350px;overflow:hidden}#tilt{width:110px;height:70px;background:#58b9e8;border:3px solid white;border-radius:10px;display:grid;place-items:center;color:#071622;font-weight:bold}small{color:#a9bed7}</style>
<main><h1>BNO055 · diagnóstico local</h1><p id="state" class="bad">Esperando datos…</p><section><h2>Orientación</h2><div class="grid"><div><span class="label">Roll</span><div id="roll" class="value">—</div></div><div><span class="label">Pitch</span><div id="pitch" class="value">—</div></div><div><span class="label">Yaw</span><div id="yaw" class="value">—</div></div><div id="tiltbox"><div id="tilt">BNO055</div></div></div><small>Vista esquemática: rotación X = pitch, Y = roll; confirme el montaje físico antes de interpretarla.</small></section>
<section><h2>Sensores</h2><div class="grid"><div>Giro °/s<div id="gyro" class="value">—</div></div><div>Aceleración lineal m/s²<div id="accel" class="value">—</div></div><div>Calibración S/G/A/M<div id="cal" class="value">—</div></div><div>Cuaternión W/X/Y/Z<div id="quat">—</div></div></div></section>
<section><h2>Diagnóstico</h2><div id="diag">—</div><small>IMUPLUS no usa magnetómetro como referencia absoluta: yaw puede derivar.</small></section></main><script>
const el=id=>document.getElementById(id),fmt=(v,n=1)=>Number(v).toFixed(n);let last=0;
async function update(){try{const r=await fetch('/api/imu',{cache:'no-store'});if(!r.ok)throw Error('HTTP');const j=await r.json();last=Date.now();el('diag').textContent=`I2C ${j.i2c} · ${j.mode} · ${fmt(j.hz)} Hz · edad ${j.age_ms} ms · errores ${j.errors}`;el('state').textContent=j.status+(j.valid?' · muestra '+j.ts_ms+' ms':' · sin muestra actual');el('state').className=j.valid?'good':'bad';const d=j.data;for(const id of ['roll','pitch','yaw'])el(id).textContent=d?fmt(d[id])+'°':'—';el('gyro').textContent=d?[d.gx,d.gy,d.gz].map(x=>fmt(x)).join(' / '):'—';el('accel').textContent=d?[d.ax,d.ay,d.az].map(x=>fmt(x)).join(' / '):'—';el('cal').textContent=d?d.cal.join(' / '):'—';el('quat').textContent=d?[d.qw,d.qx,d.qy,d.qz].map(x=>fmt(x,3)).join(' / '):'—';el('tilt').style.transform=d?`rotateX(${-d.pitch}deg) rotateY(${d.roll}deg)`:'none';}catch(e){el('state').textContent='HTTP desconectado o sin respuesta';el('state').className='bad';for(const id of ['roll','pitch','yaw','gyro','accel','cal','quat'])el(id).textContent='—';el('tilt').style.transform='none';}}
setInterval(update,100);update();</script></html>)HTML";

bool chipAt(uint8_t address){Wire.beginTransmission(address);Wire.write(0x00);if(Wire.endTransmission(false)!=0||Wire.requestFrom(address,static_cast<uint8_t>(1))!=1)return false;return Wire.read()==0xA0;}
void invalidate(){portENTER_CRITICAL(&sampleMux);latest.valid=false;connected=false;portEXIT_CRITICAL(&sampleMux);++errors;sensor=nullptr;}
bool initialize(){for(uint8_t addr:{static_cast<uint8_t>(0x28),static_cast<uint8_t>(0x29)}){if(!chipAt(addr))continue;Adafruit_BNO055* candidate=addr==0x28?&bno28:&bno29;if(!candidate->begin(BNO_USE_NDOF?OPERATION_MODE_NDOF:OPERATION_MODE_IMUPLUS))continue;sensor=candidate;activeAddress=addr;portENTER_CRITICAL(&sampleMux);connected=true;latest.valid=false;portEXIT_CRITICAL(&sampleMux);Serial.printf("# BNO055 I2C=0x%02X mode=%s\n",addr,modeName);return true;}Serial.println("# ERROR BNO055 not found at 0x28/0x29");++errors;return false;}
void acquire(){if(!sensor)return;const uint32_t now=millis();if(!chipAt(activeAddress)){Serial.println("# ERROR I2C lost");invalidate();return;}ImuSample s;const auto e=sensor->getVector(Adafruit_BNO055::VECTOR_EULER);const auto g=sensor->getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);const auto a=sensor->getVector(Adafruit_BNO055::VECTOR_LINEARACCEL);const auto q=sensor->getQuat();mapEuler(e.x(),e.y(),e.z(),s);s.gx=g.x();s.gy=g.y();s.gz=g.z();s.ax=a.x();s.ay=a.y();s.az=a.z();s.qw=q.w();s.qx=q.x();s.qy=q.y();s.qz=q.z();sensor->getCalibration(&s.cal_sys,&s.cal_gyro,&s.cal_accel,&s.cal_mag);s.ts_ms=millis();s.hz=lastRead&&s.ts_ms!=lastRead?1000.0f/static_cast<float>(s.ts_ms-lastRead):0;lastRead=s.ts_ms;s.valid=finiteSample(s);if(!s.valid){Serial.println("# ERROR invalid IMU values");invalidate();return;}portENTER_CRITICAL(&sampleMux);s.seq=latest.seq+1;latest=s;portEXIT_CRITICAL(&sampleMux);(void)now;}
void webTask(void*){server.on("/",[]{server.send_P(200,"text/html; charset=utf-8",PAGE);});server.on("/api/imu",[]{ImuSample s;bool link;portENTER_CRITICAL(&sampleMux);s=latest;link=connected;portEXIT_CRITICAL(&sampleMux);char body[640];int n=jsonLine(body,sizeof(body),s,millis(),link,modeName,activeAddress,errors);if(n<0)server.send(500,"text/plain","serialization error");else{server.sendHeader("Cache-Control","no-store");server.send(200,"application/json",body);}});server.begin();Serial.println("# HTTP server ready port=80");for(;;){server.handleClient();vTaskDelay(pdMS_TO_TICKS(1));}}
}

void setup(){Serial.begin(115200);delay(200);Wire.begin(SDA_PIN,SCL_PIN);Wire.setClock(100000);Serial.println("# BNO055 standalone test; no ESC/PWM configured");Serial.println("ts_ms,roll_deg,pitch_deg,yaw_deg,gx_dps,gy_dps,gz_dps,ax_ms2,ay_ms2,az_ms2,cal_sys,cal_gyro,cal_accel,cal_mag,status");WiFi.mode(WIFI_AP);bool ap=WiFi.softAP(SSID,BNO_AP_PASSWORD);Serial.printf("# AP=%s password=%s IP=%s status=%s\n",SSID,BNO_AP_PASSWORD,WiFi.softAPIP().toString().c_str(),ap?"OK":"FAILED");if(ap)xTaskCreatePinnedToCore(webTask,"web",8192,nullptr,1,nullptr,0);lastAttempt=millis()-RETRY_MS;}
void loop(){uint32_t now=millis();if(!sensor&&static_cast<uint32_t>(now-lastAttempt)>=RETRY_MS){lastAttempt=now;initialize();}if(sensor&&static_cast<uint32_t>(now-lastRead)>=SAMPLE_MS)acquire();if(static_cast<uint32_t>(now-lastSerial)>=SERIAL_MS){lastSerial=now;ImuSample s;portENTER_CRITICAL(&sampleMux);s=latest;portEXIT_CRITICAL(&sampleMux);char line[220];bool ok=fresh(s,now)&&s.seq!=serialSeq;if(ok)serialSeq=s.seq;csvLine(line,sizeof(line),s,ok);Serial.print(line);}delay(1);}
