![Hack Club](https://img.shields.io/badge/Hack%20Club-Blueprint-EC3750?style=for-the-badge&logo=hack-club&logoColor=white)
![Status](https://img.shields.io/badge/Status-Prototype-blue?style=for-the-badge)
![Hardware](https://img.shields.io/badge/Hardware-Raspberry%20Pi%205-C51A4A?style=for-the-badge&logo=raspberry-pi&logoColor=white)
![Built With](https://img.shields.io/badge/Built%20With-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
# Oracle Pi

an ai device that runs on a raspberry pi 5 and uses allenai/molmo-2-8b model via openrouter

![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

## app image
![image](image.png)

## what is this
im building a alexa like device that uses my phones internet via bluetooth, right now it connects to allenai/molmo-2-8b via openrouter but in the future i want to run the models fully locally on the pi

## buy list
refer to [the parts list](parts_list.md)

## how to run
1. clone this repo
2. run `bash install.sh`
3. create a file named `.env` and paste your key in it (see `.env.example`)
4. run `python main.py`
## additional regards
see [notes](notes.md)

## license
Apache 2.0