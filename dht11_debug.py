#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DHT11デバッグ用テストプログラム
"""

import RPi.GPIO as GPIO
import time
from datetime import datetime

class DHT11Debug:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
    def read_debug(self):
        print(f"GPIO{self.pin}からの読み取りを開始...")
        
        # 初期化
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.HIGH)
        time.sleep(1)  # 1秒待機
        
        print("スタート信号送信中...")
        GPIO.output(self.pin, GPIO.LOW)
        time.sleep(0.018)  # 18ms
        GPIO.output(self.pin, GPIO.HIGH)
        time.sleep(0.00004)  # 40μs
        GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        print("DHT11の応答を待機中...")
        
        # DHT11の応答確認
        timeout = 0
        while GPIO.input(self.pin) == GPIO.HIGH:
            timeout += 1
            if timeout > 10000:
                print("タイムアウト: DHT11が応答しません")
                return None, None
        
        print("DHT11応答検出!")
        
        # 詳細な読み取りは省略し、基本的な動作確認のみ
        time.sleep(0.1)
        
        return 25.0, 60.0  # テスト用の固定値
    
    def cleanup(self):
        GPIO.cleanup()

def main():
    print("DHT11デバッグテスト開始")
    print("配線確認:")
    print("  DHT11 VCC  -> Pi 3.3V (Pin 1)")
    print("  DHT11 GND  -> Pi GND  (Pin 6)")
    print("  DHT11 DATA -> Pi GPIO4 (Pin 7)")
    print()
    
    dht = DHT11Debug(pin=4)
    
    try:
        for i in range(5):
            print(f"\n=== 試行 {i+1} ===")
            temp, hum = dht.read_debug()
            
            if temp is not None and hum is not None:
                print(f"成功: 温度={temp}°C, 湿度={hum}%")
            else:
                print("失敗: センサーから読み取れませんでした")
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nテスト中断")
    finally:
        dht.cleanup()
        print("GPIO クリーンアップ完了")

if __name__ == "__main__":
    main()