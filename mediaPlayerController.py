import os
import sys
import ctypes
import cv2
import mediapipe as mp
import tkinter as tk
from tkinter import filedialog
import time

# VLC environmentSetup:
def setup_vlc_environment():
    vlc_paths = [
        "C:\\Program Files\\VideoLAN\\VLC",
        "C:\\Program Files (x86)\\VideoLAN\\VLC"
    ]
    vlc_lib_found = False
    for vlc_path in vlc_paths:
        vlc_dll_path = os.path.join(vlc_path, 'libvlc.dll')
        if os.path.isfile(vlc_dll_path):
            if vlc_path not in sys.path:
                sys.path.append(vlc_path)
            os.environ["PATH"] += os.pathsep + vlc_path
            try:
                ctypes.CDLL(vlc_dll_path)
                vlc_lib_found = True
                break
            except OSError:
                continue

    if not vlc_lib_found:
        raise FileNotFoundError("libvlc.dll not found. Please ensure VLC is installed correctly.")

    import vlc
    return vlc

# asking user for the media file path
def ask_file_path():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select a media file",
                                           filetypes=(("Media files", "*.mp4;*.mp3;*.avi;*.mkv"), ("All files", "*.*")))
    if not file_path:
        raise FileNotFoundError("No file selected.")
    return file_path

# Initialize VLC player and load media
def setup_vlc_player(vlc, media_path):
    instance = vlc.Instance("--intf=dummy --verbose=-1 --no-video-title-show")
    player = instance.media_player_new()
    media = instance.media_new(media_path)
    player.set_media(media)
    return player

# Load the VLC module and setup media player
vlc = setup_vlc_environment()
media_path = ask_file_path()
player = setup_vlc_player(vlc, media_path)
player.play()

# Setup MediaPipe for hand gesture recognition
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)

# Initialize camera
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

last_finger_count = 0  # Variable to track the last finger count
volume_step = 10  # Volume step for each gesture
skip_step = 10  # Skip step in seconds for each gesture

# Threshold for detecting raised fingers (in pixel coordinates)
FINGER_DETECT_THRESHOLD_Y = 0.1  # Adjust as needed

def count_raised_fingers_and_draw(hand_landmarks, image):
    # Define which landmarks correspond to the tips of the fingers
    finger_tips = [
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    raised_fingers = 0

    # Wrist landmark
    wrist_y = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].y

    for tip in finger_tips:
        if hand_landmarks.landmark[tip].y < wrist_y - FINGER_DETECT_THRESHOLD_Y:
            raised_fingers += 1
            # Draw circle on fingertip
            cx, cy = int(hand_landmarks.landmark[tip].x * image.shape[1]), int(hand_landmarks.landmark[tip].y * image.shape[0])
            cv2.circle(image, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

    # Thumb landmark checks
    thumb_tip = mp_hands.HandLandmark.THUMB_TIP
    thumb_ip = mp_hands.HandLandmark.THUMB_IP
    thumb_mcp = mp_hands.HandLandmark.THUMB_MCP

    if hand_landmarks.landmark[thumb_tip].x < hand_landmarks.landmark[thumb_ip].x and hand_landmarks.landmark[thumb_tip].y < hand_landmarks.landmark[thumb_mcp].y:
        raised_fingers += 1
        # Draw circle on thumb tip
        cx, cy = int(hand_landmarks.landmark[thumb_tip].x * image.shape[1]), int(hand_landmarks.landmark[thumb_tip].y * image.shape[0])
        cv2.circle(image, (cx, cy), 10, (0, 255, 0), cv2.FILLED)

    return raised_fingers

try:
    while cap.isOpened():
        start_time = time.time()
        success, image = cap.read()
        if not success:
            continue

        # Process the image and detect hands
        image = cv2.flip(image, 1)  # Flip image horizontally for better user experience
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = hands.process(image_rgb)

        finger_count = 0  # Variable to count the number of fingers shown

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                finger_count = count_raised_fingers_and_draw(hand_landmarks, image)
                finger_count = min(finger_count, 5)  # Limit finger count to 5 fingers maximum

                # Draw landmarks on hand
                mp.solutions.drawing_utils.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        # Display the finger count on the image
        cv2.putText(image, f'Fingers: {finger_count}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 0, 0), 2, cv2.LINE_AA)

        # Control video playback and volume based on hand gesture
        if finger_count != last_finger_count:  # Check if the finger count has changed
            if finger_count == 1:
                player.pause()  # Pause the video if one finger is raised
            elif finger_count == 2:
                try:
                    new_volume = min(player.audio_get_volume() + volume_step, 100)
                    player.audio_set_volume(new_volume)  # Increase volume if two fingers are raised
                    print("Volume increased to:", new_volume)
                except Exception as e:
                    print("Volume control error:", e)
            elif finger_count == 3:
                try:
                    new_volume = max(player.audio_get_volume() - volume_step, 0)
                    player.audio_set_volume(new_volume)  # Decrease volume if three fingers are raised
                    print("Volume decreased to:", new_volume)
                except Exception as e:
                    print("Volume control error:", e)
            elif finger_count == 4:
                # Skip forward if four fingers are raised
                current_time = player.get_time() / 1000  # Convert milliseconds to seconds
                player.set_time(int((current_time + skip_step) * 1000))  # Skip forward
                print("Skipped forward by:", skip_step, "seconds")
            elif finger_count == 5:
                # Skip backward if five fingers are raised
                current_time = player.get_time() / 1000  # Convert milliseconds to seconds
                player.set_time(int(max(current_time - skip_step, 0) * 1000))  # Skip backward
                print("Skipped backward by:", skip_step, "seconds")
            last_finger_count = finger_count  # Update the last finger count

        cv2.imshow('Media Player Control', image)
        end_time = time.time()
        elapsed_time = end_time - start_time
        if elapsed_time < 0.05:  # Delay for a short time to control frame rate
            time.sleep(0.05 - elapsed_time)

        if cv2.waitKey(1) & 0xFF == 27:
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
    player.stop()
