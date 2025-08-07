#!/bin/bash

# 温湿度監視システム セットアップスクリプト
# Usage: ./setup.sh

set -e

echo "=== 温湿度監視システム セットアップ ==="

# 変数設定
INSTALL_DIR="/home/pi/temperature_humidity_monitor"
SERVICE_NAME="temp-humidity-monitor"
USER="pi"

# 現在のユーザーチェック
if [ "$USER" != "pi" ] && [ "$EUID" -ne 0 ]; then
    echo "エラー: このスクリプトはpiユーザーまたはroot権限で実行してください"
    exit 1
fi

# 必要なパッケージをインストール
echo "必要なパッケージをインストールしています..."
sudo apt update
sudo apt install -y python3 python3-pip python3-full python3-rpi.gpio git

# 仮想環境を作成してライブラリをインストール
echo "Python仮想環境を作成しています..."
python3 -m venv ~/temp_humidity_venv

# 仮想環境でRPi.GPIOライブラリをインストール（既にaptでインストール済みなのでスキップ）
echo "RPi.GPIOライブラリは既にシステムにインストールされています..."

# インストールディレクトリを作成
echo "インストールディレクトリを作成しています..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown pi:pi "$INSTALL_DIR"

# 現在のディレクトリからファイルをコピー
echo "ファイルをコピーしています..."
cp -r ./* "$INSTALL_DIR/"

# 必要なファイルの存在確認
echo "必要なファイルの存在確認..."
required_files=("config.ini" "data_collector.py" "dht11_library.py" "temp-humidity-monitor.service")
for file in "${required_files[@]}"; do
    if [ ! -f "$INSTALL_DIR/$file" ] && [ ! -f "$INSTALL_DIR/raspberry_pi/$file" ]; then
        echo "エラー: 必要なファイル '$file' が見つかりません"
        echo "以下のファイルを temp_humid ディレクトリにコピーしてください:"
        echo "- config.ini"
        echo "- data_collector.py" 
        echo "- dht11_library.py"
        echo "- temp-humidity-monitor.service"
        exit 1
    fi
done

# 設定ファイルを調整
echo "設定ファイルを調整しています..."
if [ -f "$INSTALL_DIR/config.ini" ]; then
    sed -i "s|/home/pi/temperature_humidity_monitor|$INSTALL_DIR|g" "$INSTALL_DIR/config.ini"
elif [ -f "$INSTALL_DIR/raspberry_pi/config.ini" ]; then
    sed -i "s|/home/pi/temperature_humidity_monitor|$INSTALL_DIR|g" "$INSTALL_DIR/raspberry_pi/config.ini"
fi

# データディレクトリを作成
mkdir -p "$INSTALL_DIR/data"

# 実行権限を設定
if [ -f "$INSTALL_DIR/data_collector.py" ]; then
    chmod +x "$INSTALL_DIR/data_collector.py"
elif [ -f "$INSTALL_DIR/raspberry_pi/data_collector.py" ]; then
    chmod +x "$INSTALL_DIR/raspberry_pi/data_collector.py"
fi

# systemdサービスをインストール
echo "systemdサービスをインストールしています..."
if [ -f "$INSTALL_DIR/$SERVICE_NAME.service" ]; then
    sudo cp "$INSTALL_DIR/$SERVICE_NAME.service" "/etc/systemd/system/"
elif [ -f "$INSTALL_DIR/raspberry_pi/$SERVICE_NAME.service" ]; then
    sudo cp "$INSTALL_DIR/raspberry_pi/$SERVICE_NAME.service" "/etc/systemd/system/"
fi
sudo systemctl daemon-reload

# Git設定の確認
echo "Git設定を確認しています..."
if ! git config user.name > /dev/null 2>&1; then
    echo "Gitのユーザー名を設定してください:"
    read -p "ユーザー名: " git_username
    git config --global user.name "$git_username"
fi

if ! git config user.email > /dev/null 2>&1; then
    echo "Gitのメールアドレスを設定してください:"
    read -p "メールアドレス: " git_email
    git config --global user.email "$git_email"
fi

# GitHubリポジトリの設定
echo ""
echo "GitHubリポジトリの設定を行います..."
echo "1. GitHubでリポジトリを作成してください"
echo "2. Personal Access Token (PAT) を作成してください"
echo "   - Settings > Developer settings > Personal access tokens"
echo "   - repo権限を付与してください"

read -p "GitHubリポジトリのURL (https://github.com/username/repo.git): " repo_url
read -p "GitHubユーザー名: " github_username
read -s -p "Personal Access Token: " github_token
echo ""

# Git リポジトリを初期化
cd "$INSTALL_DIR"
if [ ! -d ".git" ]; then
    git init
    git remote add origin "$repo_url"
fi

# GitHub認証情報を設定（トークンを使用）
git remote set-url origin "https://$github_username:$github_token@${repo_url#https://}"

# 初回コミット
git add .
git commit -m "Initial commit: Temperature humidity monitoring system"
git branch -M main
git push -u origin main

# サービスの有効化と開始
echo "サービスを有効化・開始しています..."
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

# 動作確認
echo ""
echo "=== セットアップ完了 ==="
echo "サービス状態:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "設定内容:"
echo "- インストールディレクトリ: $INSTALL_DIR"
echo "- データファイル: $INSTALL_DIR/data/sensor_data.json"
echo "- ログファイル: /var/log/temp_humidity.log"

echo ""
echo "便利なコマンド:"
echo "- サービス状態確認: sudo systemctl status $SERVICE_NAME"
echo "- サービス停止: sudo systemctl stop $SERVICE_NAME"
echo "- サービス開始: sudo systemctl start $SERVICE_NAME"
echo "- ログ確認: sudo journalctl -u $SERVICE_NAME -f"
echo "- 手動実行（テスト）: cd $INSTALL_DIR/raspberry_pi && python3 data_collector.py --once --test"

echo ""
echo "GitHub Pagesでの確認:"
echo "1. GitHubリポジトリのSettings > Pagesで GitHub Pages を有効化してください"
echo "2. Source を 'Deploy from a branch' に設定"
echo "3. Branch を 'main' に設定"
echo "4. 数分後にWebページが表示されます"

echo ""
echo "DHT11センサーの接続:"
echo "- VCC -> 3.3V (Pin 1)"
echo "- GND -> GND (Pin 6)"  
echo "- DATA -> GPIO4 (Pin 7)"
echo ""
echo "セットアップが完了しました！"
