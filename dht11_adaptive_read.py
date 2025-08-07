#!/usr/bin/env python3
"""
DHT11 適応的読み取りツール
タイミングに適応して読み取りを行います
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

def adaptive_dht11_read():
    """適応的DHT11読み取り"""
    print("DHT11 適応的読み取りツール")
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
        
        print("\n=== 診断1: プルアップ抵抗値の推定 ===")
        
        # プルアップ抵抗値の推定（立ち上がり時間から）
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 0)
        time.sleep(0.001)
        
        # 立ち上がり時間測定
        pi.write(pin, 1)
        pi.set_mode(pin, pigpio.INPUT)
        
        start_time = time.time()
        while pi.read(pin) == 0 and (time.time() - start_time) < 0.001:
            pass
        
        rise_time = (time.time() - start_time) * 1000000
        print(f"立ち上がり時間: {rise_time:.1f}μs")
        
        if rise_time < 10:
            print("推定: 適切なプルアップ抵抗（1-10kΩ）")
            resistance_ok = True
        elif rise_time < 50:
            print("推定: 弱いプルアップ抵抗（10-47kΩ）")
            resistance_ok = True
        else:
            print("推定: プルアップ抵抗なしまたは極大値（>47kΩ）")
            resistance_ok = False
        
        print("\n=== 診断2: 適応的タイミング測定 ===")
        
        # より長いウェイト時間で試行
        for wait_time in [0.5, 1.0, 2.0]:
            print(f"\n安定化時間 {wait_time}s で試行:")
            
            # 安定化
            pi.set_mode(pin, pigpio.OUTPUT)
            pi.write(pin, 1)
            time.sleep(wait_time)
            
            # 開始信号
            pi.write(pin, 0)
            time.sleep(0.018)  # 18ms
            pi.write(pin, 1)
            time.sleep(0.000030)  # 30μs
            pi.set_mode(pin, pigpio.INPUT)
            
            # 応答測定
            state_changes = []
            start_time = time.time()
            last_state = pi.read(pin)
            
            timeout = 0.015  # 15ms
            while (time.time() - start_time) < timeout:
                current_state = pi.read(pin)
                current_time = time.time()
                
                if current_state != last_state:
                    duration = (current_time - start_time) * 1000000
                    state_changes.append({
                        'time_us': duration,
                        'from_state': last_state,
                        'to_state': current_state
                    })
                    last_state = current_state
                    
                    if len(state_changes) >= 10:  # 最初の10変化で十分
                        break
            
            print(f"  検出された状態変化数: {len(state_changes)}")
            
            if len(state_changes) >= 3:
                print("  最初の3つの変化:")
                for i, change in enumerate(state_changes[:3]):
                    print(f"    {i+1}. {change['time_us']:6.1f}μs: {change['from_state']} → {change['to_state']}")
                
                # DHT11プロトコル分析
                if (len(state_changes) >= 2 and 
                    state_changes[0]['from_state'] == 1 and state_changes[0]['to_state'] == 0 and
                    state_changes[1]['from_state'] == 0 and state_changes[1]['to_state'] == 1):
                    
                    response_start = state_changes[0]['time_us']
                    low_duration = state_changes[1]['time_us'] - state_changes[0]['time_us']
                    
                    print(f"  応答開始: {response_start:.1f}μs")
                    print(f"  LOW期間: {low_duration:.1f}μs")
                    
                    if response_start < 100:
                        print("  ✅ 応答開始: 正常（<100μs）")
                        timing_good = True
                    else:
                        print(f"  ⚠️  応答開始: 遅延（{response_start:.1f}μs）")
                        timing_good = False
                    
                    if 40 <= low_duration <= 120:
                        print("  ✅ LOW期間: 正常範囲")
                    else:
                        print(f"  ⚠️  LOW期間: 異常（期待40-120μs、実測{low_duration:.1f}μs）")
                    
                    if timing_good and len(state_changes) >= 3:
                        print("  → この設定で完全読み取りを試行")
                        success = attempt_full_read(pi, pin, wait_time)
                        if success:
                            break
            else:
                print("  応答不十分")
        
        pi.stop()
        
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

def attempt_full_read(pi, pin, stabilize_time):
    """完全データ読み取り試行"""
    print(f"\n=== 完全読み取り試行（安定化時間{stabilize_time}s）===")
    
    try:
        # 安定化
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.write(pin, 1)
        time.sleep(stabilize_time)
        
        # 開始信号
        pi.write(pin, 0)
        time.sleep(0.018)
        pi.write(pin, 1)
        time.sleep(0.000030)
        pi.set_mode(pin, pigpio.INPUT)
        
        # 応答待ち（適応的タイムアウト）
        start_time = time.time()
        
        # 応答LOW待ち
        timeout = 0.001  # 1ms
        while pi.read(pin) == 1 and (time.time() - start_time) < timeout:
            pass
        
        if pi.read(pin) != 0:
            print("応答LOW検出失敗")
            return False
        
        print("応答LOW検出")
        
        # 応答LOW終了待ち
        low_start = time.time()
        while pi.read(pin) == 0 and (time.time() - low_start) < 0.0002:  # 200μs
            pass
        
        if pi.read(pin) != 1:
            print("応答HIGH検出失敗")
            return False
        
        print("応答HIGH検出")
        
        # 応答HIGH終了待ち
        high_start = time.time()
        while pi.read(pin) == 1 and (time.time() - high_start) < 0.0002:  # 200μs
            pass
        
        if pi.read(pin) != 0:
            print("データ開始検出失敗")
            return False
        
        print("データ開始検出")
        
        # データビット読み取り（適応的タイミング）
        bits = []
        
        for bit_index in range(40):
            # LOW期間待ち
            low_start = time.time()
            while pi.read(pin) == 0 and (time.time() - low_start) < 0.0001:  # 100μs
                pass
            
            if pi.read(pin) != 1:
                print(f"ビット{bit_index}: HIGH検出失敗")
                break
            
            # HIGH期間測定
            high_start = time.time()
            while pi.read(pin) == 1 and (time.time() - high_start) < 0.0001:  # 100μs
                pass
            
            high_duration = (time.time() - high_start) * 1000000
            
            # ビット判定（適応的閾値）
            if high_duration > 35:  # 35μs以上で'1'
                bits.append('1')
            else:
                bits.append('0')
            
            # 8ビットごとに表示
            if (bit_index + 1) % 8 == 0:
                byte_bits = bits[-8:]
                byte_str = ''.join(byte_bits)
                byte_val = int(byte_str, 2)
                print(f"バイト{(bit_index + 1)//8}: {byte_str} = {byte_val}")
        
        print(f"読み取り完了: {len(bits)}/40 ビット")
        
        if len(bits) == 40:
            # データ解析
            bytes_data = []
            for i in range(5):
                byte_bits = bits[i*8:(i+1)*8]
                byte_val = int(''.join(byte_bits), 2)
                bytes_data.append(byte_val)
            
            humidity_int = bytes_data[0]
            humidity_dec = bytes_data[1]
            temp_int = bytes_data[2]
            temp_dec = bytes_data[3]
            checksum = bytes_data[4]
            
            calculated_checksum = (bytes_data[0] + bytes_data[1] + bytes_data[2] + bytes_data[3]) & 0xFF
            
            print(f"\n--- データ解析 ---")
            print(f"湿度: {humidity_int}.{humidity_dec}%")
            print(f"温度: {temp_int}.{temp_dec}°C")
            print(f"チェックサム: {checksum} (計算値: {calculated_checksum})")
            
            if checksum == calculated_checksum:
                print("✅ チェックサム: 正常")
                print("🎉 DHT11読み取り成功!")
                return True
            else:
                print("❌ チェックサム: エラー")
                print("タイミングは正常だが、ノイズまたは配線問題の可能性")
                return False
        else:
            print("❌ データ読み取り不完全")
            return False
            
    except Exception as e:
        print(f"読み取りエラー: {e}")
        return False

if __name__ == "__main__":
    try:
        adaptive_dht11_read()
    except KeyboardInterrupt:
        print("\n読み取り中断")
