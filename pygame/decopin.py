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
# PIXELS_PER_METER = 360
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
YELLOW = (255, 255, 0) # ★追加
BUTTON_COLOR = (0, 100, 200)
BUTTON_HOVER_COLOR = (0, 150, 255)
BUTTON_TEXT_COLOR = WHITE
RADIO_BUTTON_COLOR = WHITE
RADIO_BUTTON_SELECTED_COLOR = GREEN
DARK_RED = (139, 0, 0)

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
game_over_font = pygame.font.Font(None, 80) # 小さく調整
result_text_font = pygame.font.Font(None, 60) # 小さく調整
button_font = pygame.font.Font(None, 50)
button_font_small = pygame.font.Font(None, 30)

# --- アセット読み込み ---
enemy_images = {}
try:
    img_purple = pygame.image.load("image/enemy.png").convert_alpha()
    img_purple = pygame.transform.scale(img_purple, (70, 70)) # サイズ調整
    enemy_images["purple"] = img_purple

    img_red = pygame.image.load("image/enemy_red.png").convert_alpha()
    img_red = pygame.transform.scale(img_red, (70, 70)) # サイズ調整
    enemy_images["red"] = img_red

    img_orange = pygame.image.load("image/decoenemy.png").convert_alpha()
    img_orange = pygame.transform.scale(img_orange, (70, 70)) # サイズ調整
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
        img = pygame.transform.scale(img, (200, 200)) # サイズ調整
        dancer_images.append(img)
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")


# --- ゲームオブジェクト ---
enemies = pygame.sprite.Group() # 敵グループ

# プレイヤー（カーソル）の設定
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 20 # カーソル（手の当たり判定）の半径
dekopin_range_radius = 70 # デコピンのヒット範囲の半径 (100 -> 70)
# left_is_open_current = True (不要になった)
# right_is_open_current = True (不要になった)
# left_was_open = True (不要になった)
# right_was_open = True (不要になった)

# ★ デコピン検出用
left_index_pip_y_history = []
right_index_pip_y_history = []
DEKOPIN_THRESHOLD = 0.03 # 薬指との相対位置の変化量でデコピン判定
DEKOPIN_HISTORY_LEN = 5 # 履歴の長さ
TAME_DISTANCE_THRESHOLD = 0.05 # ★追加: 溜め判定のしきい値 (親指と中指の距離)

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
purple_enemies_spawned = 0
red_enemies_spawned = 0
enemy_count_on_screen = 0
MAX_ENEMIES_ON_SCREEN = 50 # 画面上の最大敵数

# --- UI要素 ---
start_button_rect_screen = pygame.Rect(0, 0, 200, 80)
start_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.centery)
retry_button_rect_screen = pygame.Rect(0, 0, 300, 60)
retry_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.bottom - 80)

# --- 説明テキスト ---
instructions = [
    "--- Dekopin Challenge ---",
    "1. Put your hand over",
    "   the START button.",
    "2. Flick your finger ", # ★修正
    "   (thumb + middle) to start.", # ★修正
    "3. Dekopin (flick your",
    "   middle finger) enemies!",
    "4. Yellow: Charge", # ★修正
    "   Green: Attack!", # ★修正
    "5. Don't let too many",
    "   enemies pile up! (Max 50)",
]

# --- 関数定義 ---

# def is_hand_open(hand_landmarks): (不要になったためコメントアウトまたは削除)
    # ...

def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

# ★追加: 溜め（チャージ）状態の判定
def is_hand_tame(hand_landmarks):
    """親指の先端と中指の先端が近いか（溜め状態か）を判定"""
    if not hand_landmarks:
        return False
    
    thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
    middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
    
    # 2D距離で判定 (Z座標は考慮しない)
    distance = math.sqrt((thumb_tip.x - middle_tip.x)**2 + (thumb_tip.y - middle_tip.y)**2)
    
    return distance < TAME_DISTANCE_THRESHOLD

# ★ デコピン判定関数 (フリックの「リリース」動作を検知)
def is_dekopin_motion(hand_landmarks, hand_history):
    if not hand_landmarks:
        return False
    
    middle_finger_pip_y = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_PIP].y

    hand_history.append(middle_finger_pip_y)
    if len(hand_history) > DEKOPIN_HISTORY_LEN:
        hand_history.pop(0)

    if len(hand_history) == DEKOPIN_HISTORY_LEN:
        # 履歴の最初(古い)より最後(今)が小さい(画面上方) = 急激に指が伸びた(リリース)
        if hand_history[0] > hand_history[-1] + DEKOPIN_THRESHOLD: 
             return True # デコピンとして判定
    return False

# ★ ゲームリセット関数
def reset_game():
    global game_state, elapsed_time, score, purple_enemies_spawned, red_enemies_spawned, \
        enemy_count_on_screen, start_time, enemy_spawn_timer, \
        left_hand_state, right_hand_state, left_marker_color, right_marker_color # ★修正

    game_state = 'READY'
    elapsed_time = 0
    score = 0
    purple_enemies_spawned = 0
    red_enemies_spawned = 0
    enemy_count_on_screen = 0
    enemies.empty() # 敵をすべて削除
    start_time = 0
    enemy_spawn_timer = 0
    
    # ★修正: 手の状態をリセット
    left_hand_state = 'OPEN'
    right_hand_state = 'OPEN'
    left_marker_color = None
    right_marker_color = None

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
            # (デバッグ用のK_SPACEはそのまま)
            if event.key == pygame.K_SPACE and GAME_PANEL_RECT.collidepoint(mouse_pos):
                dummy_cursor_rect = pygame.Rect(mouse_pos[0] - GAME_PANEL_RECT.left - cursor_radius, mouse_pos[1] - GAME_PANEL_RECT.top - cursor_radius, cursor_radius * 2, cursor_radius * 2)
                for enemy in enemies:
                    if enemy.rect.colliderect(dummy_cursor_rect):
                        if enemy.take_damage(1):
                            enemies.remove(enemy)
                            enemy_count_on_screen -= 1
                            score += 1
                        # break (複数ヒット許容のためコメントアウト)
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

    # ★修正: マーカー色を毎フレームリセット
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

            # left_is_open_now = True (不要)
            # right_is_open_now = True (不要)
            left_cursor_pos[:] = [-100, -100]
            right_cursor_pos[:] = [-100, -100]

            if results and results.multi_hand_landmarks:
                for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    # is_open = is_hand_open(hand_landmarks) (不要)
                    mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                    hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))

                    # ★追加: 溜め(Tame)とフリック(Flick)のモーションを判定
                    is_tame = is_hand_tame(hand_landmarks)
                    
                    if handedness.classification[0].label == 'Left': # カメラ映像が反転しているので、ラベルも反転
                        right_cursor_pos[:] = hand_pos # 右手として扱う
                        is_flick = is_dekopin_motion(hand_landmarks, right_index_pip_y_history)

                        if is_tame:
                            right_hand_state = 'TAME'
                            right_marker_color = YELLOW_MARKER
                        elif right_hand_state == 'TAME' and is_flick:
                            right_hand_state = 'OPEN' # 状態をリセット
                            right_marker_color = GREEN_MARKER
                            if pygame.time.get_ticks() - last_dekopin_right > DEKOPIN_COOLDOWN:
                                dekopin_right_this_frame = True
                                last_dekopin_right = pygame.time.get_ticks()
                        else:
                            right_hand_state = 'OPEN'
                            # right_marker_color = None (デフォルト)

                    elif handedness.classification[0].label == 'Right': # カメラ映像が反転しているので、ラベルも反転
                        left_cursor_pos[:] = hand_pos # 左手として扱う
                        is_flick = is_dekopin_motion(hand_landmarks, left_index_pip_y_history)

                        if is_tame:
                            left_hand_state = 'TAME'
                            left_marker_color = YELLOW_MARKER
                        elif left_hand_state == 'TAME' and is_flick:
                            left_hand_state = 'OPEN' # 状態をリセット
                            left_marker_color = GREEN_MARKER
                            if pygame.time.get_ticks() - last_dekopin_left > DEKOPIN_COOLDOWN:
                                dekopin_left_this_frame = True
                                last_dekopin_left = pygame.time.get_ticks()
                        else:
                            left_hand_state = 'OPEN'
                            # left_marker_color = None (デフォルト)
            
            # (was_open, is_open_currentのロジックは不要になったため削除)

        else:
             if cap.isOpened():
                 print("Warning: Failed to read frame from camera.")
             left_cursor_pos[:] = [-100, -100]
             right_cursor_pos[:] = [-100, -100]

    else:
        # left_is_open_current = True (不要)
        # right_is_open_current = True (不要)
        left_cursor_pos[:] = [-100, -100]
        right_cursor_pos[:] = [-100, -100]


    # --- ゲームロジック (状態に基づいて実行) ---

    left_cursor_rect_game = pygame.Rect(left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    right_cursor_rect_game = pygame.Rect(right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
    start_button_rect_game = start_button_rect_screen.copy()
    start_button_rect_game.center = (start_button_rect_screen.centerx - GAME_PANEL_RECT.left, start_button_rect_screen.centery - GAME_PANEL_RECT.top)
    retry_button_rect_game = retry_button_rect_screen.copy()
    retry_button_rect_game.center = (retry_button_rect_screen.centerx - GAME_PANEL_RECT.left, GAME_HEIGHT - 80) # 下端に固定

    if game_state == 'READY':
        start_activated = False
        # ★修正: スタートボタン上で「デコピン攻撃(緑マーカー)」をしたときにスタート
        if dekopin_left_this_frame: # (dekopin_left_this_frameは緑マーカーの時だけTrueになる)
            dekopin_hit_circle_left = pygame.Rect(left_cursor_pos[0] - dekopin_range_radius, left_cursor_pos[1] - dekopin_range_radius, dekopin_range_radius * 2, dekopin_range_radius * 2)
            if start_button_rect_game.colliderect(dekopin_hit_circle_left):
                start_activated = True
        elif dekopin_right_this_frame:
            dekopin_hit_circle_right = pygame.Rect(right_cursor_pos[0] - dekopin_range_radius, right_cursor_pos[1] - dekopin_range_radius, dekopin_range_radius * 2, dekopin_range_radius * 2)
            if start_button_rect_game.colliderect(dekopin_hit_circle_right):
                start_activated = True
        
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

        # 敵の生成 (ロジックは変更なし)
        enemy_spawn_timer += delta_time_ms
        while enemy_spawn_timer >= enemy_spawn_interval:
            enemy_spawn_timer -= enemy_spawn_interval

            new_enemy = None
            if red_enemies_spawned % 2 == 0 and red_enemies_spawned > 0 and enemy_images.get("orange") and (purple_enemies_spawned + red_enemies_spawned) > 0:
                new_enemy = Enemy(enemy_images["orange"], 2, "orange")
                red_enemies_spawned = 0 
            elif purple_enemies_spawned % 10 == 0 and purple_enemies_spawned > 0 and enemy_images.get("red"):
                new_enemy = Enemy(enemy_images["red"], 3, "red")
                purple_enemies_spawned = 0
            else:
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
        hit_dekopin = False
        hit_pos_x = -1 
        hit_pos_y = -1

        if dekopin_left_this_frame and left_cursor_pos[0] != -100: # ★修正 (攻撃判定はdekpoin_this_frameのみ)
            hit_dekopin = True
            hit_pos_x = left_cursor_pos[0]
            hit_pos_y = left_cursor_pos[1]
        elif dekopin_right_this_frame and right_cursor_pos[0] != -100: # ★修正
            hit_dekopin = True
            hit_pos_x = right_cursor_pos[0]
            hit_pos_y = right_cursor_pos[1]
        
        if hit_dekopin:
            dekopin_hit_circle = pygame.Rect(hit_pos_x - dekopin_range_radius, hit_pos_y - dekopin_range_radius, dekopin_range_radius * 2, dekopin_range_radius * 2)
            for enemy in list(enemies): 
                if enemy.rect.colliderect(dekopin_hit_circle):
                    if enemy.take_damage(1): 
                        enemies.remove(enemy)
                        enemy_count_on_screen -= 1
                        score += 1
                    # (breakなしで範囲内すべてにヒット)

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
            # ★修正: ホバー判定は「溜め(黄色)」または「攻撃(緑)」のマーカーが出ている時
            is_hovering_start = False
            if left_marker_color is not None:
                dekopin_hit_circle_left_game = pygame.Rect(left_cursor_pos[0] - dekopin_range_radius, left_cursor_pos[1] - dekopin_range_radius, dekopin_range_radius * 2, dekopin_range_radius * 2)
                if start_button_rect_game.colliderect(dekopin_hit_circle_left_game):
                    is_hovering_start = True
            if right_marker_color is not None:
                dekopin_hit_circle_right_game = pygame.Rect(right_cursor_pos[0] - dekopin_range_radius, right_cursor_pos[1] - dekopin_range_radius, dekopin_range_radius * 2, dekopin_range_radius * 2)
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
            dekopin_circle_surface_left = pygame.Surface((dekopin_range_radius * 2, dekopin_range_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(dekopin_circle_surface_left, left_marker_color, (dekopin_range_radius, dekopin_range_radius), dekopin_range_radius)
            game_surface.blit(dekopin_circle_surface_left, (left_cursor_pos[0] - dekopin_range_radius, left_cursor_pos[1] - dekopin_range_radius))

        if right_marker_color: # Noneでなければ(黄色か緑なら)描画
            dekopin_circle_surface_right = pygame.Surface((dekopin_range_radius * 2, dekopin_range_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(dekopin_circle_surface_right, right_marker_color, (dekopin_range_radius, dekopin_range_radius), dekopin_range_radius)
            game_surface.blit(dekopin_circle_surface_right, (right_cursor_pos[0] - dekopin_range_radius, right_cursor_pos[1] - dekopin_range_radius))


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