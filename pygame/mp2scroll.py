import cv2
import mediapipe as mp
import pygame
import math

# --- 初期設定 ---

# MediaPipeの手検出モデルと描画ツールを準備
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

# Pygameの初期化
pygame.init()

# Pygameウィンドウの設定
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Bouldering Game (Infinite Climb)")

# 色の定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
SKY_BLUE = (135, 206, 235) # 背景がない場合の空の色

# プレイヤー（カーソル）の設定
cursor_pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
cursor_radius = 15 # 円を小さく
GRAVITY = 5 # 重力（落下速度）

# Webカメラの準備
cap = cv2.VideoCapture(0)

# --- ★無限スクロール用の背景設定 ---
background_tiles = []
bg_image_height = 0
try:
    background_image = pygame.image.load("image/iceclimbrock.png").convert()
    bg_image_height = background_image.get_height()
    
    # 画面を埋めるのに必要なタイル数を計算 (+1はスクロール時の予備)
    num_tiles = math.ceil(SCREEN_HEIGHT / bg_image_height) + 1
    
    # 初期タイルをリストに追加
    for i in range(num_tiles):
        # タイルを画面下から上へ順番に配置
        rect = background_image.get_rect(topleft=(0, SCREEN_HEIGHT - bg_image_height * (i + 1)))
        background_tiles.append(rect)

except FileNotFoundError:
    print("エラー: image/iceclimbrock.png が見つかりません。")
    background_image = None

# 掴んでいる状態を管理する変数
is_holding = False
last_hand_y = 0  # 1フレーム前の手のY座標

# --- 関数定義 ---

def is_hand_open(hand_landmarks):
    """
    手のランドマークから、その手が開いている（パー）か閉じている（グー）かを判定する関数。
    """
    tip_ids = [
        mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP
    ]
    pip_ids = [
        mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
        mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP
    ]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) 
                       if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

# --- メインループ ---
running = True
clock = pygame.time.Clock()

while running and cap.isOpened():
    # 1. イベント処理 (PygameとOpenCV)
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            running = False

    success, image = cap.read()
    if not success: continue

    # 2. 手の検出
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    results = hands.process(image)

    # 3. カメラ映像の表示
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    cv2.imshow('MediaPipe Hands', image)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or cv2.getWindowProperty('MediaPipe Hands', cv2.WND_PROP_VISIBLE) < 1:
        running = False

    # 4. ジェスチャーとゲームロジック
    is_grabbing = False
    active_hand_pos = None

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            is_open = is_hand_open(hand_landmarks)
            mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
            hand_x = int(mcp_landmark.x * SCREEN_WIDTH)
            hand_y = int(mcp_landmark.y * SCREEN_HEIGHT)
            
            active_hand_pos = (hand_x, hand_y)
            if not is_open:
                is_grabbing = True
                # 複数検出時はどちらかの手で掴んでいればOK
                break

    if active_hand_pos:
        cursor_pos[0], cursor_pos[1] = active_hand_pos
    
    # ★掴みとスクロールのロジック
    drag_amount = 0
    if is_grabbing and active_hand_pos:
        if not is_holding: # 掴んだ瞬間
            is_holding = True
            last_hand_y = active_hand_pos[1]
        
        # 掴んでいる間の移動量を計算
        drag_amount = active_hand_pos[1] - last_hand_y
        last_hand_y = active_hand_pos[1]
    else: # 手を離した
        is_holding = False
        drag_amount = -GRAVITY # 重力で落下（背景が上にスクロール）

    # 背景タイルの位置を更新
    if background_image:
        for tile_rect in background_tiles:
            tile_rect.y += drag_amount

        # ★無限スクロールの管理
        # 一番上のタイルが画面内に見えてきたら、さらにその上にもう一枚追加
        top_tile = background_tiles[0]
        if top_tile.y > -bg_image_height:
             new_rect = background_image.get_rect(topleft=(0, top_tile.y - bg_image_height))
             background_tiles.insert(0, new_rect)

        # 一番下のタイルが完全に画面外に出たら、リストから削除
        bottom_tile = background_tiles[-1]
        if bottom_tile.y > SCREEN_HEIGHT:
            background_tiles.pop()


    # 5. Pygameの描画処理
    if background_image:
        for tile_rect in background_tiles:
            screen.blit(background_image, tile_rect)
    else:
        screen.fill(SKY_BLUE) # 背景がない場合は空の色
    
    # プレイヤー（カーソル）を描画
    pygame.draw.circle(screen, RED, cursor_pos, cursor_radius)
    pygame.display.flip()

    clock.tick(60)

# --- 終了処理 ---
cap.release()
cv2.destroyAllWindows()
pygame.quit()
