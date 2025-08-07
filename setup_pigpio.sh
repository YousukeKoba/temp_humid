#!/bin/bash
"""
pigpio環境セットアップスクリプト
DHT11の高精度制御に必要なpigpioライブラリをインストール・設定します
"""

echo "DHT11用 pigpio環境セットアップ"
echo "================================"

# 現在の環境確認
echo "1. 現在の環境確認..."
echo "Raspberry Pi OS バージョン:"
cat /etc/os-release | grep PRETTY_NAME

echo -e "\nPython バージョン:"
python3 --version

# pigpio インストール確認
echo -e "\n2. pigpio インストール状況確認..."
if dpkg -l | grep -q pigpio; then
    echo "✓ pigpio パッケージ インストール済み"
else
    echo "✗ pigpio パッケージ 未インストール"
    echo "インストールを開始します..."
    
    sudo apt update
    sudo apt install -y pigpio python3-pigpio
    
    if [ $? -eq 0 ]; then
        echo "✓ pigpio インストール完了"
    else
        echo "✗ pigpio インストール失敗"
        exit 1
    fi
fi

# pigpioデーモン設定
echo -e "\n3. pigpioデーモン設定..."

# デーモンの現在状態確認
if systemctl is-active --quiet pigpiod; then
    echo "✓ pigpioデーモン 動作中"
else
    echo "✗ pigpioデーモン 停止中"
    echo "デーモンを開始します..."
    
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
    
    # 少し待機してから状態確認
    sleep 2
    
    if systemctl is-active --quiet pigpiod; then
        echo "✓ pigpioデーモン 開始成功"
    else
        echo "✗ pigpioデーモン 開始失敗"
        echo "手動で確認してください: sudo systemctl status pigpiod"
        exit 1
    fi
fi

# 自動起動設定確認
if systemctl is-enabled --quiet pigpiod; then
    echo "✓ pigpioデーモン 自動起動 有効"
else
    echo "! pigpioデーモン 自動起動を有効化します..."
    sudo systemctl enable pigpiod
fi

# Python環境でのpigpio確認
echo -e "\n4. Python pigpio ライブラリ確認..."
python3 -c "
try:
    import pigpio
    print('✓ Python pigpio ライブラリ インポート成功')
    
    # 接続テスト
    pi = pigpio.pi()
    if pi.connected:
        print('✓ pigpioデーモン 接続成功')
        pi.stop()
    else:
        print('✗ pigpioデーモン 接続失敗')
        exit(1)
except ImportError:
    print('✗ Python pigpio ライブラリ インポート失敗')
    exit(1)
except Exception as e:
    print(f'✗ pigpio接続エラー: {e}')
    exit(1)
"

if [ $? -eq 0 ]; then
    echo "✓ pigpio環境セットアップ完了"
else
    echo "✗ pigpio環境に問題があります"
    exit 1
fi

# 設定完了メッセージ
echo -e "\n================================"
echo "pigpio環境セットアップ完了！"
echo ""
echo "次のステップ:"
echo "1. DHT11センサーを接続"
echo "2. 4.7kΩプルアップ抵抗を追加"
echo "3. テストスクリプト実行:"
echo "   python3 dht11_pigpio_test.py"
echo ""
echo "pigpioデーモン制御コマンド:"
echo "  開始: sudo systemctl start pigpiod"
echo "  停止: sudo systemctl stop pigpiod"
echo "  状態: sudo systemctl status pigpiod"
echo "  ログ: sudo journalctl -u pigpiod"
