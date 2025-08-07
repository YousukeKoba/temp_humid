#!/usr/bin/env python3
"""
DHT11 高精度テスト - pigpioライブラリ使用版
μs単位の精密制御でDHT11通信を行います
"""

try:
    import pigpio
    import time
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False
    print("警告: pigpioライブラリがインストールされていません")
    print("インストール方法:")
    print("  sudo apt update")
    print("  sudo apt install pigpio python3-pigpio")
    print("  sudo systemctl enable pigpiod")
    print("  sudo systemctl start pigpiod")

class DHT11_PreciseTiming:
    """pigpioを使用した高精度DHT11クラス"""
    
    def __init__(self, pin):
        if not PIGPIO_AVAILABLE:
            raise ImportError("pigpioライブラリが必要です")
        
        self.pin = pin
        self.pi = pigpio.pi()
        
        if not self.pi.connected:
            raise RuntimeError("pigpioデーモンに接続できません。'sudo systemctl start pigpiod'を実行してください")
        
        print(f"pigpio接続成功 (GPIO{pin})")
    
    def read_precise(self, debug=False):
        """高精度読み取り"""
        try:
            if debug:
                print(f"=== DHT11 高精度読み取り開始 (GPIO{self.pin}) ===")
            
            # 初期状態確認
            self.pi.set_mode(self.pin, pigpio.OUTPUT)
            self.pi.write(self.pin, 1)
            time.sleep(0.1)  # 安定化待機
            
            initial_state = self.pi.read(self.pin)
            if debug:
                print(f"初期状態: {'HIGH' if initial_state else 'LOW'}")
            
            # 開始信号送信（高精度）
            if not self._send_start_signal_precise(debug):
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
            humidity = bytes_data[0]     # 湿度整数部
            temperature = bytes_data[2]  # 温度整数部
            
            if debug:
                print(f"成功: 温度={temperature}°C, 湿度={humidity}%")
                print(f"生データ: {[hex(b) for b in bytes_data]}")
            
            return temperature, humidity, 'OK'
            
        except Exception as e:
            if debug:
                print(f"読み取りエラー: {e}")
            return None, None, f'ERROR_{str(e)}'
    
    def _send_start_signal_precise(self, debug=False):
        """高精度開始信号送信"""
        try:
            # 出力モード設定
            self.pi.set_mode(self.pin, pigpio.OUTPUT)
            
            # 18ms LOW信号
            self.pi.write(self.pin, 0)
            if debug:
                print("開始信号: 18ms LOW開始")
            time.sleep(0.018)  # 18ms
            
            # 40μs HIGH信号（高精度）
            self.pi.write(self.pin, 1)
            if debug:
                print("開始信号: 40μs HIGH開始")
            # pigpioのμs単位遅延
            self.pi.delay(40)  # 40μs 高精度
            
            # 入力モードに切り替え
            self.pi.set_mode(self.pin, pigpio.INPUT)
            self.pi.set_pull_up_down(self.pin, pigpio.PUD_UP)
            
            if debug:
                print("開始信号完了、入力モードに切り替え")
            
            return True
            
        except Exception as e:
            if debug:
                print(f"開始信号エラー: {e}")
            return False
    
    def _wait_response_precise(self, debug=False):
        """高精度応答信号待機"""
        timeout_us = 100000  # 100ms タイムアウト
        
        try:
            # DHT11応答: HIGH->LOW (80μs LOW) -> HIGH (80μs HIGH) -> LOW
            
            # 1. HIGH->LOW変化待機
            start_time = time.time()
            while self.pi.read(self.pin) == 1:
                if (time.time() - start_time) * 1000000 > timeout_us:
                    if debug:
                        print("応答1: HIGH->LOW変化タイムアウト")
                    return False
            
            # 2. LOW期間（約80μs）
            start_time = time.time()
            while self.pi.read(self.pin) == 0:
                if (time.time() - start_time) * 1000000 > timeout_us:
                    if debug:
                        print("応答2: LOW期間タイムアウト")
                    return False
            
            # 3. HIGH期間（約80μs）
            start_time = time.time()
            while self.pi.read(self.pin) == 1:
                if (time.time() - start_time) * 1000000 > timeout_us:
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
        timeout_us = 200  # 200μs タイムアウト
        
        try:
            for i in range(40):
                # LOW期間待機（50μs）
                start_time = time.time()
                while self.pi.read(self.pin) == 0:
                    if (time.time() - start_time) * 1000000 > timeout_us:
                        if debug:
                            print(f"ビット{i}: LOW期間タイムアウト")
                        return bits
                
                # HIGH期間測定
                high_start = time.time()
                while self.pi.read(self.pin) == 1:
                    if (time.time() - high_start) * 1000000 > timeout_us:
                        if debug:
                            print(f"ビット{i}: HIGH期間タイムアウト")
                        return bits
                
                high_duration = (time.time() - high_start) * 1000000  # μs
                
                # ビット判定: 26-28μs=0, 70μs=1
                bit_value = 1 if high_duration > 40 else 0
                bits.append(bit_value)
                
                if debug and (i < 10 or i >= 35):
                    print(f"ビット{i}: {high_duration:.1f}μs -> {bit_value}")
            
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
            self.pi.stop()

def test_pigpio_installation():
    """pigpio環境テスト"""
    print("=== pigpio環境確認 ===")
    
    if not PIGPIO_AVAILABLE:
        print("✗ pigpioライブラリ未インストール")
        return False
    
    try:
        pi = pigpio.pi()
        if pi.connected:
            print("✓ pigpioデーモン接続成功")
            pi.stop()
            return True
        else:
            print("✗ pigpioデーモン未起動")
            print("解決方法: sudo systemctl start pigpiod")
            return False
    except Exception as e:
        print(f"✗ pigpio接続エラー: {e}")
        return False

def test_precision_comparison():
    """精度比較テスト"""
    print("\n=== タイミング精度比較 ===")
    
    print("1. time.sleep()の精度テスト")
    for target_us in [40, 100, 500]:
        actual_times = []
        for _ in range(10):
            start = time.time()
            time.sleep(target_us / 1000000)  # μs to seconds
            actual = (time.time() - start) * 1000000  # μs
            actual_times.append(actual)
        
        avg_time = sum(actual_times) / len(actual_times)
        print(f"  目標: {target_us}μs, 実測平均: {avg_time:.1f}μs (誤差: {avg_time-target_us:+.1f}μs)")
    
    if PIGPIO_AVAILABLE:
        print("\n2. pigpio.delay()の精度テスト")
        try:
            pi = pigpio.pi()
            if pi.connected:
                for target_us in [40, 100, 500]:
                    actual_times = []
                    for _ in range(10):
                        start = time.time()
                        pi.delay(target_us)
                        actual = (time.time() - start) * 1000000
                        actual_times.append(actual)
                    
                    avg_time = sum(actual_times) / len(actual_times)
                    print(f"  目標: {target_us}μs, 実測平均: {avg_time:.1f}μs (誤差: {avg_time-target_us:+.1f}μs)")
                
                pi.stop()
        except Exception as e:
            print(f"pigpio精度テストエラー: {e}")

def main():
    """メインテスト"""
    print("DHT11 高精度テスト (pigpio版)")
    print("=" * 50)
    
    # 環境確認
    if not test_pigpio_installation():
        print("\npigpio環境を整備してから再実行してください")
        return
    
    # 精度比較
    test_precision_comparison()
    
    print("\n" + "=" * 50)
    print("DHT11センサーテスト開始")
    
    try:
        sensor = DHT11_PreciseTiming(4)
        
        # 単発テスト
        print("\n=== 高精度単発テスト ===")
        temp, humidity, status = sensor.read_precise(debug=True)
        
        if status == 'OK':
            print(f"✓ 成功: 温度={temp}°C, 湿度={humidity}%")
        else:
            print(f"✗ 失敗: {status}")
        
        # 連続テスト
        print("\n=== 高精度連続テスト (5回) ===")
        success_count = 0
        
        for i in range(5):
            print(f"\n--- テスト {i+1}/5 ---")
            temp, humidity, status = sensor.read_precise(debug=False)
            
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
            print("✓ pigpio使用で大幅改善！")
        elif success_count >= 2:
            print("△ 部分的改善（ハードウェア要確認）")
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
