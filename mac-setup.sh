#!/bin/bash
echo "Using Homebrew to install pre-reqs"
which -s brew
if [[ $? != 0 ]] ; then
    # Install Homebrew
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
else
    brew update
fi
brew install python3
brew install ffmpeg
brew install awscli
echo "Pre-Reqs installed, now setting up python3 for Raphael"
installpath=$(pwd)
python3 -m venv "$installpath"
. bin/activate
#Install dependencies
pip3 install -r requirements.txt
aws configure