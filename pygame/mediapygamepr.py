import cv2
import mediapipe as mp
import pygame

# --- 初期設定 ---

# MediaPipeの手検出モデルを準備
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=2,                # 最大検出数を2に設定
    min_detection_confidence=0.7,   # 検出信頼度の閾値
    min_tracking_confidence=0.7     # 追跡信頼度の閾値
)

# Pygameの初期化
pygame.init()

# Pygameウィンドウの設定
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Bouldering Game Prototype")

# 色の定義
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)

# プレイヤー（円）の設定
player_pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
player_radius = 30
GRAVITY = 10

# Webカメラの準備
cap = cv2.VideoCapture(0)

# --- 関数定義 ---

def is_hand_open(hand_landmarks):
    """
    手のランドマークから、その手が開いている（パー）か閉じている（グー）かを判定する関数。
    4本の指先が、それぞれの第二関節より上にあるかどうかで判定する。
    """
    # 親指を除く4本の指の先端のランドマークID
    tip_ids = [
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    # 親指を除く4本の指の第二関節のランドマークID
    pip_ids = [
        mp_hands.HandLandmark.INDEX_FINGER_PIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
        mp_hands.HandLandmark.RING_FINGER_PIP,
        mp_hands.HandLandmark.PINKY_PIP
    ]

    open_fingers = 0
    for tip_id, pip_id in zip(tip_ids, pip_ids):
        # 指先のy座標が第二関節のy座標より小さい（画面上で上にある）場合、指は伸びていると判定
        if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y:
            open_fingers += 1

    # 3本以上の指が伸びていれば「パー」と判定
    return open_fingers >= 3


# --- メインループ ---
running = True
clock = pygame.time.Clock()

while running and cap.isOpened():
    # 1. Pygameのイベント処理
    # 1. Pygameのイベント処理
    for event in pygame.event.get():
        # ウィンドウの閉じるボタンが押された場合
        if event.type == pygame.QUIT:
            running = False
        # キーが押された場合
        if event.type == pygame.KEYDOWN:
            # そのキーがエンターキーの場合
            if event.key == pygame.K_RETURN:
                running = False

    # 2. OpenCVとMediaPipeによる手の検出
    success, image = cap.read()
    if not success:
        print("Ignoring empty camera frame.")
        continue

    # 映像を左右反転させてから、色をBGRからRGBに変換
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    
    # パフォーマンス向上のため、画像を書き込み不可にする
    image.flags.writeable = False
    results = hands.process(image)

    # 3. ジェスチャーと手の位置を判断
    left_hand_open, right_hand_open = False, False
    left_hand_pos, right_hand_pos = None, None

    if results.multi_hand_landmarks:
        # 検出された各手についてループ
        for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
            # ランドマークから手が「パー」か「グー」かを判定
            is_open = is_hand_open(hand_landmarks)
            
            # ランドマークから中指の付け根（第3関節）の座標を取得
            mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
            hand_x = int(mcp_landmark.x * SCREEN_WIDTH)
            hand_y = int(mcp_landmark.y * SCREEN_HEIGHT)

            # 左右の手の情報を更新
            if handedness.classification[0].label == 'Left':
                left_hand_open = is_open
                left_hand_pos = (hand_x, hand_y)
            elif handedness.classification[0].label == 'Right':
                right_hand_open = is_open
                right_hand_pos = (hand_x, hand_y)

    # 4. ゲームロジック（ジェスチャーに応じてプレイヤーを動かす）
    # 両手グー：止まる
    if not left_hand_open and not right_hand_open:
        pass # 位置を更新しない
    # 右手グー、左手パー：左手の位置に追従
    elif not right_hand_open and left_hand_open and left_hand_pos:
        player_pos[0], player_pos[1] = left_hand_pos
    # 左手グー、右手パー：右手の位置に追従
    elif not left_hand_open and right_hand_open and right_hand_pos:
        player_pos[0], player_pos[1] = right_hand_pos
    # 両手パー：下に落下
    elif left_hand_open and right_hand_open:
        player_pos[1] += GRAVITY
    
    # 画面外に出ないように制限
    if player_pos[1] > SCREEN_HEIGHT - player_radius:
        player_pos[1] = SCREEN_HEIGHT - player_radius


    # 5. Pygameの描画処理
    screen.fill(WHITE) # 画面を黒で塗りつぶす
    pygame.draw.circle(screen, RED, player_pos, player_radius) # プレイヤー（円）を描画

    # 画面を更新
    pygame.display.flip()

    # フレームレートを60に設定
    clock.tick(60)

# --- 終了処理 ---
cap.release()
pygame.quit()
