import mediapipe as mp
import cv2
import random
import math
import time
#専用ターミナルでpythonファイルを実行
#Qiitaの練習用コード
#・ゲームの説明
#目的: 右手の人差し指で赤い丸に触れてスコアを稼ぐ。
#制限時間: 30秒。
#操作:
#'f' キーでフルスクリーンとウィンドウモードを切り替え。
#'q' キーでゲームを終了。（30秒たつと自動的に終了はします。）

# MediaPipe Handsのセットアップ
mp_hands = mp.solutions.hands
hands = mp_hands.Hands()
mp_drawing = mp.solutions.drawing_utils

# スコアの初期化
score = 0

# ランダムに赤い丸を表示するための初期位置
circle_x = random.randint(100, 500)
circle_y = random.randint(100, 400)
circle_radius = 20

# カメラからの映像をキャプチャ
cap = cv2.VideoCapture(0)

# OpenCVのウィンドウを作成
cv2.namedWindow('Hand Game', cv2.WINDOW_NORMAL)
is_fullscreen = False

# ゲームの制限時間（秒）
game_duration = 30
start_time = time.time()

def is_hand_touching_circle(hand_x, hand_y, circle_x, circle_y, circle_radius):
    distance = math.sqrt((hand_x - circle_x) ** 2 + (hand_y - circle_y) ** 2)
    return distance < circle_radius

def generate_new_circle_position(frame_width, frame_height, circle_radius, exclude_area):
    while True:
        new_x = random.randint(circle_radius, frame_width - circle_radius)
        new_y = random.randint(circle_radius, frame_height - circle_radius)
        if not (exclude_area[0] <= new_x <= exclude_area[2] and exclude_area[1] <= new_y <= exclude_area[3]):
            return new_x, new_y

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 画像を水平方向に反転
    frame = cv2.flip(frame, 1)

    # 画像をRGBに変換
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 手のランドマークの検出
    results = hands.process(image)

    # 画像をBGRに戻す
    frame = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    # スコアとタイマー表示領域の背景を描画
    cv2.rectangle(frame, (0, 0), (200, 100), (0, 0, 0), -1)

    # 検出結果がある場合、ランドマークを描画し、右手の位置を取得
    if results.multi_hand_landmarks:
        for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # ランドマークの座標を取得（例として8番目のランドマーク=右手の人差し指の先端を使用）
            hand_x = int(hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].x * frame.shape[1])
            hand_y = int(hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP].y * frame.shape[0])

            if is_hand_touching_circle(hand_x, hand_y, circle_x, circle_y, circle_radius):
                score += 1
                # 新しい位置に赤い丸を再配置
                circle_x, circle_y = generate_new_circle_position(frame.shape[1], frame.shape[0], circle_radius, (0, 0, 200, 100))

    # 赤い丸を描画
    cv2.circle(frame, (circle_x, circle_y), circle_radius, (0, 0, 255), -1)

    # スコアを表示
    cv2.putText(frame, f'Score: {score}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

    # 残り時間を計算
    elapsed_time = time.time() - start_time
    remaining_time = max(0, game_duration - int(elapsed_time))
    cv2.putText(frame, f'Time: {remaining_time}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

    # ゲーム終了条件
    if remaining_time <= 0:
        break

    # 画像を表示
    cv2.imshow('Hand Game', frame)

    # キー入力をチェック
    key = cv2.waitKey(10) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('f'):
        is_fullscreen = not is_fullscreen
        if is_fullscreen:
            cv2.setWindowProperty('Hand Game', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty('Hand Game', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)

# リソースの解放
cap.release()
cv2.destroyAllWindows()

# ゲーム終了メッセージ
print(f'Game Over! Your score is {score}')
