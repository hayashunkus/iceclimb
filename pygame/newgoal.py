import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np # カメラ映像変換に必要
import sys # ★ リトライ用にインポート

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
pygame.font.init() # フォントモジュールを明示的に初期化

# --- ★ 画面レイアウト定義 ---
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
LEFT_PANEL_WIDTH = int(SCREEN_WIDTH * 0.2) # 256
GAME_PANEL_WIDTH = SCREEN_WIDTH - LEFT_PANEL_WIDTH # 1024
GAME_HEIGHT = SCREEN_HEIGHT # 720

# 各パネルのRectを定義
SCORE_PANEL_RECT = pygame.Rect(0, 0, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.4))
LOG_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
CAM_PANEL_RECT = pygame.Rect(0, SCORE_PANEL_RECT.height + LOG_PANEL_RECT.height, LEFT_PANEL_WIDTH, int(SCREEN_HEIGHT * 0.3))
GAME_PANEL_RECT = pygame.Rect(LEFT_PANEL_WIDTH, 0, GAME_PANEL_WIDTH, GAME_HEIGHT)

# --- ★エネミーの定義 ---
class Enemy(pygame.sprite.Sprite):
    def __init__(self, image, speed=2):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, GAME_PANEL_WIDTH - self.rect.width)
        self.rect.y = -self.rect.height
        self.speed = speed

    def update(self):
        self.rect.y += self.speed

    def draw(self, surface):
        surface.blit(self.image, self.rect)


# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360
TOTAL_CLIMB_METERS = 105.0
MAX_PULL_METERS = 2.0
GOAL_HOLD_METERS = 100.0 # ★ ゴールホールドの設置高さ

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)

GRAVITY_ACCEL = 0.8
current_fall_velocity = 0.0
MAX_FALL_SPEED = 30
FPS = 60 # ★ フレームレート定義

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption(f"Bouldering Game ({int(GOAL_HOLD_METERS)}m Climb)")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)
BUTTON_COLOR = (0, 100, 200) # ★ リトライボタン用
BUTTON_HOVER_COLOR = (0, 150, 255) # ★ リトライボタン用
BUTTON_TEXT_COLOR = WHITE # ★ リトライボタン用

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
game_over_font = pygame.font.Font(None, 100)
goal_text_font = pygame.font.Font(None, 80)
button_font_small = pygame.font.Font(None, 30) # ★ リトライボタン用の小さいフォント

# ★エネミーの画像読み込み
enemy_image = None
try:
    enemy_image = pygame.image.load("image/enemy.png").convert_alpha()
except FileNotFoundError:
    print("エラー: image/enemy.png が見つかりません。")

# ★ ゴール背景の読み込み
goal_background_image = None
try:
    img = pygame.image.load("image/goaliceclimb.png").convert()
    goal_background_image = pygame.transform.scale(img, (GAME_PANEL_WIDTH, GAME_HEIGHT))
except FileNotFoundError:
    print("エラー: image/goaliceclimb.png が見つかりません。")

# ★ ダンサーアニメーション画像の読み込み
dancer_images = []
dancer_frame = 0
dancer_frame_time = 0
ANIMATION_SPEED_MS = 100
try:
    for i in range(1, 6):
        img_path = f"image/c-dancer-{i}.png"
        img = pygame.image.load(img_path).convert_alpha()
        img = pygame.transform.scale(img, (300, 300))
        dancer_images.append(img)
except FileNotFoundError as e:
    print(f"エラー: ダンサー画像が見つかりません。 {e}")

# ★ ゴールホールド画像の読み込み
goal_hold_image = None
goal_hold_rect_world = None # ワールド座標でのRect
try:
    goal_hold_image = pygame.image.load("image/goalhold.png").convert_alpha()
    img_rect = goal_hold_image.get_rect()
    goal_y = TOTAL_CLIMB_PIXELS - (GOAL_HOLD_METERS * PIXELS_PER_METER) - img_rect.height
    goal_x = (GAME_PANEL_WIDTH - img_rect.width) // 2
    goal_hold_rect_world = pygame.Rect(goal_x, goal_y, img_rect.width, img_rect.height)
except FileNotFoundError:
    print("エラー: image/goalhold.png が見つかりません。")


# ★エネミー管理リスト
enemy_list = []

# ★エネミー出現イベント
ENEMY_SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(ENEMY_SPAWN_EVENT, 5000)

# プレイヤー（カーソル）の設定 (左右別々に)
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45

# ★デコピン（Flick）検知用の変数
FLICK_THRESHOLD = 40
left_middle_tip_y = [0, 0]
right_middle_tip_y = [0, 0]
left_flick_pos = [-100, -100]
right_flick_pos = [-100, -100]
left_flick_detected = False
right_flick_detected = False


# Webカメラの準備
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")
    # この時点では running = False にしない

# --- 100mの壁を生成 ---
full_background = None
try:
    tile_image = pygame.image.load("image/backsnow.png").convert()
    tile_height = tile_image.get_height()
    full_background = pygame.Surface((GAME_PANEL_WIDTH, TOTAL_CLIMB_PIXELS))
    for y in range(0, TOTAL_CLIMB_PIXELS, tile_height):
        full_background.blit(tile_image, (0, y))
except FileNotFoundError:
    print("エラー: image/backsnow.png が見つかりません。")

# 背景スクロール用の変数
max_scroll = 0 # ★ グローバルスコープで初期化
if full_background:
    max_scroll = full_background.get_height() - GAME_HEIGHT
    world_y_offset = max_scroll
else:
    world_y_offset = 0

# --- ホールド（掴む岩）の生成 ---
holds_list = []
hold_image = None
try:
    hold_image = pygame.image.load("image/blockcatch.png").convert_alpha()
    hold_rect_img = hold_image.get_rect()
    hold_width, hold_height = hold_rect_img.width, hold_rect_img.height

    current_y = TOTAL_CLIMB_PIXELS - (GAME_HEIGHT // 2)
    side = 0

    min_hold_y = 0
    if goal_hold_rect_world:
        min_hold_y = goal_hold_rect_world.bottom + 50

    while current_y > min_hold_y:
        y_variation = random.randint(-PIXELS_PER_METER // 4, PIXELS_PER_METER // 4)
        h_y = current_y + y_variation
        if h_y < min_hold_y:
            h_y = min_hold_y + random.randint(10, 50)
        if h_y > TOTAL_CLIMB_PIXELS - hold_height:
             h_y = TOTAL_CLIMB_PIXELS - hold_height - random.randint(10, 50)

        x_variation = random.randint(-80, 80)
        if side == 0:
            h_x = (GAME_PANEL_WIDTH / 4) - (hold_width / 2) + x_variation
        else:
            h_x = (GAME_PANEL_WIDTH * 3 / 4) - (hold_width / 2) + x_variation

        holds_list.append(pygame.Rect(h_x, h_y, hold_width, hold_height))
        current_y -= PIXELS_PER_METER
        side = 1 - side
except FileNotFoundError:
    print("エラー: image/blockcatch.png が見つかりません。")

# --- 掴み状態の管理変数 (左右別々に) ---
left_was_holding = False # ★ 修正: 前フレームで掴めていたか (can_grab)
right_was_holding = False # ★ 修正: 前フレームで掴めていたか (can_grab)
left_hold_start_y = 0   # ★ 手のY座標アンカー
right_hold_start_y = 0  # ★ 手のY座標アンカー
# world_hold_start_y = 0 # ★ 削除
world_anchor_y_left = 0  # ★ 左手用のワールドY座標アンカー
world_anchor_y_right = 0 # ★ 右手用のワールドY座標アンカー


# --- ★ゲーム状態の管理 ---
game_over = False
game_won = False

# --- ★ ゴールホールドタッチ変数 ---
touching_goal_hold_left = False
touching_goal_hold_right = False
both_hands_touching_goal_start_time = 0
GOAL_TOUCH_DURATION_MS = 1000

# --- ★タイマー変数 ---
start_time = 0
elapsed_time = 0
final_time = 0
game_start_flag = False

# --- ★テキストログ変数 ---
log_messages = []
MAX_LOG_LINES = 6
enemy_kill_count = 0

# --- ★ リトライボタン ---
retry_button_rect_screen = pygame.Rect(0, 0, 300, 60)
retry_button_rect_screen.center = (GAME_PANEL_RECT.centerx, GAME_PANEL_RECT.bottom - 80)
# ゲームパネル内の座標に変換したRect (描画/判定用)
retry_button_rect_game = retry_button_rect_screen.copy()
retry_button_rect_game.center = (
    retry_button_rect_screen.centerx - GAME_PANEL_RECT.left,
    retry_button_rect_screen.centery - GAME_PANEL_RECT.top
)


# --- ★ 関数定義 ---

def is_hand_open(hand_landmarks):
    tip_ids = [mp_hands.HandLandmark.INDEX_FINGER_TIP, mp_hands.HandLandmark.MIDDLE_FINGER_TIP, mp_hands.HandLandmark.RING_FINGER_TIP, mp_hands.HandLandmark.PINKY_TIP]
    pip_ids = [mp_hands.HandLandmark.INDEX_FINGER_PIP, mp_hands.HandLandmark.MIDDLE_FINGER_PIP, mp_hands.HandLandmark.RING_FINGER_PIP, mp_hands.HandLandmark.PINKY_PIP]
    open_fingers = sum(1 for tip_id, pip_id in zip(tip_ids, pip_ids) if hand_landmarks.landmark[tip_id].y < hand_landmarks.landmark[pip_id].y)
    return open_fingers >= 3

def add_log(message):
    log_messages.append(message)
    if len(log_messages) > MAX_LOG_LINES:
        log_messages.pop(0)

def format_time(ms):
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    milliseconds = (ms % 1000) // 10
    return f"{minutes:02}:{seconds:02}.{milliseconds:02}"

# ★★★ リトライ（リセット）関数 ★★★
def reset_game():
    global game_over, game_won, world_y_offset, current_fall_velocity, left_was_holding, right_was_holding
    global elapsed_time, final_time, game_start_flag
    global enemy_list, enemy_kill_count, log_messages
    global cap, both_hands_touching_goal_start_time
    global left_hold_start_y, right_hold_start_y, world_anchor_y_left, world_anchor_y_right # ★ アンカーもリセット

    # ゲーム状態リセット
    game_over = False
    game_won = False

    # プレイヤー位置リセット
    world_y_offset = max_scroll # スタート地点
    current_fall_velocity = 0.0
    left_was_holding = False
    right_was_holding = False
    both_hands_touching_goal_start_time = 0
    left_hold_start_y = 0
    right_hold_start_y = 0
    world_anchor_y_left = 0
    world_anchor_y_right = 0


    # タイマーリセット
    elapsed_time = 0
    final_time = 0
    game_start_flag = False

    # 敵とログのリセット
    enemy_list = []
    enemy_kill_count = 0
    log_messages = []
    add_log("Game Ready. Press 'R' for 90m Rocket.")

    # カメラのリセット
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("Camera reopened for retry.")
        else:
            print("Error: Failed to reopen camera for retry.")
            add_log("Error: Camera failed to reopen.")

# --- メインループ ---
running = True
clock = pygame.time.Clock()
add_log("Game Ready. Press 'R' for 90m Rocket.")
camera_surface_scaled = None

while running:

    mouse_pos = pygame.mouse.get_pos() # ★ マウス位置取得
    mouse_click = False # ★ マウスクリックリセット

    if 'max_scroll' in locals():
        height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
    else:
        height_climbed = 0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False

            if event.key == pygame.K_r and not game_over and not game_won:
                warp_height_meters = 90.0
                current_max_scroll = (int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)) - GAME_HEIGHT
                warp_y_offset = current_max_scroll - (warp_height_meters * PIXELS_PER_METER)
                if warp_y_offset < 0: warp_y_offset = 0
                if warp_y_offset > current_max_scroll: warp_y_offset = current_max_scroll
                world_y_offset = warp_y_offset
                left_was_holding = False
                right_was_holding = False
                current_fall_velocity = 0
                add_log("ROCKET! Warping to 90m.")

        # ★ マウスクリックイベントを検出
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # 左クリック
                mouse_click = True

        if event.type == ENEMY_SPAWN_EVENT and not game_over and not game_won:
            if enemy_image:
                enemy_list.append(Enemy(enemy_image))

    screen.fill(GRAY)

    if game_won:
        # --- ★★★ GAME CLEAR ★★★ ---

        if final_time == 0:
            final_time = elapsed_time
            add_log(f"GOAL! Time: {format_time(final_time)}")
            if cap.isOpened(): # ★ クリア時にカメラを閉じる
                cap.release()
                print("Camera released on success.")

        game_surface = screen.subsurface(GAME_PANEL_RECT)

        if goal_background_image:
            game_surface.blit(goal_background_image, (0, 0))
        else:
            game_surface.fill(SKY_BLUE)

        goal_text = goal_text_font.render(f"{int(GOAL_HOLD_METERS)}m Climb Success!!", True, ORANGE)
        game_surface.blit(goal_text, (
            game_surface.get_width() // 2 - goal_text.get_width() // 2,
            game_surface.get_height() // 4 - goal_text.get_height() // 2
        ))

        time_text = font_ui.render(f"Clear Time: {format_time(final_time)}", True, ORANGE)
        game_surface.blit(time_text, (
            game_surface.get_width() // 2 - time_text.get_width() // 2,
            game_surface.get_height() // 4 + goal_text.get_height()
        ))

        if dancer_images:
            delta_time_ms_anim = clock.get_time() # アニメーション用に時間を取得
            dancer_frame_time += delta_time_ms_anim
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0

            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(game_surface.get_width() // 2, game_surface.get_height() // 2 + 100))
            game_surface.blit(current_dancer_image, img_rect)

        # ★ リトライボタンのロジック (マウスクリック)
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        is_hovering_retry = False
        if GAME_PANEL_RECT.collidepoint(mouse_pos):
             is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        if is_hovering_retry and mouse_click:
             reset_game()
        else:
            # ボタン描画
            btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
            pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
            btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
            game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))


    elif game_over:
        # --- ★★★ GAME OVER ★★★ ---
        if final_time == 0:
            final_time = elapsed_time
            add_log(f"GAME OVER... Time: {format_time(final_time)}")
            if cap.isOpened(): # ★ ゲームオーバー時にカメラを閉じる
                cap.release()
                print("Camera released on game over.")

        game_surface = screen.subsurface(GAME_PANEL_RECT)
        game_surface.fill(BLACK)
        go_text = game_over_font.render("GAME OVER", True, RED)
        game_surface.blit(go_text, (
            game_surface.get_width() // 2 - go_text.get_width() // 2,
            game_surface.get_height() // 2 - go_text.get_height() // 2 - 50
        ))

        time_text = font_ui.render(f"Final Time: {format_time(final_time)}", True, WHITE)
        game_surface.blit(time_text, (
            game_surface.get_width() // 2 - time_text.get_width() // 2,
            game_surface.get_height() // 2 + 50
        ))

        # ★ リトライボタンのロジック (マウスクリック)
        mouse_x_in_game = mouse_pos[0] - GAME_PANEL_RECT.left
        mouse_y_in_game = mouse_pos[1] - GAME_PANEL_RECT.top
        is_hovering_retry = False
        if GAME_PANEL_RECT.collidepoint(mouse_pos):
             is_hovering_retry = retry_button_rect_game.collidepoint(mouse_x_in_game, mouse_y_in_game)

        if is_hovering_retry and mouse_click:
             reset_game()
        else:
            # ボタン描画
            btn_color = BUTTON_HOVER_COLOR if is_hovering_retry else BUTTON_COLOR
            pygame.draw.rect(game_surface, btn_color, retry_button_rect_game, border_radius=10)
            btn_text = button_font_small.render("Retry Challenge", True, BUTTON_TEXT_COLOR)
            game_surface.blit(btn_text, btn_text.get_rect(center=retry_button_rect_game.center))

    else:
        # --- ★★★ GAME RUNNING ★★★ ---

        if not cap.isOpened():
            add_log("Camera feed lost.")
            # running = False # ★ 終了させずにUI表示は続ける

        camera_surface_scaled = None # ★ 毎フレームリセット
        left_is_grabbing = False # ★ 検出前にリセット
        right_is_grabbing = False # ★ 検出前にリセット
        left_is_open_now = True # ★ デフォルトは開
        right_is_open_now = True # ★ デフォルトは開

        if cap.isOpened():
            success, image_cam = cap.read()
            if not success:
                print("Warning: Failed to read frame.")
            else:
                # 2. 手の検出
                image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = hands.process(image_rgb)

                # 3. ★ カメラ映像の準備 (描画は後で)
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                if results and results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
                camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))


                # 4. ジェスチャーとゲームロジック
                left_flick_detected = False
                right_flick_detected = False

                left_cursor_pos[:] = [-100, -100]
                right_cursor_pos[:] = [-100, -100]
                left_flick_pos[:] = [-100, -100]
                right_flick_pos[:] = [-100, -100]

                if results and results.multi_hand_landmarks:
                    for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                        is_open = is_hand_open(hand_landmarks)
                        mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                        hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))

                        middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                        flick_pos_x = int(middle_tip.x * GAME_PANEL_WIDTH)
                        flick_pos_y = int(middle_tip.y * GAME_HEIGHT)

                        if handedness.classification[0].label == 'Left':
                            left_is_grabbing = not is_open
                            left_is_open_now = is_open # ★ 開閉状態を更新
                            left_cursor_pos[:] = hand_pos
                            left_flick_pos[:] = (flick_pos_x, flick_pos_y)

                            left_middle_tip_y[0] = left_middle_tip_y[1]
                            left_middle_tip_y[1] = flick_pos_y
                            flick_velocity = left_middle_tip_y[0] - left_middle_tip_y[1]

                            if is_open and flick_velocity > FLICK_THRESHOLD:
                                left_flick_detected = True

                        elif handedness.classification[0].label == 'Right':
                            right_is_grabbing = not is_open
                            right_is_open_now = is_open # ★ 開閉状態を更新
                            right_cursor_pos[:] = hand_pos
                            right_flick_pos[:] = (flick_pos_x, flick_pos_y)

                            right_middle_tip_y[0] = right_middle_tip_y[1]
                            right_middle_tip_y[1] = flick_pos_y
                            flick_velocity = right_middle_tip_y[0] - right_middle_tip_y[1]

                            if is_open and flick_velocity > FLICK_THRESHOLD:
                                right_flick_detected = True
        
        # ★ 手の開閉変化を検出 (カメラが失敗しても実行されるように外に出す)
        left_closed_this_frame = left_was_holding and not left_is_open_now # left_was_holding は前フレームの 'is_open' 状態
        right_closed_this_frame = right_was_holding and not right_is_open_now

        left_was_holding = left_is_open_now # 今フレームの状態を「前フレーム用」に保存
        right_was_holding = right_is_open_now

        # --- 当たり判定 (ホールド) ---
        left_cursor_rect = pygame.Rect(left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)
        right_cursor_rect = pygame.Rect(right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius, cursor_radius * 2, cursor_radius * 2)

        visible_holds_for_drawing = []
        left_colliding_hold = None
        right_colliding_hold = None

        if hold_image:
            min_y_world = world_y_offset
            max_y_world = world_y_offset + GAME_HEIGHT
            for hold_rect_world in holds_list:
                if hold_rect_world.bottom > min_y_world and hold_rect_world.top < max_y_world:
                    screen_rect = hold_rect_world.move(0, -world_y_offset)
                    visible_holds_for_drawing.append(screen_rect)

                    if left_colliding_hold is None and left_cursor_rect.colliderect(screen_rect):
                        left_colliding_hold = screen_rect
                    if right_colliding_hold is None and right_cursor_rect.colliderect(screen_rect):
                        right_colliding_hold = screen_rect

        # --- ★ ゴールホールドの当たり判定 ---
        goal_hold_rect_screen = None
        touching_goal_hold_left = False
        touching_goal_hold_right = False
        if goal_hold_rect_world:
            min_y_world = world_y_offset
            max_y_world = world_y_offset + GAME_HEIGHT
            if goal_hold_rect_world.bottom > min_y_world and goal_hold_rect_world.top < max_y_world:
                goal_hold_rect_screen = goal_hold_rect_world.move(0, -world_y_offset)
                if left_cursor_rect.colliderect(goal_hold_rect_screen):
                    touching_goal_hold_left = True
                if right_cursor_rect.colliderect(goal_hold_rect_screen):
                    touching_goal_hold_right = True

        # --- ★★★ 掴みとスクロールのロジック (V4 - 修正) ★★★
        left_can_grab_normal = left_is_grabbing and (left_colliding_hold is not None)
        right_can_grab_normal = right_is_grabbing and (right_colliding_hold is not None)
        left_can_grab_goal = left_is_grabbing and touching_goal_hold_left
        right_can_grab_goal = right_is_grabbing and touching_goal_hold_right

        left_can_grab = left_can_grab_normal or left_can_grab_goal
        right_can_grab = right_can_grab_normal or right_can_grab_goal


        if not game_start_flag and (left_can_grab or right_can_grab):
            game_start_flag = True
            start_time = pygame.time.get_ticks()
            add_log("Climb START!")

        left_grabbed_this_frame = left_can_grab and not left_was_holding # left_was_holding は前フレームの 'is_grabbing' 状態
        right_grabbed_this_frame = right_can_grab and not right_was_holding

        # --- アンカーポイントの設定 ---
        # 左手が新しく掴んだ
        if left_grabbed_this_frame:
            left_hold_start_y = left_cursor_pos[1] # 手のY座標を記録
            world_anchor_y_left = world_y_offset   # その時のワールドY座標を記録
        
        # 右手が新しく掴んだ
        if right_grabbed_this_frame:
            right_hold_start_y = right_cursor_pos[1] # 手のY座標を記録
            world_anchor_y_right = world_y_offset  # その時のワールドY座標を記録

        # --- スクロール計算 ---
        # (ゴールホールドを掴んでいる場合はスクロールしない)
        
        # まず、落下すると仮定
        current_fall_velocity += GRAVITY_ACCEL
        if current_fall_velocity > MAX_FALL_SPEED:
            current_fall_velocity = MAX_FALL_SPEED
        new_world_y_offset = world_y_offset + int(current_fall_velocity)

        # 各手が掴んでいる場合の目標Yオフセットを計算
        target_y_left = -1 # 左手の目標Y (未設定)
        target_y_right = -1 # 右手の目標Y (未設定)

        # 1. 左手が通常ホールドを掴んでいる場合
        if left_can_grab_normal:
            pull_distance_left = left_cursor_pos[1] - left_hold_start_y
            if pull_distance_left < 0: pull_distance_left = 0
            if pull_distance_left > MAX_PULL_PIXELS: pull_distance_left = MAX_PULL_PIXELS
            
            target_y_left = world_anchor_y_left - pull_distance_left
            new_world_y_offset = target_y_left # 落下をキャンセルし、左手の位置を採用
            current_fall_velocity = 0 # 落下速度リセット

        # 2. 右手が通常ホールドを掴んでいる場合
        if right_can_grab_normal:
            pull_distance_right = right_cursor_pos[1] - right_hold_start_y
            if pull_distance_right < 0: pull_distance_right = 0
            if pull_distance_right > MAX_PULL_PIXELS: pull_distance_right = MAX_PULL_PIXELS
            
            target_y_right = world_anchor_y_right - pull_distance_right
            current_fall_velocity = 0 # 落下速度リセット
            
            # 両手が掴んでいる場合、より高く登れる方(Yオフセットが小さい方)を採用
            if left_can_grab_normal:
                new_world_y_offset = min(target_y_left, target_y_right)
            else:
                new_world_y_offset = target_y_right # 右手のみ

        # 3. ゴールホールドだけ掴んでいる場合
        elif left_can_grab_goal or right_can_grab_goal:
            current_fall_velocity = 0 # 落下は止める
            new_world_y_offset = world_y_offset # スクロールはしない
        
        # 最終的なYオフセットを適用
        world_y_offset = new_world_y_offset

        # --- 状態保存 ---
        left_was_holding = left_can_grab
        right_was_holding = right_can_grab

        # --- 範囲制限 ---
        if world_y_offset > max_scroll: world_y_offset = max_scroll
        if world_y_offset < 0: world_y_offset = 0


        # --- ★ ゴール判定 (両手タッチ1秒) ---
        if touching_goal_hold_left and touching_goal_hold_right:
            if both_hands_touching_goal_start_time == 0:
                both_hands_touching_goal_start_time = pygame.time.get_ticks()
            else:
                touch_duration = pygame.time.get_ticks() - both_hands_touching_goal_start_time
                if touch_duration >= GOAL_TOUCH_DURATION_MS:
                    game_won = True # ★★★ ゲームクリア ★★★
        else:
            both_hands_touching_goal_start_time = 0


        # --- ★エネミーの更新と当たり判定 ---
        left_flick_rect = pygame.Rect(left_flick_pos[0] - cursor_radius, left_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)
        right_flick_rect = pygame.Rect(right_flick_pos[0] - cursor_radius, right_flick_pos[1] - cursor_radius, cursor_radius*2, cursor_radius*2)

        for enemy in enemy_list[:]:
            enemy.update()

            if enemy.rect.top > GAME_HEIGHT:
                enemy_list.remove(enemy)
                game_over = True
                break

            killed = False
            if left_flick_detected and left_flick_rect.colliderect(enemy.rect):
                enemy_list.remove(enemy)
                killed = True

            elif right_flick_detected and right_flick_rect.colliderect(enemy.rect):
                enemy_list.remove(enemy)
                killed = True

            if killed:
                enemy_kill_count += 1
                add_log(f"Enemy Defeated! ({enemy_kill_count})")
                if enemy_kill_count > 0 and enemy_kill_count % 5 == 0:
                    add_log("5 Kills! +10m Bonus!")
                    
                    min_y_offset_for_100m = max_scroll - (GOAL_HOLD_METERS * PIXELS_PER_METER)
                    
                    world_y_offset -= (10 * PIXELS_PER_METER)
                    
                    if world_y_offset < min_y_offset_for_100m:
                        world_y_offset = min_y_offset_for_100m
                    
                    left_was_holding = False
                    right_was_holding = False
                    current_fall_velocity = 0

        # ★ game_over チェック
        if game_over:
            pass # このフレームの残りは描画のみ

        # 5. Pygameの描画処理
        game_surface = screen.subsurface(GAME_PANEL_RECT)

        if full_background:
            game_surface.blit(full_background, (0, -world_y_offset))
        else:
            game_surface.fill(SKY_BLUE)

        if hold_image:
            for rect in visible_holds_for_drawing:
                game_surface.blit(hold_image, rect)

        if goal_hold_image and goal_hold_rect_screen:
             game_surface.blit(goal_hold_image, goal_hold_rect_screen)

        for enemy in enemy_list:
            enemy.draw(game_surface)

        left_cursor_color = GREEN if left_can_grab else RED
        right_cursor_color = GREEN if right_can_grab else RED
        ALPHA_VALUE = 128

        if left_cursor_pos[0] != -100:
            circle_surface_left = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_left, left_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_left, (left_cursor_pos[0] - cursor_radius, left_cursor_pos[1] - cursor_radius))

        if right_cursor_pos[0] != -100:
            circle_surface_right = pygame.Surface((cursor_radius * 2, cursor_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surface_right, right_cursor_color + (ALPHA_VALUE,), (cursor_radius, cursor_radius), cursor_radius)
            game_surface.blit(circle_surface_right, (right_cursor_pos[0] - cursor_radius, right_cursor_pos[1] - cursor_radius))

        if left_flick_detected:
            pygame.draw.circle(game_surface, BLUE, left_flick_pos, cursor_radius + 10, 5)
        if right_flick_detected:
            pygame.draw.circle(game_surface, BLUE, right_flick_pos, cursor_radius + 10, 5)

    # --- ★★★ UIパネルの描画 (全状態共通) ★★★ ---

    if game_start_flag and not game_won and not game_over:
        elapsed_time = pygame.time.get_ticks() - start_time

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("SCORE", True, WHITE)
    score_surface.blit(title_text, (10, 10))

    display_height = height_climbed
    if game_won:
        display_height = GOAL_HOLD_METERS

    height_text_str = f"Height: {display_height:.1f} m"
    height_text = font_ui.render(height_text_str, True, WHITE)
    score_surface.blit(height_text, (15, 60))

    time_text_str = f"Time: {format_time(elapsed_time)}"
    if final_time > 0:
        time_text_str = f"Time: {format_time(final_time)}"
    time_text = font_ui.render(time_text_str, True, WHITE)
    score_surface.blit(time_text, (15, 110))

    kill_text_str = f"Kills: {enemy_kill_count}"
    kill_text = font_ui.render(kill_text_str, True, WHITE)
    score_surface.blit(kill_text, (15, 160))

    r_text = font_log.render("'R' Key: 90m Rocket", True, GREEN)
    score_surface.blit(r_text, (15, 250))


    # --- ログパネル (左中) ---
    log_surface = screen.subsurface(LOG_PANEL_RECT)
    log_surface.fill(BLACK)
    log_title = font_title.render("LOG", True, WHITE)
    log_surface.blit(log_title, (10, 10))
    y_pos = 50
    for message in log_messages:
        log_text = font_log.render(message, True, GREEN)
        log_surface.blit(log_text, (15, y_pos))
        y_pos += 25

    # --- カメラパネル (左下) ---
    cam_title = font_title.render("CAMERA", True, WHITE)
    cam_surface = screen.subsurface(CAM_PANEL_RECT)
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))
    cam_surface.blit(cam_title, (10, 10))

    if cap.isOpened() and camera_surface_scaled:
        cam_surface.blit(camera_surface_scaled, (0, 30))
    elif not cap.isOpened():
         # ★ ゲーム実行中のみエラー表示
         if not game_won and not game_over:
             cam_error_text = font_log.render("Camera not found.", True, RED)
             cam_surface.blit(cam_error_text, (10, 50))
    
    # 画面更新 (全状態共通)
    pygame.display.flip()
    delta_time_ms = clock.tick(FPS) # ★ FPSを制御し、delta_time_ms を取得

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit() # ★ 確実な終了

#リトライできない