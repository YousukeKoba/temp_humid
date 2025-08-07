#!/usr/bin/env python3
"""
DHT11 配線確認テスト
段階的に配線を確認します
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

def test_step_by_step():
    """段階的配線確認"""
    print("DHT11 段階的配線確認")
    print("=" * 40)
    
    if not PIGPIO_AVAILABLE:
        print("pigpio未インストール")
        return
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            print("pigpioデーモン未接続")
            return
        
        pin = 4
        
        print("\n=== ステップ1: 基本GPIO動作確認 ===")
        pi.set_mode(pin, pigpio.OUTPUT)
        
        pi.write(pin, 1)
        time.sleep(0.1)
        state1 = pi.read(pin)
        print(f"HIGH出力時の読み取り: {state1}")
        
        pi.write(pin, 0)
        time.sleep(0.1)
        state2 = pi.read(pin)
        print(f"LOW出力時の読み取り: {state2}")
        
        if state1 == 1 and state2 == 0:
            print("✓ GPIO基本動作: 正常")
        else:
            print("✗ GPIO基本動作: 異常")
            return
        
        print("\n=== ステップ2: プルアップなし状態確認 ===")
        pi.set_mode(pin, pigpio.INPUT)
        time.sleep(0.1)
        
        floating_state = pi.read(pin)
        print(f"フローティング状態: {floating_state}")
        print("（プルアップ抵抗がないと不定になります）")
        
        print("\n=== ステップ3: 内蔵プルアップでの確認 ===")
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_UP)
        time.sleep(0.1)
        
        pullup_state = pi.read(pin)
        print(f"内蔵プルアップ状態: {pullup_state}")
        
        if pullup_state == 1:
            print("✓ 内蔵プルアップ: 動作")
        else:
            print("✗ 内蔵プルアップ: 異常")
        
        print("\n=== ステップ4: DHT11接続確認 ===")
        print("以下を確認してください:")
        print("1. DHT11のVCCピンが3.3Vに接続されているか")
        print("2. DHT11のGNDピンがGNDに接続されているか")
        print("3. DHT11のDATAピンがGPIO4に接続されているか")
        print("4. ブレッドボードの接触不良がないか")
        
        input("\n確認完了後、Enterを押してください...")
        
        print("\n=== ステップ5: センサー生存確認 ===")
        # 内蔵プルアップを使用してセンサー応答を確認
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 0)
        time.sleep(0.020)  # 20ms LOW
        pi.write(pin, 1)
        time.sleep(0.00005)  # 50μs HIGH
        
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_UP)
        
        # 応答確認
        start_time = time.time()
        response_detected = False
        
        initial_state = pi.read(pin)
        print(f"開始信号送信後の初期状態: {initial_state}")
        
        # 1ms以内に応答があるかチェック
        while (time.time() - start_time) < 0.001:
            current_state = pi.read(pin)
            if current_state != initial_state:
                response_detected = True
                print(f"状態変化検出: {initial_state} -> {current_state}")
                break
        
        if response_detected:
            print("✓ DHT11センサー: 応答あり（生きている）")
            print("  → プルアップ抵抗を追加すれば動作する可能性大")
        else:
            print("✗ DHT11センサー: 応答なし")
            print("  → センサー個体不良またはVCC/GND配線問題")
        
        print("\n=== 最終判定 ===")
        if response_detected:
            print("センサーは生きています。")
            print("4.7kΩプルアップ抵抗を正しく配線してください：")
            print("  DHT11-DATA → 4.7kΩ抵抗 → Pi-3.3V")
        else:
            print("センサー個体またはVCC/GND配線に問題があります。")
            print("1. 電源配線を再確認")
            print("2. 別のDHT11センサーで試行")
        
        pi.stop()
        
    except Exception as e:
        print(f"テストエラー: {e}")

if __name__ == "__main__":
    try:
        test_step_by_step()
    except KeyboardInterrupt:
        print("\nテスト中断")
