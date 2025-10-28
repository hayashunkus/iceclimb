import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np
import sys
import time # 時間計測用にインポート

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
pygame.font.init()

# --- 画面レイアウト定義 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
LEFT_PANEL_WIDTH = int(SCREEN_WIDTH * 0.2)
GAME_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH
GAME_HEIGHT = SCREEN_HEIGHT

SCORE_PANEL_RECT = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.4))
LOG_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
CAM_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height + LOG_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
GAME_PANEL_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, GAME_PANEL_WIDTH, GAME_HEIGHT)


# --- ★ 敵クラス ---
class Enemy(pygame.sprite.Sprite):
    def __init__(self, image, hp, enemy_type):
        super().__init__()
        self.original_image = image
        self.image = image
        self.rect = self.image.get_rect()
        self.hp = hp
        self.max_hp = hp
        self.enemy_type = enemy_type # "purple", "red", "orange"
        self.speed = random.randint(1, 3) # 移動速度
        self.direction = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize() # 移動方向

        self.spawn_random_corner() # 四隅のどこかに出現

    def spawn_random_corner(self):
        corner = random.randint(0, 3) # 0:左上, 1:右上, 2:左下, 3:右下
        padding = 50 # 画面端からのオフセット
        if corner == 0: # 左上
            self.rect.topleft = (padding, padding)
        elif corner == 1: # 右上
            self.rect.topright = (GAME_PANEL_WIDTH - padding, padding)
        elif corner == 2: # 左下
            self.rect.bottomleft = (padding, GAME_HEIGHT - padding)
        else: # 右下
            self.rect.bottomright = (GAME_PANEL_WIDTH - padding, GAME_HEIGHT - padding)
        
        # 画面中央に向かうように初期方向を調整
        center = pygame.Vector2(GAME_PANEL_WIDTH / 2, GAME_HEIGHT / 2)
        current_pos = pygame.Vector2(self.rect.centerx, self.rect.centery)
        self.direction = (center - current_pos).normalize()

    def update(self):
        # 画面内をランダムに動き回る
        self.rect.x += self.direction.x * self.speed
        self.rect.y += self.direction.y * self.speed

        # 画面端での反射
        if self.rect.left < 0 or self.rect.right > GAME_PANEL_WIDTH:
            self.direction.x *= -1
            if self.rect.left < 0: self.rect.left = 0
            if self.rect.right > GAME_PANEL_WIDTH: self.rect.right = GAME_PANEL_WIDTH
        if self.rect.top < 0 or self.rect.bottom > GAME_HEIGHT:
            self.direction.y *= -1
            if self.rect.top < 0: self.rect.top = 0
            if self.rect.bottom > GAME_HEIGHT: self.rect.bottom = GAME_HEIGHT

        # 体力に応じて色を暗くする (赤とオレンジの敵のみ)
        if self.enemy_type == "red" or self.enemy_type == "orange":
            damage_ratio = (self.max_hp - self.hp) / self.max_hp
            darken_factor = 1.0 - (damage_ratio * 0.5) # 0%ダメージで1.0, 100%ダメージで0.5に
            
            # 画像をコピーして色を調整
            temp_image = self.original_image.copy()
            alpha_surface = pygame.Surface(temp_image.get_size(), pygame.SRCALPHA)
            alpha_surface.fill((255, 255, 255, int(255 * darken_factor))) # アルファ値を調整
            temp_image.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.image = temp_image
        else:
            self.image = self.original_image # 紫色の敵は常に元の画像

    def take_damage(self, amount):
        self.hp -= amount
        return self.hp <= 0

    def draw(self, surface):
        surface.blit(self.image, self.rect)

# --- ゲーム設定と物理定義 (今回は不使用) ---
FPS = 60 # フレームレート

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Dekopin Challenge")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
YELLOW = (255, 255, 0)
BUTTON_COLOR = (0, 100, 200)
BUTTON_HOVER_COLOR = (0, 150, 255)
BUTTON_TEXT_COLOR = WHITE
RADIO_BUTTON_COLOR = WHITE
RADIO_BUTTON_SELECTED_COLOR = GREEN
DARK_RED = (139, 0, 0)

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
game_over_font = pygame.font.Font(None, 80)
result_text_font = pygame.font.Font(None, 60)
button_font = pygame.font.Font(None, 50)
button_font_small = pygame.font.Font(None, 30)

# --- アセット読み込み ---
enemy_images = {}
try:
    img_purple = pygame.image.load("image/enemy.png").convert_alpha()
    img_purple = pygame.transform.scale(img_purple, (70, 70))
    enemy_images["purple"] = img_purple

    img_red = pygame.image.load("image/enemy_red.png").convert_alpha()
    img_red = pygame.transform.scale(img_red, (80, 80))
    enemy_images["red"] = img_red

    img_orange = pygame.image.load("image/dekoenemy.png").convert_alpha()
    img_orange = pygame.transform.scale(img_orange, (300, 300))
    enemy_images["orange"] = img_orange
except FileNotFoundError as e:
    print(f"エラー: 敵画像が見つかりません。 {e}")
    pygame.quit()
    sys.exit()

# ダンサーアニメーション画像の読み込み (成功画面用)
dancer_images = []
dancer_frame = 0
dancer_frame_time = 0
ANIMATION_SPEED_MS = 100
try:
    for i in range(1, 6):
        img_path = f"image/c-dancer-{i}.png"
        img = pygame.image.load(img_path).convert_alpha()
        img = pygame.transform.scale(img, (200, 200))
        dancer_images.append(img)
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")


# --- ゲームオブジェクト ---
enemies = pygame.sprite.Group() # 敵グループ

# プレイヤー（カーソル）の設定
left_cursor_pos = [-100, -100] # MCP (手のひら) の位置
right_cursor_pos = [-100, -100]
left_flick_pos = [-100, -100] # TIP (中指先端) の位置
right_flick_pos = [-100, -100]
dekopin_range_radius_default = 70 # ★修正: デフォルトの半径 (デバッグ用)
left_dekopin_radius = dekopin_range_radius_default # ★追加: 動的半径
right_dekopin_radius = dekopin_range_radius_default # ★追加: 動的半径

# ★ デコピン検出用 (サンプルコードベース)
FLICK_THRESHOLD = 40 # フリック検知の速度しきい値
left_middle_tip_history = [[0, 0], [0, 0]] # ★修正: [古い[x,y], 新しい[x,y]]
right_middle_tip_history = [[0, 0], [0, 0]] # ★修正: [古い[x,y], 新しい[x,y]]
TAME_DISTANCE_THRESHOLD = 0.05 # 溜め判定のしきい値 (親指と中指の距離)

# Webカメラの準備
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")

# --- ゲーム状態管理 ---
game_state = 'READY' # 'READY', 'DEKOPIN_CHALLENGE', 'GAMEOVER_TIMEUP', 'GAMEOVER_ENEMY_OVERFLOW'

# --- タイマー変数 ---
start_time = 0
elapsed_time = 0
game_duration_ms = 60 * 1000 # 1分 = 60000ミリ秒
enemy_spawn_timer = 0
enemy_spawn_interval = 1000 / 4 # 毎秒4体なので、1体あたり250ms

# --- スコアと敵の生成カウンター ---
score = 0
purple_enemies_spawned = 0 # 赤が出てから何体紫が出たか
red_enemies_spawned = 0 # オレンジが出てから何体赤が出たか
enemy_count_on_screen = 0
MAX_ENEMIES_ON_SCREEN = 40 # 画面上の最大敵数

# --- UI要素 ---
start_button_rect_screen = pygame.Rect(0, 0, 200, 80)
start_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.centery)
retry_button_rect_screen = pygame.Rect(0, 0, 300, 60)
retry_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.bottom - 80)

# --- 説明テキスト ---
instructions = [
    "--- Dekopin mode ---",
    "1. Put your hand over",
    "   the START button.",
    "2. Flick your finger ",
    "   (thumb + middle) to start.",
    "3. Dekopin (flick your",
    "   middle finger) enemies!",
    "4. Yellow: Charge", 
    "   Green: HIT!", 
    "   (Purple:1 Red:3 Orange:5)", 
    "5. Don't let too many",
    "   enemies pile up! (Max 50)",
]

# --- 関数定義 ---

# ★追加: 手が開いているか判定 (サンプルコードより)
def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    # 3本以上開いていれば「開いている」
    return open_fingers >= 3

def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

# ★修正: 溜め（チャージ）状態の判定 (変更なし)
def is_hand_tame(hand_landmarks):
    """親指の先端と中指の先端が近いか（溜め状態か）を判定"""
    if not hand_landmarks:
        return False
    
    thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
    middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
    
    # 2D距離で判定 (Z座標は考慮しない)
    distance = math.sqrt((thumb_tip.x - middle_tip.x)**2 + (thumb_tip.y - middle_tip.y)**2)
    
    return distance < TAME_DISTANCE_THRESHOLD

# ★ is_dekopin_motion は不要になった (ロジックをメインループ内に移行)

# ★ ゲームリセット関数
def reset_game():
    global game_state, elapsed_time, score, purple_enemies_spawned, red_enemies_spawned, \
        enemy_count_on_screen, start_time, enemy_spawn_timer, \
        left_hand_state, right_hand_state, left_marker_color, right_marker_color, \
        left_middle_tip_history, right_middle_tip_history, \
        left_dekopin_radius, right_dekopin_radius # ★追加

    game_state = 'READY'
    elapsed_time = 0
    score = 0
    purple_enemies_spawned = 0
    red_enemies_spawned = 0
    enemy_count_on_screen = 0
    enemies.empty() # 敵をすべて削除
    start_time = 0
    enemy_spawn_timer = 0
    
    # 手の状態をリセット
    left_hand_state = 'OPEN'
    right_hand_state = 'OPEN'
    left_marker_color = None
    right_marker_color = None
    left_middle_tip_history = [[0, 0], [0, 0]] # ★修正
    right_middle_tip_history = [[0, 0], [0, 0]] # ★修正
    left_dekopin_radius = dekopin_range_radius_default # ★追加
    right_dekopin_radius = dekopin_range_radius_default # ★追加

    global cap
    if not cap.isOpened():
       cap = cv2.VideoCapture(0)
       if cap.isOpened():
           print("Camera reopened for retry.")
       else:
           print("Error: Failed to reopen camera for retry.")


# --- メインループ ---
running = True
clock = pygame.time.Clock()
camera_surface_scaled = None
last_dekopin_left = 0
last_dekopin_right = 0
DEKOPIN_COOLDOWN = 300 # デコピンのクールダウン時間 (ms)

# ★追加: 手の状態管理変数
left_hand_state = 'OPEN' # 'OPEN', 'TAME'
right_hand_state = 'OPEN'
left_marker_color = None # None, YELLOW_MARKER, GREEN_MARKER
right_marker_color = None

# ★追加: マーカー色の定義
ALPHA_VALUE = 80 # 透明度
YELLOW_MARKER = (255, 255, 0, ALPHA_VALUE)
GREEN_MARKER = (0, 255, 0, ALPHA_VALUE)

while running:

    delta_time_ms = clock.tick(FPS)
    mouse_pos = pygame.mouse.get_pos()
    mouse_click = False

    # 1. イベント処理
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False
            # (デバッグ用のK_SPACE)
            if event.key == pygame.K_SPACE and GAME_PANEL_RECT.collidepoint(mouse_pos):
                # ★デバッグ用のデコピン位置をマウスカーソル基準にする
                mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
                mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
                # ★デバッグではデフォルト半径を使用
                dekopin_hit_circle = pygame.Rect(mouse_x_in_game - dekopin_range_radius_default, mouse_y_in_game - dekopin_range_radius_default, dekopin_range_radius_default * 2, dekopin_range_radius_default * 2)
                
                hit_found_debug = False
                for enemy in list(enemies):
                    if enemy.rect.colliderect(dekopin_hit_circle):
                        hit_found_debug = True
                        if enemy.take_damage(1):
                            enemies.remove(enemy)
                            enemy_count_on_screen -= 1
                            score += 1
                # (デバッグではマーカー色を変えない)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mouse_click = True

    # 画面全体をクリア
    screen.fill(GRAY)

    # --- カメラ処理 & 手の検出 (常に実行) ---
    dekopin_left_this_frame = False
    dekopin_right_this_frame = False
    results = None
    hand_detected = False

    # ★ マーカー色をリセット (黄色は毎フレーム判定、緑はヒット時のみ設定)
    left_marker_color = None
    right_marker_color = None

    if cap.isOpened():
        success, image_cam = cap.read()
        if success:
            image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = hands.process(image_rgb)
            image_rgb.flags.writeable = True

            image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
            if results and results.multi_hand_landmarks:
                hand_detected = True
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
            camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))

            left_cursor_pos[:] = [-100, -100]
            right_cursor_pos[:] = [-100, -100]
            left_flick_pos[:] = [-100, -100]
            right_flick_pos[:] = [-100, -100]

            if results and results.multi_hand_landmarks:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    
                    # ★ 必要なランドマークを取得
                    mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                    tip_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                    pip_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP] # ★追加: 第2関節
                    
                    hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))
                    flick_pos = (int(tip_landmark.x * GAME_PANEL_WIDTH), int(tip_landmark.y * GAME_HEIGHT))
                    pip_pos = (int(pip_landmark.x * GAME_PANEL_WIDTH), int(pip_landmark.y * GAME_HEIGHT)) # ★追加
                    
                    # ★ 状態判定
                    is_open = is_hand_open(hand_landmarks)
                    is_tame = is_hand_tame(hand_landmarks)

                    # ★追加: 動的半径の計算
                    distance_px = math.sqrt((flick_pos[0] - pip_pos[0])**2 + (flick_pos[1] - pip_pos[1])**2)
                    dynamic_radius = distance_px * 1.2
                    # 半径に制限をかける (小さすぎ/大きすぎ防止)
                    dynamic_radius = max(30, min(150, dynamic_radius)) 
                    
                    if handedness.classification[0].label == 'Left': # カメラ映像が反転しているので、ラベルも反転
                        right_cursor_pos[:] = hand_pos # 右手として扱う (MCP)
                        right_flick_pos[:] = flick_pos # (TIP)
                        right_dekopin_radius = dynamic_radius # ★追加

                        # ★修正: 8方向フリック速度計算
                        right_middle_tip_history[0] = right_middle_tip_history[1]
                        right_middle_tip_history[1] = flick_pos
                        vel_x = right_middle_tip_history[1][0] - right_middle_tip_history[0][0]
                        vel_y = right_middle_tip_history[1][1] - right_middle_tip_history[0][1]
                        flick_velocity_magnitude = math.sqrt(vel_x**2 + vel_y**2)
                        
                        is_flick = is_open and (flick_velocity_magnitude > FLICK_THRESHOLD)

                        if is_tame:
                            right_hand_state = 'TAME'
                            right_marker_color = YELLOW_MARKER
                        elif right_hand_state == 'TAME' and is_flick:
                            right_hand_state = 'OPEN' # 状態をリセット
                            # (マーカーはヒット判定後に緑にする)
                            if pygame.time.get_ticks() - last_dekopin_right > DEKOPIN_COOLDOWN:
                                dekopin_right_this_frame = True
                                last_dekopin_right = pygame.time.get_ticks()
                        elif not is_tame:
                             right_hand_state = 'OPEN'

                    elif handedness.classification[0].label == 'Right': # カメラ映像が反転しているので、ラベルも反転
                        left_cursor_pos[:] = hand_pos # 左手として扱う (MCP)
                        left_flick_pos[:] = flick_pos # (TIP)
                        left_dekopin_radius = dynamic_radius # ★追加

                        # ★修正: 8方向フリック速度計算
                        left_middle_tip_history[0] = left_middle_tip_history[1]
                        left_middle_tip_history[1] = flick_pos
                        vel_x = left_middle_tip_history[1][0] - left_middle_tip_history[0][0]
                        vel_y = left_middle_tip_history[1][1] - left_middle_tip_history[0][1]
                        flick_velocity_magnitude = math.sqrt(vel_x**2 + vel_y**2)

                        is_flick = is_open and (flick_velocity_magnitude > FLICK_THRESHOLD)

                        if is_tame:
                            left_hand_state = 'TAME'
                            left_marker_color = YELLOW_MARKER
                        elif left_hand_state == 'TAME' and is_flick:
                            left_hand_state = 'OPEN' # 状態をリセット
                            # (マーカーはヒット判定後に緑にする)
                            if pygame.time.get_ticks() - last_dekopin_left > DEKOPIN_COOLDOWN:
                                dekopin_left_this_frame = True
                                last_dekopin_left = pygame.time.get_ticks()
                        elif not is_tame:
                            left_hand_state = 'OPEN'
            
        else:
             if cap.isOpened():
                 print("Warning: Failed to read frame from camera.")
             left_cursor_pos[:] = [-100, -100]
             right_cursor_pos[:] = [-100, -100]
             left_flick_pos[:] = [-100, -100]
             right_flick_pos[:] = [-100, -100]

    else:
        left_cursor_pos[:] = [-100, -100]
        right_cursor_pos[:] = [-100, -100]
        left_flick_pos[:] = [-100, -100]
        right_flick_pos[:] = [-100, -100]


    # --- ゲームロジック (状態に基づいて実行) ---

    # (cursor_rect_gameは不要になった)
    start_button_rect_game = start_button_rect_screen.copy()
    start_button_rect_game.center = (start_button_rect_screen.centerx - GAME_PANEL_RECT.left, start_button_rect_screen.centery - GAME_PANEL_RECT.top)
    retry_button_rect_game = retry_button_rect_screen.copy()
    retry_button_rect_game.center = (retry_button_rect_screen.centerx - GAME_PANEL_RECT.left, GAME_HEIGHT - 80)

    if game_state == 'READY':
        start_activated = False
        
        # ★修正: スタートボタン上で「デコピン攻撃(フリック)」をしたときにスタート
        if dekopin_left_this_frame: 
            # ★ 当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
            dekopin_hit_circle_left = pygame.Rect(left_flick_pos[0] - left_dekopin_radius, left_flick_pos[1] - left_dekopin_radius, left_dekopin_radius * 2, left_dekopin_radius * 2)
            if start_button_rect_game.colliderect(dekopin_hit_circle_left):
                start_activated = True
                left_marker_color = GREEN_MARKER # ★ヒットしたので緑
        elif dekopin_right_this_frame:
            # ★ 当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
            dekopin_hit_circle_right = pygame.Rect(right_flick_pos[0] - right_dekopin_radius, right_flick_pos[1] - right_dekopin_radius, right_dekopin_radius * 2, right_dekopin_radius * 2)
            if start_button_rect_game.colliderect(dekopin_hit_circle_right):
                start_activated = True
                right_marker_color = GREEN_MARKER # ★ヒットしたので緑
        
        # マウスでクリックしてもスタートできるように
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        if start_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game) and mouse_click:
            start_activated = True

        if start_activated:
            game_state = 'DEKOPIN_CHALLENGE'
            start_time = pygame.time.get_ticks()
            score = 0
            purple_enemies_spawned = 0
            red_enemies_spawned = 0
            enemy_count_on_screen = 0
            enemies.empty()
            enemy_spawn_timer = 0
            print("Dekopin Challenge Started!")

    elif game_state == 'DEKOPIN_CHALLENGE':
        elapsed_time = pygame.time.get_ticks() - start_time

        # 時間切れ判定
        if elapsed_time >= game_duration_ms:
            game_state = 'GAMEOVER_TIMEUP'
            print("Game Over: Time's Up!")

        # 敵の生成
        enemy_spawn_timer += delta_time_ms
        while enemy_spawn_timer >= enemy_spawn_interval:
            enemy_spawn_timer -= enemy_spawn_interval

            new_enemy = None
            # ★修正: オレンジのHPを 5 に
            if red_enemies_spawned >= 2 and enemy_images.get("orange"):
                # 赤が2体出たら、次はオレンジ
                new_enemy = Enemy(enemy_images["orange"], 5, "orange") 
                red_enemies_spawned = 0 # リセット
            elif purple_enemies_spawned >= 10 and enemy_images.get("red"):
                # 紫が10体出たら、次は赤
                new_enemy = Enemy(enemy_images["red"], 3, "red")
                purple_enemies_spawned = 0 # リセット
                red_enemies_spawned += 1
            else:
                # 通常は紫
                new_enemy = Enemy(enemy_images["purple"], 1, "purple")
                purple_enemies_spawned += 1
            
            if new_enemy:
                enemies.add(new_enemy)
                enemy_count_on_screen += 1
            
            if enemy_count_on_screen > MAX_ENEMIES_ON_SCREEN:
                game_state = 'GAMEOVER_ENEMY_OVERFLOW'
                print("Game Over: Too many enemies!")
                break 

        # 敵の更新
        enemies.update()

        # デコピン処理
        hit_dekopin_left = False
        hit_dekopin_right = False
        
        if dekopin_left_this_frame and left_flick_pos[0] != -100:
            hit_dekopin_left = True
        if dekopin_right_this_frame and right_flick_pos[0] != -100:
            hit_dekopin_right = True
        
        hit_found_this_frame_left = False # ★修正: 左右別々にヒット判定
        hit_found_this_frame_right = False

        if hit_dekopin_left:
            # ★ 当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
            dekopin_hit_circle = pygame.Rect(left_flick_pos[0] - left_dekopin_radius, left_flick_pos[1] - left_dekopin_radius, left_dekopin_radius * 2, left_dekopin_radius * 2)
            for enemy in list(enemies): 
                if enemy.rect.colliderect(dekopin_hit_circle):
                    hit_found_this_frame_left = True
                    if enemy.take_damage(1): 
                        enemies.remove(enemy)
                        enemy_count_on_screen -= 1
                        score += 1
            if hit_found_this_frame_left:
                left_marker_color = GREEN_MARKER # ★ヒットしたので緑
        
        if hit_dekopin_right:
            # ★ 当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
            dekopin_hit_circle = pygame.Rect(right_flick_pos[0] - right_dekopin_radius, right_flick_pos[1] - right_dekopin_radius, right_dekopin_radius * 2, right_dekopin_radius * 2)
            for enemy in list(enemies): 
                if enemy.rect.colliderect(dekopin_hit_circle):
                    hit_found_this_frame_right = True
                    if enemy.take_damage(1): 
                        enemies.remove(enemy)
                        enemy_count_on_screen -= 1
                        score += 1
            if hit_found_this_frame_right:
                right_marker_color = GREEN_MARKER # ★ヒットしたので緑


    elif game_state == 'GAMEOVER_TIMEUP' or game_state == 'GAMEOVER_ENEMY_OVERFLOW':
        # リトライボタンの処理
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top

        if retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game) and mouse_click:
            reset_game()

    # --- 描画処理 ---

    # --- ゲームパネル (右側) ---
    game_surface = screen.subsurface(GAME_PANEL_RECT)
    game_surface.fill(SKY_BLUE)

    if game_state == 'GAMEOVER_TIMEUP' or game_state == 'GAMEOVER_ENEMY_OVERFLOW':
        # (ゲームオーバー画面の描画 - 変更なし)
        if game_state == 'GAMEOVER_TIMEUP':
            go_text = game_over_font.render("TIME UP!", True, DARK_RED)
            game_surface.blit(go_text, go_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 - 100)))
            result_text = result_text_font.render(f"Score: {score} enemies", True, BLACK)
            game_surface.blit(result_text, result_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2)))
        elif game_state == 'GAMEOVER_ENEMY_OVERFLOW':
            go_text = game_over_font.render("GAME OVER", True, DARK_RED)
            game_surface.blit(go_text, go_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 - 100)))
            reason_text = font_ui.render("Too many enemies!", True, BLACK)
            game_surface.blit(reason_text, reason_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 - 30)))
            result_text = result_text_font.render(f"Score: {score} enemies", True, BLACK)
            game_surface.blit(result_text, result_text.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 + 30)))

        if game_state == 'GAMEOVER_TIMEUP' and dancer_images: 
            dancer_frame_time += delta_time_ms
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0
            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(GAME_PANEL_WIDTH // 2, GAME_HEIGHT // 2 + 150))
            game_surface.blit(current_dancer_image, img_rect)

        # リトライボタン
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)
        btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
        pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
        btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
        game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    else: # READY, DEKOPIN_CHALLENGE
        enemies.draw(game_surface) # 敵を描画

        if game_state == 'READY':
            # ★ホバー判定は「溜め(黄色)」のマーカーが出ている時
            is_hovering_start = False
            if left_marker_color == YELLOW_MARKER:
                # ★当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
                dekopin_hit_circle_left_game = pygame.Rect(left_flick_pos[0] - left_dekopin_radius, left_flick_pos[1] - left_dekopin_radius, left_dekopin_radius * 2, left_dekopin_radius * 2)
                if start_button_rect_game.colliderect(dekopin_hit_circle_left_game):
                    is_hovering_start = True
            if right_marker_color == YELLOW_MARKER:
                # ★当たり判定の中心を flick_pos (中指先端)＆動的半径に変更
                dekopin_hit_circle_right_game = pygame.Rect(right_flick_pos[0] - right_dekopin_radius, right_flick_pos[1] - right_dekopin_radius, right_dekopin_radius * 2, right_dekopin_radius * 2)
                if start_button_rect_game.colliderect(dekopin_hit_circle_right_game):
                    is_hovering_start = True
                 
            # マウスがスタートボタン上にある場合もホバー状態にする
            mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
            mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
            if start_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game):
                is_hovering_start = True

            btn_color = BUTTON_HOVER_COLOR if is_hovering_start else BUTTON_COLOR
            pygame.draw.rect(game_surface, btn_color, start_button_rect_game, border_radius=10)
            btn_text = button_font.render("START", True, BUTTON_TEXT_COLOR)
            game_surface.blit(btn_text, btn_text.get_rect(center=start_button_rect_game.center))

        # --- ★修正: カーソル（手）の描画ロジック ---
        # 決定されたマーカー色 (YELLOW_MARKER, GREEN_MARKER, or None) に基づいて描画
        
        if left_marker_color: # Noneでなければ(黄色か緑なら)描画
            # ★動的半径でSurfaceを作成
            radius = int(left_dekopin_radius)
            if radius > 0:
                dekopin_circle_surface_left = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(dekopin_circle_surface_left, left_marker_color, (radius, radius), radius)
                # ★描画位置を flick_pos (中指先端) に変更
                game_surface.blit(dekopin_circle_surface_left, (left_flick_pos[0] - radius, left_flick_pos[1] - radius))

        if right_marker_color: # Noneでなければ(黄色か緑なら)描画
            # ★動的半径でSurfaceを作成
            radius = int(right_dekopin_radius)
            if radius > 0:
                dekopin_circle_surface_right = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(dekopin_circle_surface_right, right_marker_color, (radius, radius), radius)
                # ★描画位置を flick_pos (中指先端) に変更
                game_surface.blit(dekopin_circle_surface_right, (right_flick_pos[0] - radius, right_flick_pos[1] - radius))


    # --- UIパネルの描画 ---

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("Dekopin Challenge", True, WHITE)
    score_surface.blit(title_text, (10, 10))

    score_text = font_ui.render(f"Score: {score}", True, WHITE)
    score_surface.blit(score_text, (15, 60))

    remaining_time_ms = max(0, game_duration_ms - elapsed_time) if game_state == 'DEKOPIN_CHALLENGE' else game_duration_ms
    time_text = font_ui.render(f"Time: {format_time(remaining_time_ms)}", True, WHITE)
    score_surface.blit(time_text, (15, 100))
    
    enemy_count_text = font_ui.render(f"Enemies: {enemy_count_on_screen}/{MAX_ENEMIES_ON_SCREEN}", True, RED if enemy_count_on_screen >= MAX_ENEMIES_ON_SCREEN - 3 else WHITE)
    score_surface.blit(enemy_count_text, (15, 140))


    # --- 説明パネル (左中) ---
    log_surface = screen.subsurface(LOG_PANEL_RECT)
    log_surface.fill(BLACK)
    log_title = font_title.render("HOW TO PLAY", True, WHITE)
    log_surface.blit(log_title, (10, 10))
    y_pos = 50
    for line in instructions:
        log_text = font_log.render(line, True, GREEN)
        log_surface.blit(log_text, (15, y_pos))
        # ★Y座標の増分を調整
        if "Green: HIT!" in line:
            y_pos += 20 # HP表示行の行間を詰める
        elif "Purple:1" in line:
             y_pos += 30 # 次の行間を空ける
        else:
             y_pos += 25

    # --- カメラパネル (左下) ---
    cam_surface = screen.subsurface(CAM_PANEL_RECT)
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))
    cam_title = font_title.render("CAMERA", True, WHITE)
    cam_surface.blit(cam_title, (10, 10))

    if cap.isOpened() and camera_surface_scaled:
        cam_surface.blit(camera_surface_scaled, (0, 30))
    elif not cap.isOpened():
        pass 

    # 画面更新
    pygame.display.flip()

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()
