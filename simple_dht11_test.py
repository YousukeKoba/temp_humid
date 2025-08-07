#!/usr/bin/env python3
"""
シンプルなDHT11センサーテスト
基本的なアルゴリズムでDHT11からデータを読み取ります
"""

import RPi.GPIO as GPIO
import time

def simple_dht11_test(pin=4):
    """
    シンプルなDHT11読み取りテスト
    
    Args:
        pin (int): DHT11のデータピン番号（BCM番号）
        
    Returns:
        tuple: (temperature, humidity) または None
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    try:
        print(f"DHT11センサー読み取り開始 (GPIO{pin})")
        
        # 初期状態の確認
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        initial_state = GPIO.input(pin)
        print(f"初期GPIO状態: {initial_state} ({'HIGH' if initial_state else 'LOW'})")
        
        # 開始信号を送信
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # まず確実にHIGHにする
        time.sleep(0.01)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.02)  # 20ms LOW
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.00004)  # 40μs HIGH
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # 初期状態を再確認
        after_setup_state = GPIO.input(pin)
        print(f"開始信号後GPIO状態: {after_setup_state} ({'HIGH' if after_setup_state else 'LOW'})")
        
        # DHT11の応答信号を待機
        timeout = 0
        while GPIO.input(pin) == GPIO.HIGH:
            timeout += 1
            if timeout > 10000:  # タイムアウトを増加
                print(f"エラー: DHT11からの応答がありません (タイムアウト: {timeout})")
                return None
        
        print(f"応答信号検出 (HIGH->LOW): タイムアウトカウント={timeout}")
        
        # 応答信号の LOW 部分を待機
        timeout = 0
        while GPIO.input(pin) == GPIO.LOW:
            timeout += 1
            if timeout > 10000:
                print(f"エラー: 応答信号LOWが長すぎます (タイムアウト: {timeout})")
                return None
        
        print(f"応答信号LOW完了: タイムアウトカウント={timeout}")
        
        # 応答信号の HIGH 部分を待機
        timeout = 0
        while GPIO.input(pin) == GPIO.HIGH:
            timeout += 1
            if timeout > 10000:
                print(f"エラー: 応答信号HIGHが長すぎます (タイムアウト: {timeout})")
                return None
        
        print(f"応答信号HIGH完了: タイムアウトカウント={timeout}")
        print("データ読み取り開始...")
        
        # 40ビットのデータを読み取り
        bits = []
        for i in range(40):
            # 各ビットの LOW 部分を待機
            timeout = 0
            while GPIO.input(pin) == GPIO.LOW:
                timeout += 1
                if timeout > 10000:
                    print(f"ビット{i}: LOW待機タイムアウト")
                    return None
            
            # HIGH 部分の時間を測定
            start_time = time.time()
            timeout = 0
            while GPIO.input(pin) == GPIO.HIGH:
                timeout += 1
                if timeout > 10000:
                    print(f"ビット{i}: HIGH待機タイムアウト (カウント={timeout})")
                    if i >= 10:  # 10ビット以上読めていれば部分成功
                        print(f"部分読み取り成功: {i}ビット")
                        break
                    return None
            
            duration = (time.time() - start_time) * 1000000  # マイクロ秒
            
            # ビット判定: 35μs以上なら1、未満なら0
            bit_value = 1 if duration > 35 else 0
            bits.append(bit_value)
            
            # 最初の10ビットをデバッグ表示
            if i < 10:
                print(f"ビット{i:2d}: {duration:5.1f}μs (カウント:{timeout:4d}) -> {bit_value}")
        
        print(f"データ読み取り完了: {len(bits)}ビット")
        
        if len(bits) < 32:
            print("読み取りビット数が不足しています")
            return None
        
        # ビットをバイトに変換
        bytes_data = []
        for i in range(5):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) + bits[i * 8 + j]
            bytes_data.append(byte_val)
        
        print(f"バイトデータ: {[f'0x{b:02x}' for b in bytes_data]}")
        
        # 温湿度データを抽出
        humidity_int = bytes_data[0]
        humidity_dec = bytes_data[1]
        temperature_int = bytes_data[2]
        temperature_dec = bytes_data[3]
        checksum_received = bytes_data[4]
        
        # DHT11では小数部は通常0
        humidity = humidity_int + humidity_dec * 0.1
        temperature = temperature_int + temperature_dec * 0.1
        
        # チェックサムを計算
        checksum_calculated = (humidity_int + humidity_dec + temperature_int + temperature_dec) & 0xFF
        
        print(f"湿度: {humidity}% (整数部: {humidity_int}, 小数部: {humidity_dec})")
        print(f"温度: {temperature}°C (整数部: {temperature_int}, 小数部: {temperature_dec})")
        print(f"チェックサム: 計算値=0x{checksum_calculated:02x}, 受信値=0x{checksum_received:02x}")
        
        # チェックサム検証
        if checksum_calculated == checksum_received:
            print("✓ チェックサム OK!")
            
            # 値の妥当性をチェック
            if 0 <= humidity <= 100 and -40 <= temperature <= 80:
                print("✓ 値の範囲 OK!")
                return temperature, humidity
            else:
                print("✗ 値が妥当範囲外です")
                return None
        else:
            print("✗ チェックサムエラー")
            # チェックサムエラーでも参考値として表示
            print(f"参考値: 温度={temperature}°C, 湿度={humidity}%")
            return None
            
    except Exception as e:
        print(f"エラー: {e}")
        return None
    finally:
        GPIO.cleanup()

def multiple_test(pin=4, count=5):
    """
    複数回テストを実行
    
    Args:
        pin (int): DHT11のデータピン番号
        count (int): テスト回数
    """
    print(f"=== DHT11 連続テスト ({count}回) ===")
    successful_readings = []
    
    for i in range(count):
        print(f"\n--- テスト {i+1}/{count} ---")
        result = simple_dht11_test(pin)
        
        if result:
            temp, hum = result
            successful_readings.append((temp, hum))
            print(f"成功: 温度={temp}°C, 湿度={hum}%")
        else:
            print("失敗")
        
        if i < count - 1:
            print("2秒待機...")
            time.sleep(2)
    
    # 結果のまとめ
    print(f"\n=== テスト結果まとめ ===")
    print(f"成功回数: {len(successful_readings)}/{count}")
    
    if successful_readings:
        avg_temp = sum(reading[0] for reading in successful_readings) / len(successful_readings)
        avg_hum = sum(reading[1] for reading in successful_readings) / len(successful_readings)
        print(f"平均値: 温度={avg_temp:.1f}°C, 湿度={avg_hum:.1f}%")

if __name__ == "__main__":
    print("DHT11センサー シンプルテスト")
    print("GPIO4ピンに接続されたDHT11センサーを読み取ります")
    print("Ctrl+Cで終了\n")
    
    try:
        # 単発テスト
        result = simple_dht11_test(pin=4)
        if result:
            temp, hum = result
            print(f"\n最終結果: 温度={temp}°C, 湿度={hum}%")
        else:
            print("\n単発テスト失敗")
        
        print("\n" + "="*50)
        
        # 連続テスト
        multiple_test(pin=4, count=3)
        
    except KeyboardInterrupt:
        print("\n\nテストを中断しました")
    except Exception as e:
        print(f"\nエラー: {e}")
    finally:
        GPIO.cleanup()
        print("GPIO設定をクリーンアップしました")
