import cv2
import mediapipe as mp
import pygame
import math
import random

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

# --- ゲーム設定と物理定義 ---
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
GREEN = (0, 255, 0) # ★修正点：GREENの定義を追加
BLACK = (0, 0, 0)
SKY_BLUE = (135, 206, 235)
font = pygame.font.Font(None, 50)

# プレイヤー（カーソル）の設定
cursor_pos = [SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2]
cursor_radius = 15

# Webカメラの準備
cap = cv2.VideoCapture(0)

# --- 100mの壁を生成 ---
full_background = None
try:
    tile_image = pygame.image.load("image/backsnow.png").convert()
    tile_height = tile_image.get_height()
    full_background = pygame.Surface((SCREEN_WIDTH, TOTAL_CLIMB_PIXELS))
    for y in range(0, TOTAL_CLIMB_PIXELS, tile_height):
        full_background.blit(tile_image, (0, y))

except FileNotFoundError:
    print("エラー: image/backsnow.png が見つかりません。")

# 背景スクロール用の変数
if full_background:
    max_scroll = full_background.get_height() - SCREEN_HEIGHT
    world_y_offset = max_scroll # スタート時は一番下
else:
    max_scroll = 0
    world_y_offset = 0

# --- ホールド（掴む岩）の生成 ---
holds_list = [] # ワールド座標系でのホールドのRectを格納
hold_image = None
try:
    hold_image = pygame.image.load("image/blockcatch.png").convert_alpha() # 透過をサポート
    hold_rect = hold_image.get_rect()
    hold_width, hold_height = hold_rect.width, hold_rect.height
    
    # スタート時の画面中央付近（ワールド座標の最後の方）から生成を開始
    current_y = TOTAL_CLIMB_PIXELS - (SCREEN_HEIGHT // 2)
    side = 0 # 0=左, 1=右
    
    while current_y > 0: # 頂上(0)に達するまで
        y_variation = random.randint(-PIXELS_PER_METER // 4, PIXELS_PER_METER // 4)
        h_y = current_y + y_variation
        
        x_variation = random.randint(-80, 80)
        if side == 0:
            h_x = (SCREEN_WIDTH / 4) - (hold_width / 2) + x_variation
        else:
            h_x = (SCREEN_WIDTH * 3 / 4) - (hold_width / 2) + x_variation
        
        holds_list.append(pygame.Rect(h_x, h_y, hold_width, hold_height))
        
        current_y -= PIXELS_PER_METER
        side = 1 - side # 左右を交互に

except FileNotFoundError:
    print("エラー: image/blockcatch.png が見つかりません。")


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
    
    cursor_rect = pygame.Rect(cursor_pos[0] - cursor_radius, cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)

    visible_holds_for_drawing = []
    colliding_hold = None
    if hold_image:
        min_y_world = world_y_offset
        max_y_world = world_y_offset + SCREEN_HEIGHT
        
        for hold_rect_world in holds_list:
            if hold_rect_world.bottom > min_y_world and hold_rect_world.top < max_y_world:
                screen_rect = hold_rect_world.move(0, -world_y_offset)
                visible_holds_for_drawing.append(screen_rect) 
                
                if colliding_hold is None and cursor_rect.colliderect(screen_rect):
                    colliding_hold = screen_rect
    
    can_grab = is_grabbing and (colliding_hold is not None)

    if can_grab:
        if not is_holding: 
            is_holding = True
            hold_start_y = active_hand_pos[1]
            world_hold_start_y = world_y_offset
        
        pull_distance = active_hand_pos[1] - hold_start_y
        if pull_distance < 0: pull_distance = 0
        if pull_distance > MAX_PULL_PIXELS: pull_distance = MAX_PULL_PIXELS
        world_y_offset = world_hold_start_y - pull_distance

    else: 
        is_holding = False
        world_y_offset += GRAVITY
    
    if world_y_offset > max_scroll: world_y_offset = max_scroll
    if world_y_offset < 0: world_y_offset = 0

    # 5. Pygameの描画処理
    if full_background:
        screen.blit(full_background, (0, -world_y_offset))
    else:
        screen.fill(SKY_BLUE)
    
    if hold_image:
        for rect in visible_holds_for_drawing:
            screen.blit(hold_image, rect)
    
    height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
    height_text = font.render(f"Height: {height_climbed:.1f} m", True, BLACK)
    pygame.draw.rect(screen, WHITE, (5, 5, height_text.get_width() + 10, height_text.get_height()))
    screen.blit(height_text, (10, 5))
    
    cursor_color = RED
    if is_holding:
        cursor_color = GREEN # 掴んでいるときは緑
    pygame.draw.circle(screen, cursor_color, cursor_pos, cursor_radius)
    
    pygame.display.flip()

    clock.tick(60)

# --- 終了処理 ---
cap.release()
cv2.destroyAllWindows()
pygame.quit()