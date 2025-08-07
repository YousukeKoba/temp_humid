#!/usr/bin/env python3
"""
温湿度データ収集・GitHub更新スクリプト

DHT11センサーから温湿度データを収集し、JSONファイルに保存して
GitHub Pages用リポジトリに自動プッシュします。
"""

import json
import os
import sys
import time
import subprocess
import configparser
from datetime import datetime, timedelta
from pathlib import Path

# DHT11ライブラリをインポート
from dht11_library import DHT11


class TemperatureHumidityLogger:
    """温湿度データロガークラス"""
    
    def __init__(self, config_file='config.ini'):
        """
        初期化
        
        Args:
            config_file (str): 設定ファイルのパス
        """
        self.config = self._load_config(config_file)
        self.sensor = DHT11(pin=self.config['sensor']['pin'])
        self.data_file = Path(self.config['data']['file_path'])
        self.repo_path = Path(self.config['git']['repo_path'])
        
        # データディレクトリを作成
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"温湿度ロガーを初期化しました")
        print(f"センサーピン: GPIO{self.config['sensor']['pin']}")
        print(f"データファイル: {self.data_file}")
        print(f"リポジトリパス: {self.repo_path}")
    
    def _load_config(self, config_file):
        """設定ファイルを読み込み"""
        config = configparser.ConfigParser()
        
        # デフォルト設定
        default_config = {
            'sensor': {
                'pin': '4',
                'retry_count': '3',
                'read_interval': '60'
            },
            'data': {
                'file_path': '/home/pi/temperature_humidity_monitor/data/sensor_data.json',
                'max_records': '525600',  # 1年分（1分間隔）
                'backup_enabled': 'true'
            },
            'git': {
                'repo_path': '/home/pi/temperature_humidity_monitor',
                'auto_push': 'true',
                'commit_message': 'Update sensor data',
                'remote_name': 'origin',
                'branch_name': 'main'
            },
            'logging': {
                'level': 'INFO',
                'console_output': 'true',
                'log_file': '/var/log/temp_humidity.log'
            }
        }
        
        # 設定ファイルが存在しない場合はデフォルト設定で作成
        if not Path(config_file).exists():
            print(f"設定ファイルが見つかりません。デフォルト設定で {config_file} を作成します。")
            self._create_default_config(config_file, default_config)
        
        config.read(config_file)
        
        # 型変換
        parsed_config = {}
        for section_name, section in config.items():
            if section_name == 'DEFAULT':
                continue
            parsed_config[section_name] = {}
            for key, value in section.items():
                if key in ['pin', 'retry_count', 'read_interval', 'max_records']:
                    parsed_config[section_name][key] = int(value)
                elif key in ['backup_enabled', 'auto_push', 'console_output']:
                    parsed_config[section_name][key] = value.lower() == 'true'
                else:
                    parsed_config[section_name][key] = value
        
        return parsed_config
    
    def _create_default_config(self, config_file, default_config):
        """デフォルト設定ファイルを作成"""
        config = configparser.ConfigParser()
        for section_name, section_data in default_config.items():
            config[section_name] = section_data
        
        with open(config_file, 'w') as f:
            config.write(f)
    
    def read_sensor(self):
        """
        センサーからデータを読み取り
        
        Returns:
            dict: センサーデータ辞書、エラー時はNone
        """
        temperature, humidity, status = self.sensor.read_retry(
            retries=self.config['sensor']['retry_count']
        )
        
        if status == 'OK':
            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'temperature': round(temperature, 1),
                'humidity': round(humidity, 1),
                'status': status
            }
        else:
            self._log(f"センサー読み取りエラー: {status}", level='ERROR')
            return None
    
    def load_existing_data(self):
        """既存のデータファイルを読み込み"""
        if not self.data_file.exists():
            return []
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            self._log(f"データファイル読み込みエラー: {e}", level='ERROR')
            return []
    
    def save_data(self, data_list):
        """
        データをJSONファイルに保存
        
        Args:
            data_list (list): センサーデータのリスト
        """
        # データ件数制限
        max_records = self.config['data']['max_records']
        if len(data_list) > max_records:
            data_list = data_list[-max_records:]
        
        # バックアップ作成
        if self.config['data']['backup_enabled'] and self.data_file.exists():
            backup_file = self.data_file.with_suffix('.json.bak')
            try:
                subprocess.run(['cp', str(self.data_file), str(backup_file)], check=True)
            except subprocess.CalledProcessError as e:
                self._log(f"バックアップ作成エラー: {e}", level='WARNING')
        
        # データ保存
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data_list, f, indent=2, ensure_ascii=False)
            self._log(f"データを保存しました: {len(data_list)}件")
        except IOError as e:
            self._log(f"データ保存エラー: {e}", level='ERROR')
            raise
    
    def git_push(self):
        """GitHubにデータをプッシュ"""
        if not self.config['git']['auto_push']:
            return
        
        try:
            os.chdir(self.repo_path)
            
            # Gitの状態確認
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True, check=True)
            
            if not result.stdout.strip():
                self._log("変更がないためプッシュをスキップします")
                return
            
            # ファイルをステージング
            subprocess.run(['git', 'add', '.'], check=True)
            
            # コミット
            commit_message = f"{self.config['git']['commit_message']} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            
            # プッシュ
            remote = self.config['git']['remote_name']
            branch = self.config['git']['branch_name']
            subprocess.run(['git', 'push', remote, branch], check=True)
            
            self._log("GitHubに正常にプッシュしました")
            
        except subprocess.CalledProcessError as e:
            self._log(f"Git操作エラー: {e}", level='ERROR')
        except Exception as e:
            self._log(f"予期しないエラー: {e}", level='ERROR')
    
    def cleanup_old_data(self, data_list, days=30):
        """
        古いデータをクリーンアップ
        
        Args:
            data_list (list): データリスト
            days (int): 保持日数
            
        Returns:
            list: クリーンアップ後のデータリスト
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        cutoff_iso = cutoff_date.isoformat() + 'Z'
        
        filtered_data = [
            item for item in data_list 
            if item.get('timestamp', '') >= cutoff_iso
        ]
        
        removed_count = len(data_list) - len(filtered_data)
        if removed_count > 0:
            self._log(f"古いデータ {removed_count}件を削除しました")
        
        return filtered_data
    
    def run_once(self):
        """1回のデータ収集・保存・プッシュを実行"""
        # センサーデータ読み取り
        sensor_data = self.read_sensor()
        if sensor_data is None:
            return False
        
        # 既存データ読み込み
        existing_data = self.load_existing_data()
        
        # 新しいデータを追加
        existing_data.append(sensor_data)
        
        # 古いデータをクリーンアップ（設定で有効な場合）
        if self.config['data'].get('cleanup_days'):
            existing_data = self.cleanup_old_data(
                existing_data, 
                self.config['data']['cleanup_days']
            )
        
        # データ保存
        self.save_data(existing_data)
        
        # GitHubにプッシュ
        self.git_push()
        
        self._log(f"データ収集完了: 温度={sensor_data['temperature']}°C, "
                 f"湿度={sensor_data['humidity']}%")
        
        return True
    
    def run_continuous(self):
        """連続実行モード"""
        self._log("連続実行モードを開始します")
        interval = self.config['sensor']['read_interval']
        
        try:
            while True:
                start_time = time.time()
                
                success = self.run_once()
                if not success:
                    self._log("データ収集に失敗しました", level='WARNING')
                
                # 次の実行まで待機
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self._log("ユーザーによって停止されました")
        except Exception as e:
            self._log(f"予期しないエラー: {e}", level='ERROR')
            raise
        finally:
            self.sensor.cleanup()
            self._log("センサーをクリーンアップしました")
    
    def _log(self, message, level='INFO'):
        """ログ出力"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {level}: {message}"
        
        if self.config['logging']['console_output']:
            print(log_message)
        
        # ログファイルへの出力（オプション）
        if self.config['logging'].get('log_file'):
            try:
                with open(self.config['logging']['log_file'], 'a') as f:
                    f.write(log_message + '\n')
            except IOError:
                pass  # ログファイル書き込みエラーは無視


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='温湿度データ収集システム')
    parser.add_argument('--config', default='config.ini', 
                       help='設定ファイルパス (デフォルト: config.ini)')
    parser.add_argument('--once', action='store_true', 
                       help='一度だけ実行（連続実行しない）')
    parser.add_argument('--test', action='store_true', 
                       help='テストモード（Gitプッシュなし）')
    
    args = parser.parse_args()
    
    try:
        logger = TemperatureHumidityLogger(args.config)
        
        # テストモードの場合はGitプッシュを無効化
        if args.test:
            logger.config['git']['auto_push'] = False
            print("テストモード: Gitプッシュは無効です")
        
        if args.once:
            success = logger.run_once()
            sys.exit(0 if success else 1)
        else:
            logger.run_continuous()
            
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
