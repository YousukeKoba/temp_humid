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
    
    def read(self):
        """
        温湿度データを読み取り
        
        Returns:
            tuple: (temperature, humidity, status)
                - temperature: 温度（℃）
                - humidity: 湿度（%）
                - status: 読み取り結果（'OK', 'CHECKSUM_ERROR', 'TIMEOUT', 'NO_DATA'）
        """
        # 前回の読み取りから2秒以上経過していることを確認
        if time.time() - self.last_valid_time < 2:
            return self.last_temperature, self.last_humidity, 'CACHE'
        
        # センサーの開始信号を送信
        if not self._start_signal():
            return None, None, 'TIMEOUT'
        
        # データビットを読み取り
        data_bits = self._read_data_bits()
        if not data_bits:
            return None, None, 'NO_DATA'
        
        # データをバイトに変換
        data_bytes = self._bits_to_bytes(data_bits)
        if not data_bytes:
            return None, None, 'NO_DATA'
        
        # チェックサムを検証
        if not self._verify_checksum(data_bytes):
            return None, None, 'CHECKSUM_ERROR'
        
        # 温湿度データを解析
        humidity = data_bytes[0] + data_bytes[1] * 0.1
        temperature = data_bytes[2] + data_bytes[3] * 0.1
        
        # 値が妥当範囲内かチェック
        if not (0 <= humidity <= 100 and -40 <= temperature <= 80):
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
            time.sleep(0.018)
            
            # 30μs HIGH
            GPIO.output(self.pin, GPIO.HIGH)
            time.sleep(0.00003)
            
            # ピンを入力モードに変更
            GPIO.setup(self.pin, GPIO.IN)
            
            # DHT11の応答信号を待機（80μs LOW + 80μs HIGH）
            # LOW信号の開始を待機（タイムアウト: 100μs）
            timeout = 0
            while GPIO.input(self.pin) == GPIO.HIGH:
                time.sleep(0.000001)
                timeout += 1
                if timeout > 100:
                    return False
            
            # LOW信号の終了を待機（タイムアウト: 100μs）
            timeout = 0
            while GPIO.input(self.pin) == GPIO.LOW:
                time.sleep(0.000001)
                timeout += 1
                if timeout > 100:
                    return False
            
            # HIGH信号の終了を待機（タイムアウト: 100μs）
            timeout = 0
            while GPIO.input(self.pin) == GPIO.HIGH:
                time.sleep(0.000001)
                timeout += 1
                if timeout > 100:
                    return False
            
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
                timeout = 0
                while GPIO.input(self.pin) == GPIO.LOW:
                    time.sleep(0.000001)
                    timeout += 1
                    if timeout > 100:
                        return None
                
                # HIGH信号の時間を測定してビット判定
                high_start = time.time()
                timeout = 0
                while GPIO.input(self.pin) == GPIO.HIGH:
                    time.sleep(0.000001)
                    timeout += 1
                    if timeout > 100:
                        return None
                
                high_time = (time.time() - high_start) * 1000000  # マイクロ秒
                
                # 26-28μs: 0ビット, 70μs: 1ビット
                if high_time > 40:
                    bits.append(1)
                else:
                    bits.append(0)
            
            return bits
            
        except Exception as e:
            print(f"データ読み取りエラー: {e}")
            return None
    
    def _bits_to_bytes(self, bits):
        """
        ビットリストをバイト配列に変換
        
        Args:
            bits (list): 40個のビットリスト
            
        Returns:
            list: 5個のバイト値、エラー時はNone
        """
        if len(bits) != 40:
            return None
        
        bytes_data = []
        for i in range(5):
            byte_val = 0
            for j in range(8):
                byte_val = (byte_val << 1) + bits[i * 8 + j]
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
    
    def read_retry(self, retries=3):
        """
        リトライ機能付きの読み取り
        
        Args:
            retries (int): リトライ回数
            
        Returns:
            tuple: (temperature, humidity, status)
        """
        for attempt in range(retries):
            temp, humidity, status = self.read()
            if status == 'OK':
                return temp, humidity, status
            
            if attempt < retries - 1:
                time.sleep(2)  # リトライ前に2秒待機
        
        return temp, humidity, status
    
    def cleanup(self):
        """
        GPIO設定をクリーンアップ
        """
        GPIO.cleanup(self.pin)


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
