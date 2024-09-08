#!/bin/bash
apt-get install python3
apt-get install ffmpeg
apt-get install libportaudio2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
echo "Pre-Reqs installed, now setting up python3 for Raphael"
installpath=$(pwd)
python3 -m venv "$installpath"
. bin/activate
#Install dependencies
pip3 install boto3
pip3 install irc
pip3 install openai
pip3 install obsws_python
pip3 install sounddevice
pip3 install pyyaml
pip3 install aiofile
pip3 install amazon_transcribe
pip3 install flask
pip3 install requests
aws configure