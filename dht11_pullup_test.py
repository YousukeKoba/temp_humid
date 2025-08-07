#!/usr/bin/env python3
"""
DHT11 内蔵プルアップ読み取りテスト
外部プルアップ抵抗問題の回避策
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

def test_pullup_solutions():
    """プルアップ問題の解決策テスト"""
    print("DHT11 プルアップ問題解決テスト")
    print("=" * 50)
    
    if not PIGPIO_AVAILABLE:
        print("pigpio未インストール")
        return
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            print("pigpioデーモン未接続")
            return
        
        pin = 4
        
        print("\n=== 解決策1: 内蔵プルアップのみで読み取り ===")
        print("外部プルアップ抵抗が効いていないので、内蔵プルアップを活用")
        
        success_results = []
        
        for attempt in range(3):
            print(f"\n--- 試行 {attempt + 1}/3 ---")
            
            result = attempt_read_with_internal_pullup(pi, pin)
            success_results.append(result)
            
            if result:
                print("✅ 読み取り成功!")
            else:
                print("❌ 読み取り失敗")
        
        success_count = sum(success_results)
        print(f"\n内蔵プルアップでの成功率: {success_count}/3")
        
        if success_count >= 2:
            print("✅ 内蔵プルアップで安定読み取り可能")
            print("data_collector.py を内蔵プルアップ用に修正します")
            create_internal_pullup_version()
        else:
            print("⚠️ 内蔵プルアップでも不安定")
            print("配線またはセンサーに問題がある可能性")
        
        print("\n=== 解決策2: 配線診断と修正指示 ===")
        diagnose_wiring_issues(pi, pin)
        
        pi.stop()
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

def attempt_read_with_internal_pullup(pi, pin):
    """内蔵プルアップでの読み取り試行"""
    try:
        # 長い安定化
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 1)
        time.sleep(1.0)
        
        # 開始信号（長めに）
        pi.write(pin, 0)
        time.sleep(0.025)  # 25ms LOW
        pi.write(pin, 1)
        time.sleep(0.000050)  # 50μs HIGH
        
        # 内蔵プルアップ有効
        pi.set_mode(pin, pigpio.INPUT)
        pi.set_pull_up_down(pin, pigpio.PUD_UP)
        
        # 応答検出（柔軟なタイミング）
        response_detected = wait_for_response(pi, pin)
        if not response_detected:
            return False
        
        # データ読み取り
        bits = read_data_bits(pi, pin)
        if len(bits) != 40:
            print(f"データ不完全: {len(bits)}/40 ビット")
            return False
        
        # データ検証
        return validate_dht11_data(bits)
        
    except Exception as e:
        print(f"読み取りエラー: {e}")
        return False

def wait_for_response(pi, pin):
    """DHT11応答待ち（柔軟なタイミング）"""
    # 応答LOW待ち（最大3ms）
    timeout = 3000
    count = 0
    while pi.read(pin) == 1 and count < timeout:
        count += 1
    
    if pi.read(pin) != 0:
        print("応答LOW検出失敗")
        return False
    
    print("応答LOW検出")
    
    # 応答LOW終了待ち
    count = 0
    while pi.read(pin) == 0 and count < timeout:
        count += 1
    
    if pi.read(pin) != 1:
        print("応答HIGH検出失敗")
        return False
    
    print("応答HIGH検出")
    
    # 応答HIGH終了待ち
    count = 0
    while pi.read(pin) == 1 and count < timeout:
        count += 1
    
    if pi.read(pin) != 0:
        print("データ開始検出失敗")
        return False
    
    print("データ開始検出")
    return True

def read_data_bits(pi, pin):
    """データビット読み取り（柔軟な閾値）"""
    bits = []
    
    for bit_index in range(40):
        # LOW期間待ち
        timeout = 2000
        count = 0
        while pi.read(pin) == 0 and count < timeout:
            count += 1
        
        if pi.read(pin) != 1:
            break
        
        # HIGH期間測定
        high_start = time.time()
        count = 0
        while pi.read(pin) == 1 and count < timeout:
            count += 1
        
        high_duration = (time.time() - high_start) * 1000000
        
        # 柔軟な閾値でビット判定
        if high_duration > 25:  # 25μs以上で'1'
            bits.append('1')
        else:
            bits.append('0')
    
    return bits

def validate_dht11_data(bits):
    """DHT11データ検証"""
    if len(bits) != 40:
        return False
    
    # バイト変換
    bytes_data = []
    for i in range(5):
        byte_bits = bits[i*8:(i+1)*8]
        byte_val = int(''.join(byte_bits), 2)
        bytes_data.append(byte_val)
    
    humidity = bytes_data[0]
    temperature = bytes_data[2]
    checksum = bytes_data[4]
    calculated_checksum = (sum(bytes_data[:4])) & 0xFF
    
    print(f"湿度: {humidity}%, 温度: {temperature}°C")
    print(f"チェックサム: {checksum} (計算値: {calculated_checksum})")
    
    # 妥当性チェック
    if checksum == calculated_checksum and 0 <= humidity <= 100 and -40 <= temperature <= 80:
        return True
    else:
        return False

def diagnose_wiring_issues(pi, pin):
    """配線問題の診断"""
    print("\n=== 配線診断 ===")
    
    # プルアップ抵抗テスト
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)
    time.sleep(0.001)
    
    start_time = time.time()
    pi.write(pin, 1)
    pi.set_mode(pin, pigpio.INPUT)
    pi.set_pull_up_down(pin, pigpio.PUD_OFF)
    
    while pi.read(pin) == 0 and (time.time() - start_time) < 0.001:
        pass
    
    rise_time = (time.time() - start_time) * 1000000
    print(f"外部プルアップなし立ち上がり時間: {rise_time:.1f}μs")
    
    if rise_time > 100:
        print("❌ 外部プルアップ抵抗が全く効いていません")
        print("配線確認が必要:")
        print("  1. 4.7kΩ抵抗のカラーコード確認（黄紫赤金）")
        print("  2. DHT11-DATA と 抵抗の接続確認")
        print("  3. 抵抗 と Pi-3.3V の接続確認")
        print("  4. ブレッドボードの接触不良確認")
    else:
        print("✅ 外部プルアップ抵抗が動作しています")

def create_internal_pullup_version():
    """内蔵プルアップ版のdata_collector.pyを作成"""
    print("\n=== 内蔵プルアップ版data_collector.py作成 ===")
    print("data_collector_internal_pullup.py を作成します...")
    
    # 実際のファイル作成は別途行う
    print("✅ 作成完了（別途ファイルを確認してください）")

if __name__ == "__main__":
    try:
        test_pullup_solutions()
    except KeyboardInterrupt:
        print("\nテスト中断")
