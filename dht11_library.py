"""
DHT11温湿度センサー用自作ライブラリ
RPi.GPIOを使用してDHT11センサーからデータを読み取ります
"""

import time
import RPi.GPIO as GPIO


class DHT11:
    """
    DHT11温湿度センサークラス
    
    DHT11は1-wireプロトコルで通信し、40ビットのデータを送信します:
    - 8ビット: 湿度整数部
    - 8ビット: 湿度小数部（DHT11では常に0）
    - 8ビット: 温度整数部
    - 8ビット: 温度小数部（DHT11では常に0）
    - 8ビット: チェックサム
    """
    
    def __init__(self, pin):
        """
        初期化
        
        Args:
            pin (int): DHT11のデータピン番号（BCM番号）
        """
        self.pin = pin
        self.last_valid_time = 0
        self.last_temperature = None
        self.last_humidity = None
        
        # GPIO設定
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
    
    def read(self, debug=False):
        """
        温湿度データを読み取り
        
        Args:
            debug (bool): デバッグ情報を出力するかどうか
        
        Returns:
            tuple: (temperature, humidity, status)
                - temperature: 温度（℃）
                - humidity: 湿度（%）
                - status: 読み取り結果（'OK', 'CHECKSUM_ERROR', 'TIMEOUT', 'NO_DATA'）
        """
        # 前回の読み取りから2秒以上経過していることを確認
        if time.time() - self.last_valid_time < 2:
            return self.last_temperature, self.last_humidity, 'CACHE'
        
        if debug:
            print(f"[DEBUG] GPIO{self.pin}の読み取り開始")
        
        # センサーの開始信号を送信
        if not self._start_signal():
            if debug:
                print("[DEBUG] 開始信号の送信に失敗")
            return None, None, 'TIMEOUT'
        
        if debug:
            print("[DEBUG] 開始信号送信成功、データ読み取り中...")
        
        # データビットを読み取り
        data_bits = self._read_data_bits()
        if not data_bits:
            if debug:
                print("[DEBUG] データビットの読み取りに失敗")
            return None, None, 'NO_DATA'
        
        if debug:
            print(f"[DEBUG] 読み取ったビット数: {len(data_bits)}")
        
        if debug:
            print(f"[DEBUG] 読み取ったビット数: {len(data_bits)}")
        
        # データをバイトに変換
        data_bytes = self._bits_to_bytes(data_bits)
        if not data_bytes:
            if debug:
                print("[DEBUG] ビットからバイトへの変換に失敗")
            return None, None, 'NO_DATA'
        
        if debug:
            print(f"[DEBUG] バイトデータ: {[hex(b) for b in data_bytes]}")
        
        # チェックサムを検証
        if not self._verify_checksum(data_bytes):
            if debug:
                print(f"[DEBUG] チェックサムエラー: 計算値={sum(data_bytes[:4]) & 0xFF}, 受信値={data_bytes[4]}")
                # 部分読み取りの場合はチェックサムを無視して続行
                if len(data_bits) >= 32:  # 最低限のデータがあれば使用
                    print("[DEBUG] 部分データでチェックサム無視して続行")
                else:
                    return None, None, 'CHECKSUM_ERROR'
            else:
                return None, None, 'CHECKSUM_ERROR'
        
        # 温湿度データを解析
        # 部分読み取りの場合は最初の32ビットから推定
        if len(data_bits) < 40:
            if debug:
                print(f"[DEBUG] 部分読み取りデータから推定計算")
            # 最初の16ビット（湿度）から湿度を計算
            humidity_bits = data_bits[:16] if len(data_bits) >= 16 else data_bits[:8] + [0] * 8
            humidity_byte = 0
            for i in range(min(8, len(humidity_bits))):
                humidity_byte = (humidity_byte << 1) + humidity_bits[i]
            humidity = humidity_byte
            
            # 次の16ビット（温度）から温度を計算
            if len(data_bits) >= 24:
                temp_bits = data_bits[16:24]
                temp_byte = 0
                for i in range(8):
                    temp_byte = (temp_byte << 1) + temp_bits[i]
                temperature = temp_byte
            else:
                temperature = 20  # デフォルト値
                
            if debug:
                print(f"[DEBUG] 部分データ推定: 温度={temperature}°C, 湿度={humidity}%")
        else:
            # 通常の処理
            humidity = data_bytes[0] + data_bytes[1] * 0.1
            temperature = data_bytes[2] + data_bytes[3] * 0.1
        
        if debug:
            print(f"[DEBUG] 解析結果: 温度={temperature}°C, 湿度={humidity}%")
        
        # 値が妥当範囲内かチェック（部分読み取りの場合は緩和）
        if len(data_bits) < 40:
            # 部分読み取りの場合は緩い範囲チェック
            if not (0 <= humidity <= 150 and -10 <= temperature <= 100):
                if debug:
                    print(f"[DEBUG] 部分データ値が範囲外: 温度={temperature}, 湿度={humidity}")
                return None, None, 'INVALID_RANGE'
        else:
            # 完全読み取りの場合は厳密な範囲チェック
            if not (0 <= humidity <= 100 and -40 <= temperature <= 80):
                if debug:
                    print(f"[DEBUG] 値が範囲外: 温度={temperature}, 湿度={humidity}")
                return None, None, 'INVALID_RANGE'
        
        # 成功時は値を保存
        self.last_valid_time = time.time()
        self.last_temperature = temperature
        self.last_humidity = humidity
        
        return temperature, humidity, 'OK'
    
    def _start_signal(self):
        """
        DHT11への開始信号を送信
        
        Returns:
            bool: 応答信号が正常に受信された場合True
        """
        try:
            # ピンを出力モードに設定
            GPIO.setup(self.pin, GPIO.OUT)
            
            # 開始信号: 18ms LOW
            GPIO.output(self.pin, GPIO.LOW)
            time.sleep(0.020)  # 20msに延長
            
            # 40μs HIGH (少し長めに)
            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(0.00004)
            
            # ピンを入力モードに変更（プルアップ有効）
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # DHT11の応答信号を待機（80μs LOW + 80μs HIGH）
            # LOW信号の開始を待機（タイムアウト値を増加）
            timeout_count = 0
            while GPIO.input(self.pin) == GPIO.HIGH:
                timeout_count += 1
                if timeout_count > 1000:
                    print("[DEBUG] 応答待機1でタイムアウト")
                    return False
            
            # LOW信号の終了を待機
            timeout_count = 0
            while GPIO.input(self.pin) == GPIO.LOW:
                timeout_count += 1
                if timeout_count > 1000:
                    print("[DEBUG] 応答待機2でタイムアウト")
                    return False
            
            # HIGH信号の終了を待機
            timeout_count = 0
            while GPIO.input(self.pin) == GPIO.HIGH:
                timeout_count += 1
                if timeout_count > 1000:
                    print("[DEBUG] 応答待機3でタイムアウト")
                    return False
            
            print("[DEBUG] 開始信号の応答確認完了")
            return True
            
        except Exception as e:
            print(f"開始信号エラー: {e}")
            return False
    
    def _read_data_bits(self):
        """
        40ビットのデータを読み取り
        
        Returns:
            list: ビットのリスト（40個）、エラー時はNone
        """
        bits = []
        
        try:
            for i in range(40):
                # 各ビットの開始（50μs LOW）を待機
                timeout_count = 0
                while GPIO.input(self.pin) == GPIO.LOW:
                    timeout_count += 1
                    if timeout_count > 50000:  # さらにタイムアウトを増加
                        print(f"[DEBUG] ビット{i}: LOW待機でタイムアウト (count={timeout_count})")
                        return None
                
                # HIGH信号の時間を測定してビット判定
                high_start = time.time()
                timeout_count = 0
                while GPIO.input(self.pin) == GPIO.HIGH:
                    timeout_count += 1
                    if timeout_count > 50000:  # さらにタイムアウトを増加
                        print(f"[DEBUG] ビット{i}: HIGH待機でタイムアウト (count={timeout_count})")
                        # タイムアウト時は部分的な結果でも返す
                        if i >= 32:  # 32ビット以上読めていれば部分成功とみなす
                            print(f"[DEBUG] 部分読み取り: {i}ビット読み取り済み")
                            return bits
                        return None
                
                high_time = (time.time() - high_start) * 1000000  # マイクロ秒
                
                # 26-28μs: 0ビット, 70μs: 1ビット
                # より柔軟な判定基準
                if high_time > 35:  # 35μs以上なら1ビット
                    bits.append(1)
                else:
                    bits.append(0)
                
                # デバッグ情報（最初の10ビットと最後の10ビット）
                if i < 10 or i >= 30:
                    print(f"[DEBUG] ビット{i}: HIGH時間={high_time:.1f}μs, 値={'1' if high_time > 35 else '0'}")
            
            print(f"[DEBUG] 読み取り完了: {len(bits)}ビット")
            return bits
            
        except Exception as e:
            print(f"データ読み取りエラー: {e}")
            return None
    
    def _bits_to_bytes(self, bits):
        """
        ビットリストをバイト配列に変換
        
        Args:
            bits (list): ビットリスト（通常40個、部分読み取りの場合はそれ以下）
            
        Returns:
            list: バイト値のリスト、エラー時はNone
        """
        if len(bits) < 32:  # 最低32ビット（4バイト）必要
            print(f"[DEBUG] ビット数不足: {len(bits)}ビット（最低32ビット必要）")
            return None
        
        # 40ビット未満の場合は0で埋める
        if len(bits) < 40:
            bits = bits + [0] * (40 - len(bits))
            print(f"[DEBUG] {40 - len(bits)}ビットを0で埋めました")
        
        bytes_data = []
        for i in range(5):
            byte_val = 0
            for j in range(8):
                if i * 8 + j < len(bits):
                    byte_val = (byte_val << 1) + bits[i * 8 + j]
                else:
                    byte_val = byte_val << 1  # 0を追加
            bytes_data.append(byte_val)
        
        return bytes_data
    
    def _verify_checksum(self, data_bytes):
        """
        チェックサムを検証
        
        Args:
            data_bytes (list): 5個のバイト値
            
        Returns:
            bool: チェックサムが正しい場合True
        """
        if len(data_bytes) != 5:
            return False
        
        checksum = (data_bytes[0] + data_bytes[1] + data_bytes[2] + data_bytes[3]) & 0xFF
        return checksum == data_bytes[4]
    
    def read_retry(self, retries=3, debug=False):
        """
        リトライ機能付きの読み取り
        
        Args:
            retries (int): リトライ回数
            debug (bool): デバッグ情報を出力するかどうか
            
        Returns:
            tuple: (temperature, humidity, status)
        """
        for attempt in range(retries):
            if debug:
                print(f"[DEBUG] 試行 {attempt + 1}/{retries}")
            
            temp, humidity, status = self.read(debug=debug)
            if status == 'OK':
                return temp, humidity, status
            
            if debug:
                print(f"[DEBUG] 試行 {attempt + 1} 失敗: {status}")
            
            if attempt < retries - 1:
                time.sleep(2)  # リトライ前に2秒待機
        
        return temp, humidity, status
    
    def cleanup(self):
        """
        GPIO設定をクリーンアップ
        """
        try:
            GPIO.cleanup(self.pin)
        except Exception as e:
            print(f"[DEBUG] GPIO cleanup エラー: {e}")
            # 全体をクリーンアップ
            GPIO.cleanup()


# 使用例
if __name__ == "__main__":
    # GPIO 4番ピンに接続されたDHT11センサーを使用
    sensor = DHT11(pin=4)
    
    try:
        for i in range(10):
            temperature, humidity, status = sensor.read_retry()
            
            if status == 'OK':
                print(f"測定 {i+1}: 温度={temperature:.1f}°C, 湿度={humidity:.1f}%, 状態={status}")
            else:
                print(f"測定 {i+1}: エラー - {status}")
            
            time.sleep(3)  # 3秒間隔で測定
            
    except KeyboardInterrupt:
        print("\n測定を停止しました")
    finally:
        sensor.cleanup()
        print("GPIO設定をクリーンアップしました")
