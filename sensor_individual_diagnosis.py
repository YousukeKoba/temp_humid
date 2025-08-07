#!/usr/bin/env python3
"""
DHT11センサー個体診断テスト
プルアップ抵抗とセンサー個体の問題を切り分けます
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

def test_pullup_resistance():
    """プルアップ抵抗の動作確認"""
    print("=== プルアップ抵抗動作確認 ===")
    
    if not PIGPIO_AVAILABLE:
        print("pigpio未インストール")
        return False
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            print("pigpioデーモン未接続")
            return False
        
        pin = 4
        
        # 1. 出力モードでLOWに設定
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 0)
        time.sleep(0.1)
        
        # 2. 入力モードに切り替え（プルアップなし）
        pi.set_mode(pin, pigpio.INPUT)
        
        # 3. プルアップ抵抗による立ち上がり時間測定
        start_time = time.time()
        
        # HIGHになるまでの時間を測定
        while pi.read(pin) == 0:
            if (time.time() - start_time) > 0.001:  # 1ms タイムアウト
                break
        
        pullup_time = (time.time() - start_time) * 1000000  # μs
        final_state = pi.read(pin)
        
        print(f"プルアップ立ち上がり時間: {pullup_time:.1f}μs")
        print(f"最終状態: {'HIGH' if final_state else 'LOW'}")
        
        # 判定
        if final_state == 1:
            if pullup_time < 100:  # 100μs以下
                print("✓ プルアップ抵抗: 正常動作 (4.7kΩ想定)")
                return True
            elif pullup_time < 500:  # 500μs以下
                print("△ プルアップ抵抗: 弱い (10kΩ以上の可能性)")
                return True
            else:
                print("✗ プルアップ抵抗: 不十分 (内蔵プルアップのみ)")
                return False
        else:
            print("✗ プルアップ抵抗: 機能していない")
            return False
            
        pi.stop()
        
    except Exception as e:
        print(f"プルアップテストエラー: {e}")
        return False

def test_sensor_communication_basic():
    """センサー基本通信テスト"""
    print("\n=== センサー基本通信テスト ===")
    
    if not PIGPIO_AVAILABLE:
        return False
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            return False
        
        pin = 4
        
        # 開始信号送信
        print("1. 開始信号送信...")
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 0)
        time.sleep(0.020)  # 20ms LOW
        pi.write(pin, 1)
        time.sleep(0.00005)  # 50μs HIGH
        
        # 入力モードに切り替え
        pi.set_mode(pin, pigpio.INPUT)
        
        # 応答確認
        print("2. センサー応答確認...")
        
        # 初期状態
        initial_state = pi.read(pin)
        print(f"   初期状態: {'HIGH' if initial_state else 'LOW'}")
        
        # HIGH->LOW変化待機 (1ms タイムアウト)
        start_time = time.time()
        response_detected = False
        
        while (time.time() - start_time) < 0.001:
            if pi.read(pin) == 0:
                response_detected = True
                break
        
        if response_detected:
            print("   ✓ センサー応答検出")
            
            # 応答パターンの詳細確認
            time.sleep(0.0001)  # 100μs待機
            mid_state = pi.read(pin)
            time.sleep(0.0001)  # さらに100μs待機
            later_state = pi.read(pin)
            
            print(f"   応答中の状態変化: {initial_state} -> 0 -> {mid_state} -> {later_state}")
            
            if mid_state == 1 or later_state == 1:
                print("   ✓ 応答パターン確認")
                return True
            else:
                print("   ✗ 応答パターン異常（LOWのまま）")
                return False
        else:
            print("   ✗ センサー応答なし")
            return False
            
        pi.stop()
        
    except Exception as e:
        print(f"基本通信テストエラー: {e}")
        return False

def test_multiple_pins():
    """複数ピンでのテスト"""
    print("\n=== 複数ピンテスト ===")
    
    test_pins = [4, 18, 17, 27, 22]
    working_pins = []
    
    if not PIGPIO_AVAILABLE:
        return []
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            return []
        
        for pin in test_pins:
            print(f"\nGPIO{pin}でテスト:")
            
            # 基本I/O確認
            pi.set_mode(pin, pigpio.OUTPUT)
            pi.write(pin, 1)
            time.sleep(0.01)
            state1 = pi.read(pin)
            
            pi.write(pin, 0)
            time.sleep(0.01)
            state2 = pi.read(pin)
            
            pi.set_mode(pin, pigpio.INPUT)
            time.sleep(0.01)
            state3 = pi.read(pin)
            
            print(f"  I/Oテスト: HIGH={state1}, LOW={state2}, INPUT={state3}")
            
            if state1 == 1 and state2 == 0:
                print(f"  ✓ GPIO{pin}: 基本動作OK")
                working_pins.append(pin)
            else:
                print(f"  ✗ GPIO{pin}: 基本動作NG")
        
        pi.stop()
        return working_pins
        
    except Exception as e:
        print(f"複数ピンテストエラー: {e}")
        return []

def sensor_diagnosis():
    """総合診断"""
    print("DHT11センサー個体診断")
    print("=" * 50)
    
    # 1. プルアップ抵抗確認
    pullup_ok = test_pullup_resistance()
    
    # 2. センサー通信確認
    sensor_ok = test_sensor_communication_basic()
    
    # 3. 複数ピン確認
    working_pins = test_multiple_pins()
    
    # 診断結果
    print("\n" + "=" * 50)
    print("診断結果")
    print("=" * 50)
    
    if pullup_ok and sensor_ok:
        print("✓ ハードウェア: 正常")
        print("  → ソフトウェア調整で解決可能")
    elif pullup_ok and not sensor_ok:
        print("✗ センサー個体: 不良の可能性大")
        print("  → DHT11センサーの交換推奨")
    elif not pullup_ok and not sensor_ok:
        print("✗ 配線問題: プルアップ抵抗未接続")
        print("  → 配線を再確認してください")
    else:
        print("△ 部分的問題: 詳細調査必要")
    
    print(f"\n動作確認済みGPIOピン: {working_pins}")
    
    if len(working_pins) > 1:
        alt_pin = [p for p in working_pins if p != 4][0]
        print(f"代替案: GPIO{alt_pin}でDHT11を試してください")
    
    # 推奨アクション
    print("\n推奨アクション:")
    if not pullup_ok:
        print("1. 4.7kΩ抵抗の配線を再確認")
        print("2. ブレッドボードの接触不良確認")
    
    if not sensor_ok:
        print("3. 別のDHT11センサーで試行")
        print("4. DHT22センサーへの交換検討")
        print("5. BME280(I2C)センサーへの変更検討")

if __name__ == "__main__":
    try:
        sensor_diagnosis()
    except KeyboardInterrupt:
        print("\n診断中断")
