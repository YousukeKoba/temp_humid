#!/usr/bin/env python3
"""
DHT11 詳細タイミング分析
実際のプロトコル波形を解析してタイミングの問題を特定
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

def analyze_dht11_timing():
    """詳細タイミング分析"""
    print("DHT11 詳細タイミング分析")
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
        
        print("\n=== 分析1: 開始信号の詳細確認 ===")
        
        # より正確な開始信号を送信
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 1)
        time.sleep(0.1)  # 安定化
        
        print("開始信号送信:")
        print("1. 18ms LOW送信")
        pi.write(pin, 0)
        time.sleep(0.018)  # 18ms LOW
        
        print("2. 20-40μs HIGH送信")
        pi.write(pin, 1)
        time.sleep(0.000030)  # 30μs HIGH
        
        print("3. INPUT モードに切り替え")
        pi.set_mode(pin, pigpio.INPUT)
        # プルアップ抵抗があるので内蔵プルアップは使わない
        
        print("\n=== 分析2: 応答タイミング測定 ===")
        
        # 詳細な応答タイミングを測定
        measurements = []
        start_time = time.time()
        last_state = pi.read(pin)
        state_changes = []
        
        # 最初の10ms間の状態変化を記録
        timeout = 0.010  # 10ms
        while (time.time() - start_time) < timeout:
            current_state = pi.read(pin)
            current_time = time.time()
            
            if current_state != last_state:
                duration = (current_time - start_time) * 1000000  # μs
                state_changes.append({
                    'time_us': duration,
                    'from_state': last_state,
                    'to_state': current_state
                })
                print(f"  {duration:6.1f}μs: {last_state} → {current_state}")
                last_state = current_state
        
        print(f"\n検出された状態変化数: {len(state_changes)}")
        
        if len(state_changes) == 0:
            print("❌ DHT11からの応答が全くありません")
            print("考えられる問題:")
            print("  - プルアップ抵抗の配線が正しくない")
            print("  - センサーの電源が正しく供給されていない")
            print("  - 開始信号のタイミングが不適切")
            
        elif len(state_changes) >= 2:
            print("✅ DHT11応答検出!")
            
            # DHT11のプロトコル分析
            if state_changes[0]['from_state'] == 1 and state_changes[0]['to_state'] == 0:
                response_low_start = state_changes[0]['time_us']
                print(f"応答開始（HIGH→LOW）: {response_low_start:.1f}μs")
                
                if len(state_changes) >= 2 and state_changes[1]['to_state'] == 1:
                    response_low_duration = state_changes[1]['time_us'] - response_low_start
                    print(f"応答LOW期間: {response_low_duration:.1f}μs")
                    
                    # 標準的なDHT11の応答タイミング
                    if 70 <= response_low_duration <= 90:
                        print("✅ 応答LOW期間: 正常（80μs期待値）")
                    else:
                        print(f"⚠️  応答LOW期間: 異常（80μs期待、実測{response_low_duration:.1f}μs）")
                    
                    if len(state_changes) >= 3:
                        response_high_duration = state_changes[2]['time_us'] - state_changes[1]['time_us']
                        print(f"応答HIGH期間: {response_high_duration:.1f}μs")
                        
                        if 70 <= response_high_duration <= 90:
                            print("✅ 応答HIGH期間: 正常（80μs期待値）")
                        else:
                            print(f"⚠️  応答HIGH期間: 異常（80μs期待、実測{response_high_duration:.1f}μs）")
        
        print("\n=== 分析3: 完全データ読み取り試行 ===")
        
        # 完全なデータ読み取りを試行
        print("完全なDHT11読み取りを実行...")
        
        # 開始信号
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 1)
        time.sleep(0.1)
        pi.write(pin, 0)
        time.sleep(0.018)
        pi.write(pin, 1)
        time.sleep(0.000030)
        pi.set_mode(pin, pigpio.INPUT)
        
        # データビット読み取り
        bits = []
        bit_count = 0
        
        # 応答待ち
        start_time = time.time()
        while pi.read(pin) == 1 and (time.time() - start_time) < 0.001:
            pass
        
        if pi.read(pin) == 0:
            print("応答LOW検出")
            
            # 応答LOW待ち
            while pi.read(pin) == 0 and (time.time() - start_time) < 0.002:
                pass
            
            if pi.read(pin) == 1:
                print("応答HIGH検出")
                
                # 応答HIGH待ち
                while pi.read(pin) == 1 and (time.time() - start_time) < 0.003:
                    pass
                
                # データビット読み取り
                for i in range(40):
                    # LOW待ち
                    low_start = time.time()
                    while pi.read(pin) == 0 and (time.time() - low_start) < 0.0001:
                        pass
                    
                    if pi.read(pin) == 1:
                        # HIGH期間測定
                        high_start = time.time()
                        while pi.read(pin) == 1 and (time.time() - high_start) < 0.0001:
                            pass
                        
                        high_duration = (time.time() - high_start) * 1000000
                        
                        if high_duration > 40:  # 40μs以上なら'1'
                            bits.append('1')
                        else:
                            bits.append('0')
                        
                        bit_count += 1
                        
                        if bit_count % 8 == 0:
                            byte_str = ''.join(bits[-8:])
                            byte_val = int(byte_str, 2)
                            print(f"バイト{bit_count//8}: {byte_str} = {byte_val}")
                    else:
                        print(f"ビット{i}でHIGH検出失敗")
                        break
                
                print(f"\n読み取り完了: {bit_count}/40 ビット")
                
                if bit_count == 40:
                    # チェックサム検証
                    bytes_data = []
                    for j in range(5):
                        byte_bits = bits[j*8:(j+1)*8]
                        byte_val = int(''.join(byte_bits), 2)
                        bytes_data.append(byte_val)
                    
                    humidity = bytes_data[0]
                    temperature = bytes_data[2]
                    checksum = bytes_data[4]
                    calculated_checksum = (bytes_data[0] + bytes_data[1] + bytes_data[2] + bytes_data[3]) & 0xFF
                    
                    print(f"湿度: {humidity}%")
                    print(f"温度: {temperature}°C")
                    print(f"チェックサム: {checksum} (計算値: {calculated_checksum})")
                    
                    if checksum == calculated_checksum:
                        print("✅ チェックサム: 正常")
                        print("🎉 DHT11読み取り成功!")
                    else:
                        print("❌ チェックサム: エラー")
                else:
                    print("❌ データ読み取り不完全")
            else:
                print("応答HIGH検出失敗")
        else:
            print("応答LOW検出失敗")
        
        pi.stop()
        
    except Exception as e:
        print(f"分析エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        analyze_dht11_timing()
    except KeyboardInterrupt:
        print("\n分析中断")
