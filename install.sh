#!/bin/bash

echo "installing oracle pi..."

sudo apt update
sudo apt install -y python3 python3-pip python3-venv
sudo apt install -y portaudio19-dev python3-pyaudio
sudo apt install -y espeak ffmpeg libespeak1

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "done, now create .env with your api key:"
echo "  echo 'OPENROUTER_API_KEY=your_key' > .env"
echo ""
echo "then run:"
echo "  source venv/bin/activate"
echo "  python main.py"
