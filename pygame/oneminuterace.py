import cv2
import mediapipe as mp
import pygame
import math
import random
import numpy as np # カメラ映像変換に必要

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

# --- ゲーム設定と物理定義 ---
PIXELS_PER_METER = 360

# ★変更: 壁の全長を長く設定 (200m)
TOTAL_CLIMB_METERS = 200.0
MAX_PULL_METERS = 2.0
# ★(削除) GOAL_HOLD_METERS = 50.0

# ★変更: ゲーム時間を定義 (60秒 = 60000ms)
GAME_DURATION_MS = 60000

TOTAL_CLIMB_PIXELS = int(TOTAL_CLIMB_METERS * PIXELS_PER_METER)
MAX_PULL_PIXELS = int(MAX_PULL_METERS * PIXELS_PER_METER)

GRAVITY_ACCEL = 0.8
current_fall_velocity = 0.0
MAX_FALL_SPEED = 30

# Pygameウィンドウの設定
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
# ★変更: タイトルを「1 Minute Climb」に変更
pygame.display.set_caption("Bouldering Game (1 Minute Climb)")

# 色とフォントの定義
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
GRAY = (50, 50, 50)
SKY_BLUE = (135, 206, 235)
BLUE = (0, 0, 255)
ORANGE = (255, 165, 0)

font_ui = pygame.font.Font(None, 36)
font_log = pygame.font.Font(None, 24)
font_title = pygame.font.Font(None, 40)
goal_text_font = pygame.font.Font(None, 80)

# ★ ゴール背景の読み込み (終了画面用)
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

# --- (削除) ゴールホールド画像の読み込み ---
# goal_hold_image = None (削除)
# goal_hold_rect_world = None (削除)

# プレイヤー（カーソル）の設定 (左右別々に)
left_cursor_pos = [-100, -100]
right_cursor_pos = [-100, -100]
cursor_radius = 45

# --- 背景タイルの読み込み ---
tile_image = None
tile_width = 0
tile_height = 0
try:
    # ★変更: .convert_alpha() を推奨
    tile_image = pygame.image.load("image/backsnow.png").convert_alpha() 
    tile_width = tile_image.get_width()
    tile_height = tile_image.get_height()
    if tile_width <= 0 or tile_height <= 0:
        print("エラー: 背景画像のサイズが不正です。")
        tile_image = None
except FileNotFoundError:
    print("エラー: image/backsnow.png が見つかりません。")
# ★★★ここまで追加★★★


# Webカメラの準備
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("エラー: カメラを起動できません。")
    running = False



# 背景スクロール用の変数
# ★変更: full_background を使わず、TOTAL_CLIMB_PIXELS から直接計算
max_scroll = TOTAL_CLIMB_PIXELS - GAME_HEIGHT
world_y_offset = max_scroll

# 壁の全長(200m)が画面ハイトより低い設定など、ありえないが念のため
if max_scroll < 0:
    max_scroll = 0
    world_y_offset = 0

# --- ホールド（掴む岩）の生成 ---
holds_list = []
hold_image = None
try:
    hold_image = pygame.image.load("image/blockcatch.png").convert_alpha()
    hold_rect_img = hold_image.get_rect() # 画像自体のRectを取得
    hold_width, hold_height = hold_rect_img.width, hold_rect_img.height

    current_y = TOTAL_CLIMB_PIXELS - (GAME_HEIGHT // 2)
    side = 0

    # ★変更: ゴールホールドがなくなったので、壁の上端近くまで生成
    min_hold_y = 50 # 壁の上端から50px

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
        
        # ホールドの間隔を 0.7m に
        current_y -= int(PIXELS_PER_METER * 0.7)
        
        side = 1 - side
except FileNotFoundError:
    print("エラー: image/blockcatch.png が見つかりません。")

# --- 掴み状態の管理変数 (左右別々に) ---
left_was_holding = False
right_was_holding = False
left_hold_start_y = 0
right_hold_start_y = 0
world_hold_start_y = 0

# --- ★ゲーム状態の管理 ---
game_finished = False # game_won から 'game_finished' に名前変更

# --- (削除) ゴールホールドタッチ変数 ---
# touching_goal_hold_left = False (削除)
# ... (関連変数すべて削除)


# --- ★タイマー変数 ---
start_time = 0
# ★変更: elapsed_time を remaining_time_ms に変更
remaining_time_ms = GAME_DURATION_MS
final_time = 0
game_start_flag = False
# ★追加: 最終的な高さを保存する変数
final_height_meters = 0.0


# --- ★テキストログ変数 ---
log_messages = []
MAX_LOG_LINES = 6

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

# --- メインループ ---
running = True
clock = pygame.time.Clock()
# ★変更: ログメッセージ
add_log("Game Ready.")
add_log("Grab to start 60sec climb.")
# ★ カメラ映像を保持する変数
camera_surface_scaled = None

while running:

    delta_time_ms = clock.get_time()

    if 'max_scroll' in locals():
        height_climbed = (max_scroll - world_y_offset) / PIXELS_PER_METER
        if height_climbed < 0: height_climbed = 0.0 # マイナス表示防止
    else:
        height_climbed = 0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                running = False

            # --- (削除) 'R' キーのロケット機能 ---
            # if event.key == pygame.K_r ... (削除)

    screen.fill(GRAY)

    # ★変更: if game_won: -> if game_finished:
    if game_finished:
        # --- ★★★ GAME FINISHED ★★★ ---

        # 終了時のログ（一度だけ追加される）
        if final_time == 0: 
            final_time = GAME_DURATION_MS
            add_log(f"FINISH! Height: {final_height_meters:.1f}m")

        game_surface = screen.subsurface(GAME_PANEL_RECT)

        if goal_background_image:
            game_surface.blit(goal_background_image, (0, 0))
        else:
            game_surface.fill(SKY_BLUE)

        # ★変更: 最終的な高さを表示
        goal_text_str = f"{final_height_meters:.1f}m Climb Success!!"
        goal_text = goal_text_font.render(goal_text_str, True, ORANGE)
        game_surface.blit(goal_text, (
            game_surface.get_width() // 2 - goal_text.get_width() // 2,
            game_surface.get_height() // 4 - goal_text.get_height() // 2
        ))

        # ★変更: タイムを 01:00.00 に固定
        time_text = font_ui.render(f"Total Time: {format_time(GAME_DURATION_MS)}", True, ORANGE)
        game_surface.blit(time_text, (
            game_surface.get_width() // 2 - time_text.get_width() // 2,
            game_surface.get_height() // 4 + goal_text.get_height()
        ))

        if dancer_images:
            dancer_frame_time += delta_time_ms
            if dancer_frame_time > ANIMATION_SPEED_MS:
                dancer_frame = (dancer_frame + 1) % len(dancer_images)
                dancer_frame_time = 0

            current_dancer_image = dancer_images[dancer_frame]
            img_rect = current_dancer_image.get_rect(center=(game_surface.get_width() // 2, game_surface.get_height() // 2 + 100))
            game_surface.blit(current_dancer_image, img_rect)

        if cap.isOpened():
            cap.release()

    # ★変更: elif not game_won: -> elif not game_finished:
    elif not game_finished:
        # --- ★★★ GAME RUNNING ★★★ ---

        # ★ タイマーチェック (UI描画セクションからここに移動)
        if game_start_flag:
            elapsed_raw = pygame.time.get_ticks() - start_time
            remaining_time_ms = GAME_DURATION_MS - elapsed_raw
            if remaining_time_ms <= 0:
                remaining_time_ms = 0
                game_finished = True # ★★★ タイムアップ ★★★
                final_time = GAME_DURATION_MS
                final_height_meters = (max_scroll - world_y_offset) / PIXELS_PER_METER
                if final_height_meters < 0: final_height_meters = 0.0
        else:
            remaining_time_ms = GAME_DURATION_MS


        if not cap.isOpened():
            add_log("Camera feed lost.")
            break

        success, image_cam = cap.read()
        if not success: continue

        # 2. 手の検出
        image_rgb = cv2.cvtColor(cv2.flip(image_cam, 1), cv2.COLOR_BGR2RGB)
        image_rgb.flags.writeable = False
        results = hands.process(image_rgb)

        # 3. ★ カメラ映像の準備 (描画は後で)
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(image_bgr, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pygame = pygame.image.frombuffer(image_rgb.tobytes(), image_rgb.shape[1::-1], "RGB")
        camera_surface_scaled = pygame.transform.scale(image_pygame, (CAM_PANEL_RECT.width, CAM_PANEL_RECT.height))


        # 4. ジェスチャーとゲームロジック
        left_is_grabbing = False
        right_is_grabbing = False
        left_cursor_pos[:] = [-100, -100]
        right_cursor_pos[:] = [-100, -100]

        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                is_open = is_hand_open(hand_landmarks)
                mcp_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP]
                hand_pos = (int(mcp_landmark.x * GAME_PANEL_WIDTH), int(mcp_landmark.y * GAME_HEIGHT))
                
                if handedness.classification[0].label == 'Left':
                    left_is_grabbing = not is_open
                    left_cursor_pos[:] = hand_pos
                elif handedness.classification[0].label == 'Right':
                    right_is_grabbing = not is_open
                    right_cursor_pos[:] = hand_pos

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

        # --- (削除) ゴールホールドの当たり判定 ---
        # goal_hold_rect_screen = None (削除)
        # ...

        # --- ★★★ 掴みとスクロールのロジック ★★★ ---
        
        # ★変更: ゴールホールド判定を削除
        left_can_grab = left_is_grabbing and (left_colliding_hold is not None)
        right_can_grab = right_is_grabbing and (right_colliding_hold is not None)

        if not game_start_flag and (left_can_grab or right_can_grab):
            game_start_flag = True
            start_time = pygame.time.get_ticks()
            add_log("Climb START!")

        left_grabbed_this_frame = left_can_grab and not left_was_holding
        right_grabbed_this_frame = right_can_grab and not right_was_holding

        # ★変更: ゴールホールド判定を削除
        if (left_grabbed_this_frame) or (right_grabbed_this_frame):
            world_hold_start_y = world_y_offset
            if left_can_grab:
                left_hold_start_y = left_cursor_pos[1]
            if right_can_grab:
                right_hold_start_y = right_cursor_pos[1]

        # ★変更: ゴールホールド判定を削除
        if left_can_grab or right_can_grab:
            current_fall_velocity = 0
            pull_distance_left = 0
            pull_distance_right = 0
            if left_can_grab:
                pull_distance_left = left_cursor_pos[1] - left_hold_start_y
            if right_can_grab:
                pull_distance_right = right_cursor_pos[1] - right_hold_start_y

            pull_distance = max(pull_distance_left, pull_distance_right)

            if pull_distance < 0: pull_distance = 0
            if pull_distance > MAX_PULL_PIXELS: pull_distance = MAX_PULL_PIXELS

            world_y_offset = world_hold_start_y - pull_distance
        
        # ★変更: ゴールホールド判定(elif)を削除
        else:
            current_fall_velocity += GRAVITY_ACCEL
            if current_fall_velocity > MAX_FALL_SPEED:
                current_fall_velocity = MAX_FALL_SPEED
            world_y_offset += int(current_fall_velocity)

        left_was_holding = left_can_grab
        right_was_holding = right_can_grab

        if world_y_offset > max_scroll: world_y_offset = max_scroll
        if world_y_offset < 0: world_y_offset = 0

        # --- (削除) ゴール判定 (両手タッチ1秒) ---
        # if touching_goal_hold_left and ... (削除)

        # 5. Pygameの描画処理

        game_surface = screen.subsurface(GAME_PANEL_RECT)

        # ★★★ここから変更★★★
        # --- 動的な背景タイリング ---
        if tile_image and tile_height > 0 and tile_width > 0:
            
            # 画面のY座標 0 (world_y_offset) に最も近い、
            # タイルの開始Y座標 (世界座標) を計算
            start_y_world = (world_y_offset // tile_height) * tile_height

            # 画面内に見えるタイルをループ
            y = start_y_world
            while y < world_y_offset + GAME_HEIGHT:
                
                # タイルのX座標をループ
                x = 0
                while x < GAME_PANEL_WIDTH:
                    
                    # 世界座標 (x, y) を画面座標 (x, screen_y) に変換
                    screen_y = y - world_y_offset
                    game_surface.blit(tile_image, (x, screen_y))
                    
                    x += tile_width
                y += tile_height
        
        else:
            # 画像がない場合は空の色で塗りつぶす
            game_surface.fill(SKY_BLUE)
        # ★★★ここまで変更★★★
        if hold_image:
            for rect in visible_holds_for_drawing:
                game_surface.blit(hold_image, rect)

        # --- (削除) ゴールホールドの描画 ---
        # if goal_hold_image and goal_hold_rect_screen: ... (削除)

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

    # --- ★★★ UIパネルの描画 (全状態共通) ★★★ ---

    # ★ タイマーロジックは GAME_RUNNING セクションの先頭に移動しました

    # --- スコアパネル (左上) ---
    score_surface = screen.subsurface(SCORE_PANEL_RECT)
    score_surface.fill(BLACK)
    title_text = font_title.render("SCORE", True, WHITE)
    score_surface.blit(title_text, (10, 10))

    display_height = height_climbed
    if game_finished:
        display_height = final_height_meters # 終了したら最終結果に固定

    height_text_str = f"Height: {display_height:.1f} m"
    height_text = font_ui.render(height_text_str, True, WHITE)
    score_surface.blit(height_text, (15, 60))

    # ★変更: 常に remaining_time_ms を表示
    time_text_str = f"Time: {format_time(remaining_time_ms)}"
    time_text = font_ui.render(time_text_str, True, WHITE)
    score_surface.blit(time_text, (15, 110))

    r_text1 = font_log.render("Please reload,", True, GREEN)
    r_text2 = font_log.render("if you want to retry.", True, GREEN)
    score_surface.blit(r_text1, (15, 230))
    score_surface.blit(r_text2, (15, 260))


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
    pygame.draw.rect(cam_surface, BLACK, (0, 0, CAM_PANEL_RECT.width, CAM_PANEL_RECT.height)) # 背景を黒で
    cam_surface.blit(cam_title, (10, 10)) # タイトルを描画

    # ★変更: not game_finished
    if not game_finished and cap.isOpened():
        if camera_surface_scaled:
            cam_surface.blit(camera_surface_scaled, (0, 30))
    elif not cap.isOpened() and not game_finished:
        cam_error_text = font_log.render("Camera not found.", True, RED)
        cam_surface.blit(cam_error_text, (10, 50))
    # ★ game_finished の場合は黒背景+タイトルのみ

    # 画面更新 (全状態共通)
    pygame.display.flip()
    clock.tick(60)

# --- 終了処理 ---
if cap.isOpened():
    cap.release()
cv2.destroyAllWindows()
pygame.quit()