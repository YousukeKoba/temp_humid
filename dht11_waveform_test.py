#!/usr/bin/env python3
"""
DHT11 波形制御版 - pigpioの波形機能を使用
最高精度でDHT11通信を行います
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False

class DHT11_Waveform:
    """pigpio波形制御を使用したDHT11クラス"""
    
    def __init__(self, pin):
        if not PIGPIO_AVAILABLE:
            raise ImportError("pigpioライブラリが必要です")
        
        self.pin = pin
        self.pi = pigpio.pi()
        
        if not self.pi.connected:
            raise RuntimeError("pigpioデーモンに接続できません")
        
        print(f"pigpio波形制御 接続成功 (GPIO{pin})")
    
    def read_waveform(self, debug=False):
        """波形制御による高精度読み取り"""
        try:
            if debug:
                print(f"=== DHT11 波形制御読み取り開始 (GPIO{self.pin}) ===")
            
            # 開始信号を波形で送信
            if not self._send_start_waveform(debug):
                return None, None, 'START_SIGNAL_FAILED'
            
            # 応答信号確認
            if not self._wait_response_precise(debug):
                return None, None, 'NO_RESPONSE'
            
            # データ読み取り
            bits = self._read_data_precise(debug)
            if not bits or len(bits) < 40:
                return None, None, f'READ_ERROR_{len(bits) if bits else 0}_BITS'
            
            # データ変換
            bytes_data = self._bits_to_bytes(bits[:40])
            
            # チェックサム確認
            checksum = (bytes_data[0] + bytes_data[1] + bytes_data[2] + bytes_data[3]) & 0xFF
            if checksum != bytes_data[4]:
                if debug:
                    print(f"チェックサムエラー: 計算={checksum:02x}, 受信={bytes_data[4]:02x}")
                    print(f"バイトデータ: {[hex(b) for b in bytes_data]}")
                return None, None, 'CHECKSUM_ERROR'
            
            # DHT11データ抽出
            humidity = bytes_data[0]
            temperature = bytes_data[2]
            
            if debug:
                print(f"成功: 温度={temperature}°C, 湿度={humidity}%")
            
            return temperature, humidity, 'OK'
            
        except Exception as e:
            if debug:
                print(f"読み取りエラー: {e}")
            return None, None, f'ERROR_{str(e)}'
    
    def _send_start_waveform(self, debug=False):
        """波形による開始信号送信"""
        try:
            # 波形定義
            # 18ms LOW + 40μs HIGH
            waveform = []
            
            # 18ms LOW (18000μs)
            waveform.append(pigpio.pulse(0, 1<<self.pin, 18000))
            
            # 40μs HIGH
            waveform.append(pigpio.pulse(1<<self.pin, 0, 40))
            
            # 波形をクリア
            self.pi.wave_clear()
            
            # 波形を追加
            self.pi.wave_add_generic(waveform)
            
            # 波形を作成
            wave_id = self.pi.wave_create()
            if wave_id < 0:
                if debug:
                    print(f"波形作成失敗: {wave_id}")
                return False
            
            # 初期状態設定（HIGH）
            self.pi.write(self.pin, 1)
            time.sleep(0.1)  # 安定化
            
            if debug:
                print("波形による開始信号送信中...")
            
            # 波形送信
            self.pi.wave_send_once(wave_id)
            
            # 波形送信完了まで待機
            while self.pi.wave_tx_busy():
                time.sleep(0.001)
            
            # 波形削除
            self.pi.wave_delete(wave_id)
            
            # 入力モードに切り替え
            self.pi.set_mode(self.pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.pin, pigpio.PUD_UP)
            
            if debug:
                print("波形送信完了、入力モードに切り替え")
            
            return True
            
        except Exception as e:
            if debug:
                print(f"波形送信エラー: {e}")
            return False
    
    def _wait_response_precise(self, debug=False):
        """応答信号待機"""
        timeout_us = 100000  # 100ms
        
        try:
            # DHT11応答待機
            start_time = self.pi.get_tick()
            
            # HIGH->LOW変化待機
            while self.pi.read(self.pin) == 1:
                if (self.pi.get_tick() - start_time) > timeout_us:
                    if debug:
                        print("応答1: HIGH->LOW変化タイムアウト")
                    return False
            
            # LOW期間
            start_time = self.pi.get_tick()
            while self.pi.read(self.pin) == 0:
                if (self.pi.get_tick() - start_time) > timeout_us:
                    if debug:
                        print("応答2: LOW期間タイムアウト")
                    return False
            
            # HIGH期間
            start_time = self.pi.get_tick()
            while self.pi.read(self.pin) == 1:
                if (self.pi.get_tick() - start_time) > timeout_us:
                    if debug:
                        print("応答3: HIGH期間タイムアウト")
                    return False
            
            if debug:
                print("応答信号: 正常検出")
            return True
            
        except Exception as e:
            if debug:
                print(f"応答信号エラー: {e}")
            return False
    
    def _read_data_precise(self, debug=False):
        """高精度データ読み取り"""
        bits = []
        timeout_us = 200  # 200μs
        
        try:
            for i in range(40):
                # LOW期間待機
                start_time = self.pi.get_tick()
                while self.pi.read(self.pin) == 0:
                    if (self.pi.get_tick() - start_time) > timeout_us:
                        if debug:
                            print(f"ビット{i}: LOW期間タイムアウト")
                        return bits
                
                # HIGH期間測定
                high_start = self.pi.get_tick()
                while self.pi.read(self.pin) == 1:
                    if (self.pi.get_tick() - high_start) > timeout_us:
                        if debug:
                            print(f"ビット{i}: HIGH期間タイムアウト")
                        return bits
                
                high_duration = self.pi.get_tick() - high_start
                
                # ビット判定
                bit_value = 1 if high_duration > 40 else 0
                bits.append(bit_value)
                
                if debug and (i < 10 or i >= 35):
                    print(f"ビット{i}: {high_duration}μs -> {bit_value}")
            
            if debug:
                print(f"データ読み取り完了: 40ビット")
            return bits
            
        except Exception as e:
            if debug:
                print(f"データ読み取りエラー: {e}")
            return bits
    
    def _bits_to_bytes(self, bits):
        """ビット→バイト変換"""
        bytes_data = []
        for i in range(5):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) + bits[i * 8 + j]
            bytes_data.append(byte_val)
        return bytes_data
    
    def cleanup(self):
        """リソース解放"""
        if hasattr(self, 'pi'):
            self.pi.wave_clear()
            self.pi.stop()

def test_waveform_precision():
    """波形精度テスト"""
    print("=== pigpio波形精度テスト ===")
    
    if not PIGPIO_AVAILABLE:
        print("pigpio未インストール")
        return
    
    try:
        pi = pigpio.pi()
        if not pi.connected:
            print("pigpioデーモン未接続")
            return
        
        test_pin = 4
        
        # テスト用波形
        test_durations = [40, 100, 500, 1000]  # μs
        
        for duration in test_durations:
            print(f"\n{duration}μs パルステスト:")
            
            # 波形定義
            waveform = [
                pigpio.pulse(1<<test_pin, 0, duration),  # HIGH
                pigpio.pulse(0, 1<<test_pin, duration),  # LOW
            ]
            
            # 波形作成
            pi.wave_clear()
            pi.wave_add_generic(waveform)
            wave_id = pi.wave_create()
            
            if wave_id >= 0:
                # 測定
                measured_times = []
                for _ in range(5):
                    start = time.time()
                    pi.wave_send_once(wave_id)
                    while pi.wave_tx_busy():
                        pass
                    measured = (time.time() - start) * 1000000 / 2  # 半分（片方向）
                    measured_times.append(measured)
                
                avg_time = sum(measured_times) / len(measured_times)
                print(f"  目標: {duration}μs, 実測平均: {avg_time:.1f}μs")
                
                pi.wave_delete(wave_id)
            else:
                print(f"  波形作成失敗: {wave_id}")
        
        pi.stop()
        
    except Exception as e:
        print(f"波形精度テストエラー: {e}")

def main():
    """メインテスト"""
    print("DHT11 波形制御版テスト")
    print("=" * 50)
    
    # 波形精度テスト
    test_waveform_precision()
    
    print("\n" + "=" * 50)
    print("DHT11センサーテスト開始")
    
    try:
        sensor = DHT11_Waveform(4)
        
        # 単発テスト
        print("\n=== 波形制御単発テスト ===")
        temp, humidity, status = sensor.read_waveform(debug=True)
        
        if status == 'OK':
            print(f"✓ 成功: 温度={temp}°C, 湿度={humidity}%")
        else:
            print(f"✗ 失敗: {status}")
        
        # 連続テスト
        print("\n=== 波形制御連続テスト (5回) ===")
        success_count = 0
        
        for i in range(5):
            print(f"\n--- テスト {i+1}/5 ---")
            temp, humidity, status = sensor.read_waveform(debug=False)
            
            if status == 'OK':
                print(f"✓ 成功: 温度={temp}°C, 湿度={humidity}%")
                success_count += 1
            else:
                print(f"✗ 失敗: {status}")
            
            if i < 4:
                time.sleep(2.5)
        
        print(f"\n=== 結果 ===")
        print(f"成功率: {success_count}/5 ({success_count*20}%)")
        
        if success_count >= 4:
            print("✓ 波形制御で高精度達成！")
        elif success_count >= 2:
            print("△ 改善あり（ハードウェア要確認）")
        else:
            print("✗ ハードウェア問題が主因")
        
    except Exception as e:
        print(f"テストエラー: {e}")
    finally:
        try:
            sensor.cleanup()
        except:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nテスト中断")
