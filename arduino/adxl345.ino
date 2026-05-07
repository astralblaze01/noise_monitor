#include <Wire.h>

#define ADXL345_ADDR 0x53

// 레지스터
#define BW_RATE     0x2C
#define POWER_CTL   0x2D
#define DATA_FORMAT 0x31
#define FIFO_CTL    0x38
#define FIFO_STATUS 0x39
#define DATAX0      0x32

#define BUFFER_SIZE 64   // (32 FIFO × 2배 여유)

int16_t zBuffer[BUFFER_SIZE];
int bufferIndex = 0;

//레지스터 값 수정하는 함수.
//define 참조. ADXL-345 datasheet의 레지스터 이름과 번호 일치함.
void writeRegister(byte reg, byte value) {
  Wire.beginTransmission(ADXL345_ADDR); //센서와 통신 열기
  Wire.write(reg); //원하는 레지스터 열어서 (ex. 0x00)
  Wire.write(value); //비트 마스크로 설정하기 (ex. 0x0F)
  Wire.endTransmission(); //센서와 통신 닫기
}

void setup() {
  Serial.begin(230400);   // binary 전송 → 속도 올림
  Wire.begin();
  Wire.setClock(400000);  // 400kHz i2c 통신 최대

  delay(100);

  // 센서 설정
  writeRegister(BW_RATE, 0x0E);     // 1600Hz
  writeRegister(POWER_CTL, 0x08);   // 측정 모드
  writeRegister(DATA_FORMAT, 0x00); // ±2g

  // FIFO 설정 (Stream mode, 32 samples)
  // 0x9F = 이진수 1001 1111
  // 앞의 10(Stream Mode): 메모리가 꽉 차면 옛날 데이터부터 버리면서 새 데이터 담기
  // 뒤의 11111: 데이터가 32개 꽉 차면 신호 주기 (Watermark)
  // ADXL-345 datasheet 21p STREAM MODE 참조
  writeRegister(FIFO_CTL, 0x9F);

  delay(10);
}

int cnt = 0; //FIFO 꽉 차 있는 경우 데이터 유실 중이기 때문에 해당 경우 카운트용.

void loop() {
  // FIFO에 몇 개 쌓였는지 확인

  Wire.beginTransmission(ADXL345_ADDR);
  Wire.write(FIFO_STATUS); //FIFO_STATUS 레지스터 열기
  Wire.endTransmission(false); //통신 연결 연장
  Wire.requestFrom(ADXL345_ADDR, 1); //FIFO_STATUS 레지스터 1바이트만 읽기

  int fifoEntries = Wire.read() & 0x3F; // 상위 2비트 제외 FIFO에 얼마나 있는지. 최대 32 

  if (fifoEntries == 0) return; //읽어올 데이터 없으면 다시 loop.
  
  if (fifoEntries == 32) cnt++;

	//FIFO에 data가 있다면
  for (int i = 0; i < fifoEntries; i++) {
     // Z축만 읽기 (DATAX0부터 X 2, Y 2, Z 2 총 6바이트지만 Z만 사용)
    Wire.beginTransmission(ADXL345_ADDR);
    Wire.write(DATAX0);
    Wire.endTransmission(false);
    Wire.requestFrom(ADXL345_ADDR, 6); //DATAX0 레지스터에 xyz 값이 담겨있음. 총 6바이트 읽어오기.

    // X, Y 버림
    Wire.read(); Wire.read(); // X
    Wire.read(); Wire.read(); // Y
    // Z만 사용
    int16_t z = Wire.read() | (Wire.read() << 8);
    zBuffer[bufferIndex++] = z;

    // 버퍼 꽉 차면 전송
    if (bufferIndex >= BUFFER_SIZE) {
      //디버깅 용
      // for(int j = 0; j < BUFFER_SIZE; j++) {
      //   Serial.print(zBuffer[j]); Serial.println(cnt);
      // }
      Serial.write((uint8_t*)zBuffer, BUFFER_SIZE * 2); //zBuffer 원소 하나당 2바이트 총 BUFFER_SIZE * 2 크기
      bufferIndex = 0;
    }
  }
}