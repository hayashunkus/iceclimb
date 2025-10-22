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

# --- ★ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360  # 1メートルあたりのピクセル数 (720px / 2m)
TOTAL_CLIMB_METERS = 100.0
MAX_PULL_METERS = 1.0

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)
GRAVITY = 5 # 落下速度

# Pygameウィンドウの設定
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Bouldering Game ({int(TOTAL_CLIMB_METERS)}m Climb)")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
font = pygame.font.Font(None, 50)

# プレイヤー（カーソル）の設定
cursor_pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
cursor_radius = 15

# Webカメラの準備
cap = cv2.VideoCapture(0)

# --- ★100mの壁を生成 ---
full_background = None
try:
    tile_image = pygame.image.load("image/iceclimbrock.png").convert()
    tile_height = tile_image.get_height()
    
    # 100m分の高さを持つ巨大なサーフェスを作成
    full_background = pygame.Surface((SCREEN_WIDTH, TOTAL_CLIMB_PIXELS))
    
    # タイル画像で巨大サーフェスを埋める
    for y in range(0, TOTAL_CLIMB_PIXELS, tile_height):
        full_background.blit(tile_image, (0, y))

except FileNotFoundError:
    print("エラー: image/iceclimbrock.png が見つかりません。")

# 背景スクロール用の変数
if full_background:
    max_scroll = full_background.get_height() - SCREEN_HEIGHT
    world_y_offset = max_scroll # スタート時は一番下
else:
    max_scroll = 0
    world_y_offset = 0

# 掴んでいる状態を管理する変数
is_holding = False
hold_start_y = 0      # 掴み始めた時の「手のY座標」
world_hold_start_y = 0  # 掴み始めた時の「背景のY座標」

# --- 関数定義 ---
def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
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
            if not is_hand_open(hand_landmarks): is_grabbing = True
            mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
            active_hand_pos = (int(mcp_landmark.x * SCREEN_WIDTH), int(mcp_landmark.y * SCREEN_HEIGHT))
            if is_grabbing: break
    if active_hand_pos: cursor_pos[:] = active_hand_pos
    
    # ★掴みとスクロールのロジック（プル制限付き）
    if is_grabbing and active_hand_pos:
        if not is_holding: # 掴んだ瞬間
            is_holding = True
            hold_start_y = active_hand_pos[1]
            world_hold_start_y = world_y_offset
        
        # 掴んだ位置からの移動距離を計算
        pull_distance = active_hand_pos[1] - hold_start_y
        
        # 移動距離が0未満（上に押している）場合は無視
        if pull_distance < 0:
            pull_distance = 0
            
        # ★1回のプル距離を1m（MAX_PULL_PIXELS）に制限
        if pull_distance > MAX_PULL_PIXELS:
            pull_distance = MAX_PULL_PIXELS
            
        # 背景をスクロール
        world_y_offset = world_hold_start_y - pull_distance

    else: # 手を離した
        is_holding = False
        # 重力で落下
        world_y_offset += GRAVITY
    
    # スクロール範囲の制限 (0が頂上、max_scrollが地上)
    if world_y_offset > max_scroll: world_y_offset = max_scroll
    if world_y_offset < 0: world_y_offset = 0

    # 5. Pygameの描画処理
    if full_background:
        screen.blit(full_background, (0, -world_y_offset))
    else:
        screen.fill(SKY_BLUE)
    
    # ★高度表示UIを描画
    height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
    height_text = font.render(f"Height: {height_climbed:.1f} m", True, BLACK)
    # 文字の背景を描画
    pygame.draw.rect(screen, WHITE, (5, 5, height_text.get_width() + 10, height_text.get_height()))
    screen.blit(height_text, (10, 5))
    
    # プレイヤー（カーソル）を描画
    pygame.draw.circle(screen, RED, cursor_pos, cursor_radius)
    pygame.display.flip()

    clock.tick(60)

# --- 終了処理 ---
cap.release()
cv2.destroyAllWindows()
pygame.quit()
