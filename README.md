# Hand-Tracking-Module
A real time hand tracking module for sign language with voice feature!

Uses LSTM neutral network 

# Exemple




https://github.com/user-attachments/assets/30772251-d9f6-4f12-aa5e-f93aec79ea8d

# Features 
- Editable data base (delete, add or change sign data base)
- Over 90% accuracy
- voice feature reading the signs



Future AI API interpretation of words for full sentence sturcture stay tunned!!
Working on making it a usable app on windows without any venv setup (failing lol but it'll work out somehow trust)
  


# Installation
Clone the repo


    git clone https://github.com/Malia-lai/Hand-Tracking-Module


# Requirements
 py 2.9 (need to be compatible with mediapipe 0.10.9)
 Then download the requirements :3

    pip install -r requirements.txt

# Use 
collect.py is to train your model with any word you want (add your word + key to click inside the GESTURES dictionary and boot the code)

samplenum.py to check number of samples and/or if the numpy file containing your data is corrupted.

delete.py delete a specific gesture's data by writing the name you gave it inside the GESTURE dictionary.

realtime.py to boot the code and sign in real life !





